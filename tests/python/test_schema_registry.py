"""The text-to-SQL prompt/allowlist is built from schema_registry.yml and
dbt/delivery_pipeline/metrics/metrics.yml. This test catches the two files
drifting apart (e.g. a metric pointing at a semantic view that isn't in the
allowlist)."""
from __future__ import annotations

from ai.text_to_sql.schema_registry import SchemaRegistry


def test_registry_loads_expected_views():
    registry = SchemaRegistry()
    assert registry.schema == "SEMANTIC"
    assert "SEMANTIC.SEM_ORDERS" in registry.allowed_tables
    assert "SEMANTIC.SEM_REVENUE_DAILY" in registry.allowed_tables


def test_every_metric_semantic_view_is_on_the_allowlist():
    registry = SchemaRegistry()
    for metric in registry.metrics:
        view = metric.get("semantic_view")
        if view is None:
            continue  # e.g. review_sentiment, sourced from AI/MARTS rather than SEMANTIC (documented as such)
        assert view in registry.allowed_tables, f"metric '{metric['name']}' references {view}, which is not in schema_registry.yml"


def test_prompt_rendering_includes_every_view_and_metric():
    registry = SchemaRegistry()
    schema_text = registry.render_schema_for_prompt()
    for view in registry.views:
        assert view in schema_text

    metrics_text = registry.render_metrics_for_prompt()
    for metric in registry.metrics:
        assert metric["name"] in metrics_text
