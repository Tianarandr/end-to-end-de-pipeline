"""Role-scoped Snowflake connection factories. See ADR-006 and
docs/architecture/05-security.md. There are exactly two AI-facing roles,
and each function here gets exactly one of them; nothing in ai/ ever
connects with TRANSFORM_ROLE or a broader role, even for convenience."""
from __future__ import annotations

import snowflake.connector
from ai.common.config import AISettings
from snowflake.connector import SnowflakeConnection


def get_ai_enrich_connection(settings: AISettings) -> SnowflakeConnection:
    """Writer path: ai/enrichment. Reads STAGING.STG_REVIEWS, writes AI schema only."""
    return snowflake.connector.connect(
        account=settings.snowflake_account,
        user=settings.snowflake_ai_enrich_user,
        password=settings.snowflake_ai_enrich_password,
        role=settings.snowflake_ai_enrich_role,
        warehouse=settings.snowflake_warehouse,
        database=settings.snowflake_database,
        schema="AI",
    )


def get_ai_readonly_connection(settings: AISettings) -> SnowflakeConnection:
    """Reader path: ai/rag, ai/text_to_sql. SELECT on SEMANTIC only, which is
    the real enforcement boundary behind the text-to-SQL guardrails (see
    ADR-006). Also sets a session-level statement timeout as defense in depth
    alongside the role-level default (snowflake/01_roles_and_grants.sql)."""
    conn = snowflake.connector.connect(
        account=settings.snowflake_account,
        user=settings.snowflake_ai_readonly_user,
        password=settings.snowflake_ai_readonly_password,
        role=settings.snowflake_ai_readonly_role,
        warehouse=settings.snowflake_warehouse,
        database=settings.snowflake_database,
        schema=settings.text_to_sql_allowed_schema,
    )
    cursor = conn.cursor()
    cursor.execute(f"ALTER SESSION SET STATEMENT_TIMEOUT_IN_SECONDS = {int(settings.text_to_sql_query_timeout_seconds)}")
    cursor.close()
    return conn
