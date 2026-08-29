"""All AI.REVIEW_ENRICHED / AI.ENRICHMENT_LOG access. Kept as plain functions
over a cursor (not a class) so tests can pass a mocked cursor. See
tests/python/test_enrichment_idempotency.py."""
from __future__ import annotations

from datetime import UTC, datetime


def get_reviews_to_process(cursor, batch_size: int, reprocess_failed: bool) -> list[tuple[str, str]]:
    """Selects reviews with no SUCCEEDED attempt yet. By default also skips
    reviews whose most recent attempt FAILED; those only get picked up again
    via --reprocess-failed, an explicit operator call rather than an
    automatic retry loop. That keeps failures visible instead of silently
    retrying forever in the background."""
    failed_clause = "" if reprocess_failed else """
        AND r.review_id NOT IN (
            SELECT review_id FROM AI.ENRICHMENT_LOG WHERE status = 'FAILED'
        )
    """
    cursor.execute(
        f"""
        SELECT r.review_id, r.comment
        FROM STAGING.STG_REVIEWS r
        WHERE r.review_id NOT IN (SELECT review_id FROM AI.REVIEW_ENRICHED)
        {failed_clause}
        LIMIT {int(batch_size)}
        """
    )
    return cursor.fetchall()


def get_attempt_number(cursor, review_id: str) -> int:
    cursor.execute(
        "SELECT COALESCE(MAX(attempt_number), 0) FROM AI.ENRICHMENT_LOG WHERE review_id = %(review_id)s",
        {"review_id": review_id},
    )
    (max_attempt,) = cursor.fetchone()
    return int(max_attempt) + 1


def log_attempt(cursor, *, batch_id: str, review_id: str, attempt_number: int, status: str,
                 error_message: str | None, model_name: str | None, model_version: str | None,
                 prompt_version: str | None) -> None:
    cursor.execute(
        """
        INSERT INTO AI.ENRICHMENT_LOG
            (batch_id, review_id, attempt_number, status, error_message, model_name, model_version, prompt_version, processed_at)
        VALUES (%(batch_id)s, %(review_id)s, %(attempt_number)s, %(status)s, %(error_message)s, %(model_name)s, %(model_version)s, %(prompt_version)s, %(processed_at)s)
        """,
        {
            "batch_id": batch_id,
            "review_id": review_id,
            "attempt_number": attempt_number,
            "status": status,
            "error_message": error_message,
            "model_name": model_name,
            "model_version": model_version,
            "prompt_version": prompt_version,
            "processed_at": datetime.now(UTC),
        },
    )


def write_success(cursor, *, review_id: str, classification, model_name: str, model_version: str,
                   prompt_version: str, batch_id: str) -> None:
    cursor.execute(
        """
        INSERT INTO AI.REVIEW_ENRICHED
            (review_id, sentiment_label, sentiment_score, topic, key_issue, model_name, model_version, prompt_version, batch_id, processed_at)
        VALUES (%(review_id)s, %(sentiment_label)s, %(sentiment_score)s, %(topic)s, %(key_issue)s, %(model_name)s, %(model_version)s, %(prompt_version)s, %(batch_id)s, %(processed_at)s)
        """,
        {
            "review_id": review_id,
            "sentiment_label": classification.sentiment_label,
            "sentiment_score": classification.sentiment_score,
            "topic": classification.topic,
            "key_issue": classification.key_issue,
            "model_name": model_name,
            "model_version": model_version,
            "prompt_version": prompt_version,
            "batch_id": batch_id,
            "processed_at": datetime.now(UTC),
        },
    )
