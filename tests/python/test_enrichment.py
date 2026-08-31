"""Unit tests for the AI enrichment layer's structured-output validation and
attempt logging. See docs/architecture/04-ai-architecture.md#a-batch-ai-enrichment-aienrichment
and docs/data_contracts/review_enriched.yml."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from pydantic import ValidationError

from ai.enrichment.pii import scrub_pii
from ai.enrichment.repository import get_reviews_to_process, log_attempt, write_success
from ai.enrichment.schema import ReviewClassification


def test_valid_classification_parses():
    c = ReviewClassification.model_validate(
        {"sentiment_label": "negative", "sentiment_score": -0.8, "topic": "delivery", "key_issue": "late delivery"}
    )
    assert c.sentiment_label == "negative"
    assert c.sentiment_score == -0.8


def test_classification_rejects_out_of_range_score():
    with pytest.raises(ValidationError):
        ReviewClassification.model_validate(
            {"sentiment_label": "negative", "sentiment_score": -5.0, "topic": "delivery", "key_issue": None}
        )


def test_classification_rejects_unknown_topic():
    with pytest.raises(ValidationError):
        ReviewClassification.model_validate(
            {"sentiment_label": "positive", "sentiment_score": 0.5, "topic": "not-a-real-topic", "key_issue": None}
        )


def test_classification_rejects_unknown_sentiment_label():
    with pytest.raises(ValidationError):
        ReviewClassification.model_validate(
            {"sentiment_label": "very positive", "sentiment_score": 0.9, "topic": "service", "key_issue": None}
        )


def test_key_issue_is_optional():
    c = ReviewClassification.model_validate(
        {"sentiment_label": "positive", "sentiment_score": 0.9, "topic": "service", "key_issue": None}
    )
    assert c.key_issue is None


def test_get_reviews_to_process_excludes_previously_failed_by_default():
    cursor = MagicMock()
    cursor.fetchall.return_value = [("r1", "great food")]

    get_reviews_to_process(cursor, batch_size=10, reprocess_failed=False)

    sql = cursor.execute.call_args[0][0]
    assert "ENRICHMENT_LOG WHERE status = 'FAILED'" in sql


def test_get_reviews_to_process_includes_failed_when_reprocessing():
    cursor = MagicMock()
    cursor.fetchall.return_value = []

    get_reviews_to_process(cursor, batch_size=10, reprocess_failed=True)

    sql = cursor.execute.call_args[0][0]
    assert "FAILED" not in sql or "ENRICHMENT_LOG WHERE status = 'FAILED'" not in sql


def test_log_attempt_records_failure_with_error_message():
    cursor = MagicMock()
    log_attempt(
        cursor, batch_id="b1", review_id="r1", attempt_number=1, status="FAILED",
        error_message="model timeout", model_name="gpt-4o-mini", model_version=None, prompt_version="v1",
    )
    params = cursor.execute.call_args[0][1]
    assert params["status"] == "FAILED"
    assert params["error_message"] == "model timeout"


def test_write_success_persists_all_traceability_fields():
    cursor = MagicMock()
    classification = ReviewClassification(sentiment_label="positive", sentiment_score=0.7, topic="pricing", key_issue=None)

    write_success(
        cursor, review_id="r1", classification=classification, model_name="gpt-4o-mini",
        model_version="gpt-4o-mini-2024-07-18", prompt_version="v1", batch_id="b1",
    )
    params = cursor.execute.call_args[0][1]
    for field in ("model_name", "model_version", "prompt_version", "batch_id", "processed_at"):
        assert params[field] is not None


def test_scrub_pii_redacts_email():
    scrubbed, count = scrub_pii("contact me at jane.doe@example.com about my order")
    assert "example.com" not in scrubbed
    assert "[REDACTED_EMAIL]" in scrubbed
    assert count == 1


def test_scrub_pii_redacts_credit_card():
    scrubbed, count = scrub_pii("charge failed on card 4111 1111 1111 1111 please retry")
    assert "4111" not in scrubbed
    assert "[REDACTED_CARD]" in scrubbed
    assert count == 1


def test_scrub_pii_redacts_phone_number():
    scrubbed, count = scrub_pii("call me back on 0412 345 678 tomorrow")
    assert "[REDACTED_PHONE]" in scrubbed
    assert count == 1


def test_scrub_pii_leaves_ordinary_review_text_untouched():
    text = "food was cold and delivery took forever, very disappointed"
    scrubbed, count = scrub_pii(text)
    assert scrubbed == text
    assert count == 0


def test_scrub_pii_handles_empty_string():
    scrubbed, count = scrub_pii("")
    assert scrubbed == ""
    assert count == 0
