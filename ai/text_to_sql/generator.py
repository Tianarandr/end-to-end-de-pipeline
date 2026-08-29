"""Calls the LLM to turn a question into a candidate SQL string. It only
produces a candidate; guardrails.py decides whether it's ever executed."""
from __future__ import annotations

import json

from openai import OpenAI

from ai.text_to_sql.prompt import build_system_prompt
from ai.text_to_sql.schema_registry import SchemaRegistry


def generate_sql(client: OpenAI, model: str, question: str, registry: SchemaRegistry, row_limit: int) -> str:
    response = client.chat.completions.create(
        model=model,
        temperature=0,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": build_system_prompt(registry, row_limit)},
            {"role": "user", "content": question},
        ],
    )
    payload = json.loads(response.choices[0].message.content)
    return payload["sql"].strip().rstrip(";")
