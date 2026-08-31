"""Environment-driven config for the whole AI layer. No hardcoded
credentials, no hardcoded model names. See .env.example and
docs/architecture/05-security.md."""
from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class AISettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: str = "dev"

    openai_api_key: str
    ai_chat_model: str = "gpt-4o-mini"
    ai_embedding_model: str = "text-embedding-3-small"

    snowflake_account: str
    snowflake_warehouse: str = "DELIVERY_WH"
    snowflake_database: str

    # Writer path (ai/enrichment): reads STAGING, writes AI only.
    snowflake_ai_enrich_user: str = ""
    snowflake_ai_enrich_password: str = ""
    snowflake_ai_enrich_role: str = "AI_ENRICH_ROLE"

    # Reader path (ai/rag, ai/text_to_sql): SELECT on SEMANTIC only.
    snowflake_ai_readonly_user: str = ""
    snowflake_ai_readonly_password: str = ""
    snowflake_ai_readonly_role: str = "AI_READONLY_ROLE"

    ai_enrichment_batch_size: int = 50
    ai_enrichment_max_retries: int = 3
    ai_enrichment_prompt_version: str = "v1"

    text_to_sql_row_limit: int = 200
    text_to_sql_query_timeout_seconds: int = 30
    text_to_sql_allowed_schema: str = "SEMANTIC"


def load_settings() -> AISettings:
    return AISettings()
