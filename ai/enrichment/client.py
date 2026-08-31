"""LLM call for a single review: retries on transient failures, then
structured-output validation. Idempotency and batching live in run.py; this
module just turns one review into a validated ReviewClassification, or
raises once retries are exhausted."""
from __future__ import annotations

import json

from openai import OpenAI
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from ai.enrichment.prompts.review_classification_v1 import PROMPT_VERSION, SYSTEM_PROMPT
from ai.enrichment.schema import ReviewClassification


class ClassificationError(Exception):
    """The model responded, but not with something schema.py accepts."""


def _retryable(settings_max_retries: int):
    return retry(
        reraise=True,
        stop=stop_after_attempt(settings_max_retries),
        wait=wait_exponential(multiplier=1, min=1, max=20),
        retry=retry_if_exception_type((TimeoutError, ConnectionError)),
    )


def classify_review(client: OpenAI, model: str, comment: str, max_retries: int) -> tuple[ReviewClassification, str]:
    """Returns (classification, model_version). Raises ClassificationError if
    the model's response doesn't validate against ReviewClassification even
    after retries. The caller (run.py) is responsible for logging that as a
    FAILED attempt, not for silently dropping it."""

    @_retryable(max_retries)
    def _call():
        return client.chat.completions.create(
            model=model,
            temperature=0,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": comment},
            ],
        )

    response = _call()
    raw = response.choices[0].message.content
    model_version = response.model  # provider-reported, e.g. "gpt-4o-mini-2024-07-18"

    try:
        payload = json.loads(raw)
        classification = ReviewClassification.model_validate(payload)
    except Exception as exc:
        raise ClassificationError(f"Model response failed schema validation: {exc}. Raw: {raw!r}") from exc

    return classification, model_version


__all__ = ["classify_review", "ClassificationError", "PROMPT_VERSION"]
