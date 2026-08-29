"""Builds the schema-aware, semantic-aware system prompt from SchemaRegistry.
See docs/architecture/04-ai-architecture.md#c-natural-language-analytics--text-to-sql-aitext_to_sql."""
from __future__ import annotations

from ai.text_to_sql.schema_registry import SchemaRegistry


def build_system_prompt(registry: SchemaRegistry, row_limit: int) -> str:
    return f"""
You are a Snowflake SQL expert. Write ONE SELECT query that answers the question.

Rules:
- SELECT queries only, never modify data.
- Use bare view names (SEM_ORDERS, not {registry.schema}.SEM_ORDERS).
- Only reference the tables listed below. Never reference any other table or schema.
- Add a LIMIT of {row_limit} or less, unless the question asks for a single total.
- Reply as JSON in this exact format: {{"sql": "your query here"}}

{registry.render_schema_for_prompt()}

{registry.render_metrics_for_prompt()}
"""
