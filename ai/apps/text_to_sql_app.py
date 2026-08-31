"""Streamlit natural-language-to-SQL app. Thin composition of
ai/text_to_sql/*.py: generation, guardrail validation, and execution are
each imported, never re-implemented here. Run with `make text-to-sql` or
`streamlit run ai/apps/text_to_sql_app.py`."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from ai.common.config import load_settings
from ai.common.llm_client import get_client
from ai.common.snowflake_client import get_ai_readonly_connection
from ai.text_to_sql.executor import run_query
from ai.text_to_sql.generator import generate_sql
from ai.text_to_sql.guardrails import GuardrailViolation, validate_and_prepare
from ai.text_to_sql.schema_registry import SchemaRegistry

EXAMPLE_QUESTIONS = [
    "Top 10 cities by GMV",
    "Which cuisine has the most orders?",
    "Average delivery time by city, worst first?",
    "Cancellation rate by restaurant, highest first",
]

st.title("Chat with your Delivery Data")
st.caption("Ask in English. The LLM writes SQL against SEMANTIC views only, see docs/architecture/04-ai-architecture.md.")

with st.sidebar:
    st.header("Example Questions")
    for q in EXAMPLE_QUESTIONS:
        st.markdown(f"- {q}")
    st.divider()
    st.caption("Guardrails: SELECT-only · SEMANTIC schema only · row limit · query timeout · AI_READONLY_ROLE (no write privileges anywhere). See ADR-006.")

settings = load_settings()
client = get_client(settings)
registry = SchemaRegistry()

question = st.text_input("Enter your question here", placeholder="Top 10 restaurants by revenue in Auckland")

if question:
    candidate_sql = generate_sql(client, settings.ai_chat_model, question, registry, settings.text_to_sql_row_limit)
    st.code(candidate_sql, language="sql")

    try:
        validated = validate_and_prepare(
            candidate_sql, registry.allowed_tables, registry.schema, settings.text_to_sql_row_limit
        )
    except GuardrailViolation as exc:
        st.error(f"The generated SQL was rejected by guardrails: {exc}")
    else:
        try:
            connection = get_ai_readonly_connection(settings)
            df: pd.DataFrame = run_query(connection, validated)
            connection.close()

            st.success(f"{len(df)} rows returned")
            st.dataframe(df, hide_index=True)

            if len(df.columns) == 2 and pd.api.types.is_numeric_dtype(df.iloc[:, 1]):
                st.bar_chart(df, x=df.columns[0], y=df.columns[1])
        except Exception as exc:  # noqa: BLE001 - shown to the user rather than swallowed
            st.error(f"Error running query: {exc}")
