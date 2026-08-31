"""Loads the two files the text-to-SQL prompt and the guardrails are both
built from: schema_registry.yml (the table/column allowlist) and
dbt/delivery_pipeline/metrics/metrics.yml (the canonical metric dictionary,
see ADR-005). The prompt is generated from the same file a human reading
the semantic layer's docs would read, so there's no hand-maintained copy
that can drift out of sync.
"""
from __future__ import annotations

from pathlib import Path

import yaml

_THIS_DIR = Path(__file__).parent
DEFAULT_SCHEMA_REGISTRY_PATH = _THIS_DIR / "schema_registry.yml"
DEFAULT_METRICS_PATH = _THIS_DIR.parent.parent / "dbt" / "delivery_pipeline" / "metrics" / "metrics.yml"


class SchemaRegistry:
    def __init__(self, schema_registry_path: Path = DEFAULT_SCHEMA_REGISTRY_PATH, metrics_path: Path = DEFAULT_METRICS_PATH) -> None:
        registry = yaml.safe_load(schema_registry_path.read_text())
        self.schema: str = registry["schema"]
        self.views: dict[str, dict] = registry["views"]
        metrics_doc = yaml.safe_load(metrics_path.read_text())
        self.metrics: list[dict] = metrics_doc["metrics"]

    @property
    def allowed_tables(self) -> set[str]:
        """Fully-qualified `SCHEMA.VIEW` names guardrails.py checks generated SQL against."""
        return {f"{self.schema}.{view}" for view in self.views}

    def render_schema_for_prompt(self) -> str:
        lines = [f"Tables available (Snowflake schema `{self.schema}`). Use bare view names, no database/schema prefix.", ""]
        for view, spec in self.views.items():
            cols = ", ".join(spec["columns"])
            lines.append(f"{view}({cols})  -- {spec['description']}")
        return "\n".join(lines)

    def render_metrics_for_prompt(self) -> str:
        lines = ["Canonical metric definitions: use these names and the view they say to query; never re-derive a metric from raw columns if a semantic view already computes it:", ""]
        for m in self.metrics:
            aliases = f" (aka {', '.join(m['aliases'])})" if m.get("aliases") else ""
            view = m.get("semantic_view", "n/a")
            lines.append(f"- {m['name']}{aliases}: {m['description']} [{view}]")
        return "\n".join(lines)
