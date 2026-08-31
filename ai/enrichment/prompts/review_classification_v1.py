"""Prompt version v1. Bumping the classification taxonomy or instructions
means a new prompts/review_classification_v2.py plus a PROMPT_VERSION bump,
never an in-place edit of this file. See docs/data_contracts/review_enriched.yml's
breaking_change_policy and docs/architecture/04-ai-architecture.md."""

PROMPT_VERSION = "v1"

TOPICS = ["food quality", "delivery", "service", "packaging", "pricing", "other"]

SYSTEM_PROMPT = f"""
You classify customer reviews for a food delivery app.

For the review you are given, return:
- sentiment_label: positive, negative, or neutral
- sentiment_score: a number between -1.0 and 1.0
- topic: one of {TOPICS}
- key_issue: a short phrase of 6 words or less that describes the main issue in the review, if any. If there is no issue, return null

Reply as JSON in this exact format:
{{
    "sentiment_label": "<sentiment_label>",
    "sentiment_score": <sentiment_score>,
    "topic": "<topic>",
    "key_issue": "<key_issue>"
}}
"""
