"""One place every AI capability gets its OpenAI client from, so switching
providers/models, adding request logging, or adding a shared rate limiter is
a one-file change instead of a grep-and-replace across ai/enrichment, ai/rag,
and ai/text_to_sql."""
from __future__ import annotations

from functools import lru_cache

from openai import OpenAI

from ai.common.config import AISettings


@lru_cache(maxsize=1)
def _client(api_key: str) -> OpenAI:
    return OpenAI(api_key=api_key)


def get_client(settings: AISettings) -> OpenAI:
    return _client(settings.openai_api_key)
