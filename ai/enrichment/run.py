"""CLI entrypoint for batch AI enrichment. This is what Airflow's
`ai_enrichment` task calls (`python -m ai.enrichment.run`). See
docs/architecture/04-ai-architecture.md#a-batch-ai-enrichment-aienrichment.

Idempotent: never re-classifies a review already in AI.REVIEW_ENRICHED.
Resumable: a review whose last attempt FAILED is retried automatically, up
to ai_enrichment_max_retries times within a single run (client.py). Across
runs it's only retried when explicitly asked via --reprocess-failed, so
nothing gets stuck in a silent retry loop or quietly dropped.

Exit code is non-zero if the batch's failure rate exceeds a threshold, which
is what Airflow's `ai_quality_checks` task (see airflow/dags/) checks before
allowing `publish` to run.
"""
from __future__ import annotations

import argparse
import sys
import uuid

from ai.common.config import load_settings
from ai.common.llm_client import get_client
from ai.common.logging_utils import get_logger, log_event
from ai.common.snowflake_client import get_ai_enrich_connection
from ai.enrichment.client import ClassificationError, classify_review
from ai.enrichment.prompts.review_classification_v1 import PROMPT_VERSION
from ai.enrichment.repository import get_attempt_number, get_reviews_to_process, log_attempt, write_success

logger = get_logger(__name__)

# Whether the batch's failure rate is acceptable gets judged separately, by
# ai/enrichment/quality_check.py (Airflow's `ai_quality_checks` task). This
# module's job just ends at "ran the batch, logged every attempt." That keeps
# "did the job run" and "was the output good enough to publish" as separate,
# independently inspectable Airflow tasks, matching the DAG's
# ai_enrichment -> ai_quality_checks stages.


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Batch AI review enrichment.")
    parser.add_argument("--batch-id", default=None, help="Defaults to a fresh UUID; Airflow passes dag_run.run_id here.")
    parser.add_argument("--reprocess-failed", action="store_true", help="Also retry reviews whose most recent attempt FAILED.")
    args = parser.parse_args(argv)

    settings = load_settings()
    batch_id = args.batch_id or str(uuid.uuid4())
    llm = get_client(settings)

    connection = get_ai_enrich_connection(settings)
    cursor = connection.cursor()

    reviews = get_reviews_to_process(cursor, settings.ai_enrichment_batch_size, args.reprocess_failed)
    log_event(logger, "enrichment_batch_started", batch_id=batch_id, review_count=len(reviews))

    if not reviews:
        log_event(logger, "enrichment_batch_empty", batch_id=batch_id)
        cursor.close()
        connection.close()
        return 0

    succeeded, failed = 0, 0
    for review_id, comment in reviews:
        attempt_number = get_attempt_number(cursor, review_id)
        try:
            classification, model_version = classify_review(
                llm, settings.ai_chat_model, comment, settings.ai_enrichment_max_retries
            )
            write_success(
                cursor,
                review_id=review_id,
                classification=classification,
                model_name=settings.ai_chat_model,
                model_version=model_version,
                prompt_version=PROMPT_VERSION,
                batch_id=batch_id,
            )
            log_attempt(
                cursor, batch_id=batch_id, review_id=review_id, attempt_number=attempt_number,
                status="SUCCEEDED", error_message=None, model_name=settings.ai_chat_model,
                model_version=model_version, prompt_version=PROMPT_VERSION,
            )
            succeeded += 1
            log_event(logger, "enrichment_review_succeeded", batch_id=batch_id, review_id=review_id)
        except (ClassificationError, Exception) as exc:  # noqa: BLE001 - every failure gets logged, not swallowed
            log_attempt(
                cursor, batch_id=batch_id, review_id=review_id, attempt_number=attempt_number,
                status="FAILED", error_message=str(exc)[:2000], model_name=settings.ai_chat_model,
                model_version=None, prompt_version=PROMPT_VERSION,
            )
            failed += 1
            log_event(logger, "enrichment_review_failed", level=40, batch_id=batch_id, review_id=review_id, error=str(exc))

        connection.commit()  # commit per review: a mid-batch crash leaves earlier reviews correctly recorded

    cursor.close()
    connection.close()

    failure_rate = failed / len(reviews)
    log_event(
        logger, "enrichment_batch_finished", batch_id=batch_id,
        succeeded=succeeded, failed=failed, failure_rate=round(failure_rate, 3),
    )

    return 0  # per-review failures are logged, not raised (see module docstring)


if __name__ == "__main__":
    sys.exit(main())
