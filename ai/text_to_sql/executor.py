"""Executes a ValidatedQuery under AI_READONLY_ROLE: the second, real
guardrail layer (ADR-006). Session-level statement timeout is already set by
get_ai_readonly_connection(); this module adds nothing beyond running the
query and returning a bounded result."""
from __future__ import annotations

import pandas as pd

from ai.text_to_sql.guardrails import ValidatedQuery
from snowflake.connector import SnowflakeConnection


def run_query(connection: SnowflakeConnection, query: ValidatedQuery) -> pd.DataFrame:
    cursor = connection.cursor()
    try:
        cursor.execute(query.sql)
        return cursor.fetch_pandas_all()
    finally:
        cursor.close()
