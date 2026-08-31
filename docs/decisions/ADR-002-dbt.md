# ADR-002: Use dbt for transformation

## Status
Accepted

## Context
Business logic (staging cleanup, star schema, marts, semantic views) needs
to be version-controlled, tested, documented, and reusable, not scattered
across ad-hoc SQL scripts or embedded in orchestration code.

## Decision
Use dbt (`dbt-core` + `dbt-snowflake`) for every SQL transformation from
`RAW` through `SEMANTIC`.

## Why
- **Tests as code**: `unique`, `not_null`, `relationships`,
  `accepted_values`, and custom tests live next to the model they test and
  run as part of the same build. This is the entire mechanism behind
  [07-data-quality.md](../architecture/07-data-quality.md).
- **Documentation as code**: model/column descriptions, owners, and grain
  live in the same YAML as the tests, so docs can't drift silently out of
  sync the way a separate wiki page does.
- **Macros give business logic exactly one home.** `macros/metrics.sql`
  defines GMV/cancellation-rate/AOV once; every mart and semantic view
  calls it. This is what closes the original repo's biggest correctness
  risk (the same aggregate expression copy-pasted across three marts).
- **Incremental models with `merge`** (`fact_orders`, `fact_order_items`)
  give idempotent, efficient re-runs without hand-written upsert logic.
- **`ref()`/`source()`** builds an explicit DAG and lineage graph for free:
  this *is* the project's column/model-level lineage tool, so no separate
  lineage product was needed (see [ADR-007](ADR-007-no-kafka-spark-k8s.md)).
- Selectors (`--select`, `--exclude`, `tag:ai`) let Airflow orchestrate at
  the *stage* level (staging / marts / semantic / ai-tagged) without any
  dbt-internal logic leaking into the DAG file.

## Alternatives considered

| Option | Why not |
|---|---|
| Hand-written SQL scripts run by Airflow | No tests, no docs, no lineage, no dependency graph. This is exactly what the original repo's `snowflake_queries/*.sql` were; the redesign keeps only the one-time setup DDL there and moves all recurring transformation logic into dbt. |
| A Python transformation framework (e.g. pandas/Polars pipelines) | Pulls data out of the warehouse to transform it in application memory, throwing away Snowflake's compute; there's no benefit here since every transformation is expressible in SQL. |
| Dedicated semantic-layer product on top of dbt (dbt Semantic Layer/Cube/etc.) | See [ADR-005](ADR-005-semantic-layer.md): dbt's own modeling + docs + YAML is sufficient at this metric count. |

## Consequences
- The team needs SQL + Jinja fluency; this is a reasonable bar for a data
  engineering team and lower than requiring a general-purpose language
  framework.
- dbt Cloud is not used. `dbt-core` run by Airflow/CI keeps the stack
  self-hosted and avoids a recurring SaaS cost the project doesn't need at
  this scale.
