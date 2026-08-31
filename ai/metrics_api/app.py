"""Read-only HTTP API over the semantic layer's canonical metrics
(dbt/delivery_pipeline/metrics/metrics.yml), for callers that want a metric
value without going through the RAG/text-to-SQL chat UIs: a dashboard, a
scheduled report, another service. It's the same reader capability as
ai/text_to_sql/ on a different interface, not a new access path: same
AI_READONLY_ROLE connection (SELECT-only on SEMANTIC, session statement
timeout), same SchemaRegistry allowlist, same row-limit setting. See
docs/architecture/04-ai-architecture.md#e-metrics-api-aimetrics_api.

Deliberately thin: one query shape (`SELECT * FROM <the metric's semantic
view> LIMIT n`), no generic filter/group-by query builder. The semantic
view already has the grain and every column a caller would filter on; a
caller that needs an arbitrary slice can query it directly in Snowflake, or
this gets a filter parameter added when a real caller actually needs one
(see ADR-007 on not building for hypothetical requirements).

Run locally: `pip install -r requirements-metrics-api.txt && uvicorn ai.metrics_api.app:app --port 8000`.
requirements-metrics-api.txt is kept separate from requirements.txt: that
file is also installed alongside Airflow itself in CI/the Airflow image,
and Airflow 3.x pins its own internal fastapi version.
"""
from __future__ import annotations

from fastapi import FastAPI, HTTPException

from ai.common.config import load_settings
from ai.common.snowflake_client import get_ai_readonly_connection
from ai.text_to_sql.schema_registry import SchemaRegistry

app = FastAPI(title="Delivery Metrics API", version="1.0.0")
registry = SchemaRegistry()


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/metrics")
def list_metrics() -> list[dict]:
    return [
        {
            "name": metric["name"],
            "aliases": metric.get("aliases", []),
            "description": " ".join(metric["description"].split()),
            "grain": metric.get("grain", []),
            "semantic_view": metric.get("semantic_view"),
            "owner": metric.get("owner"),
        }
        for metric in registry.metrics
    ]


def _find_metric(name: str) -> dict:
    for metric in registry.metrics:
        if metric["name"] == name or name in metric.get("aliases", []):
            return metric
    raise HTTPException(status_code=404, detail=f"Unknown metric '{name}'. See GET /metrics for the list.")


@app.get("/metrics/{metric_name}")
def get_metric(metric_name: str, limit: int = 100) -> dict:
    metric = _find_metric(metric_name)
    view = metric.get("semantic_view")
    if view is None:
        raise HTTPException(status_code=422, detail=f"Metric '{metric_name}' has no single semantic_view to query directly.")
    if view not in registry.allowed_tables:
        # Defensive, not expected to trip: `view` comes from metrics.yml, a
        # file this service ships with, not from the request.
        raise HTTPException(status_code=422, detail=f"'{view}' is not on the SEMANTIC allowlist.")

    settings = load_settings()
    bounded_limit = max(1, min(limit, settings.text_to_sql_row_limit))
    schema, view_name = view.split(".")

    connection = get_ai_readonly_connection(settings)
    try:
        cursor = connection.cursor()
        cursor.execute(f"SELECT * FROM {schema}.{view_name} LIMIT {bounded_limit}")
        columns = [col[0].lower() for col in cursor.description]
        rows = [dict(zip(columns, row, strict=True)) for row in cursor.fetchall()]
    finally:
        connection.close()

    return {"metric": metric["name"], "semantic_view": view, "row_count": len(rows), "rows": rows}
