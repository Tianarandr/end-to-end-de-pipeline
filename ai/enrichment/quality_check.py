"""What Airflow's `ai_quality_checks` task calls. It judges whether an
enrichment batch's output is good enough to publish, separately from
whether the job merely executed (that's ai/enrichment/run.py's job). See
docs/architecture/07-data-quality.md#whats-tested.

A batch failing this check stops the DAG before `publish`: mart_review_insights
(tag:ai) never builds on top of an enrichment run that mostly failed.
"""
from __future__ import annotations

import argparse
import sys

from ai.common.config import load_settings
from ai.common.logging_utils import get_logger, log_event
from ai.common.snowflake_client import get_ai_enrich_connection
from observability.alerting import send_alert

logger = get_logger(__name__)

FAILURE_RATE_THRESHOLD = 0.2


class QualityCheckFailed(Exception):
    pass


def check_batch_quality(batch_id: str) -> dict:
    settings = load_settings()
    connection = get_ai_enrich_connection(settings)
    cursor = connection.cursor()
    cursor.execute(
        "SELECT status, COUNT(*) FROM AI.ENRICHMENT_LOG WHERE batch_id = %(batch_id)s GROUP BY status",
        {"batch_id": batch_id},
    )
    counts = dict(cursor.fetchall())
    connection.close()

    succeeded = counts.get("SUCCEEDED", 0)
    failed = counts.get("FAILED", 0)
    total = succeeded + failed
    failure_rate = (failed / total) if total else 0.0

    result = {"batch_id": batch_id, "succeeded": succeeded, "failed": failed, "failure_rate": round(failure_rate, 3)}
    log_event(logger, "ai_quality_check_result", **result)

    if total == 0:
        # Nothing attempted this batch (e.g. no new reviews) isn't a
        # failure, just a no-op. Only an actual high failure rate blocks
        # publish.
        return result

    if failure_rate > FAILURE_RATE_THRESHOLD:
        raise QualityCheckFailed(
            f"AI enrichment failure rate {failure_rate:.1%} exceeds the {FAILURE_RATE_THRESHOLD:.0%} "
            f"threshold for batch {batch_id} ({failed}/{total} reviews failed). "
            f"See AI.ENRICHMENT_LOG for error_message detail. Not proceeding to publish."
        )

    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check an AI enrichment batch's quality before publish.")
    parser.add_argument("--batch-id", required=True)
    args = parser.parse_args(argv)

    try:
        check_batch_quality(args.batch_id)
    except QualityCheckFailed as exc:
        log_event(logger, "ai_quality_check_failed", level=40, error=str(exc))
        send_alert(
            subject=f"AI enrichment batch {args.batch_id} failed quality check",
            message=str(exc),
            severity="critical",
            context={"batch_id": args.batch_id},
        )
        print(str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
