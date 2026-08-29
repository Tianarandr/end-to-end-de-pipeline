"""Structured-output contract for review classification. The LLM's JSON
response is validated against this before it's ever written to Snowflake.
A malformed or out-of-range response fails loudly here instead of writing
garbage into AI.REVIEW_ENRICHED.sentiment_score. See
docs/data_contracts/review_enriched.yml."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Topic = Literal["food quality", "delivery", "service", "packaging", "pricing", "other"]
SentimentLabel = Literal["positive", "neutral", "negative"]


class ReviewClassification(BaseModel):
    sentiment_label: SentimentLabel
    sentiment_score: float = Field(ge=-1.0, le=1.0)
    topic: Topic
    key_issue: str | None = None
