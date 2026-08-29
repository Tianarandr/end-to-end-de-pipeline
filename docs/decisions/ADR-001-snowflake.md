# ADR-001: Use Snowflake as the warehouse

## Status
Accepted

## Context
The platform needs a place to run SQL transformations at scale, enforce
schema and access control, and serve both BI-style aggregate queries and
ad-hoc LLM-generated queries, without the team operating cluster
infrastructure themselves.

## Decision
Use Snowflake as the single warehouse for RAW/STAGING/MARTS/SEMANTIC/AI.

## Why
- **Separation of storage and compute**, with per-workload warehouses and
  auto-suspend: the AI enrichment job, the nightly dbt build, and an
  analyst's ad-hoc query don't contend for the same compute, and idle
  compute costs ~$0.
- **Role-based access control down to the schema/view level** is exactly
  the primitive the [security model](../architecture/05-security.md) is
  built on (`AI_READONLY_ROLE` scoped to `SELECT` on `SEMANTIC` only).
  This is *the* mechanism that makes "AI never touches raw data" enforceable
  rather than just documented.
- **Zero operational burden**: no cluster sizing, no compaction/vacuuming,
  no query engine tuning. For a small data team, engineer-hours saved here
  are worth more than the per-credit cost difference against a
  self-managed alternative.
- **First-class `COPY INTO` + external stages** make the S3 landing zone
  pattern (see [ADR-004](ADR-004-s3-landing-zone.md)) a few lines of SQL,
  not custom ETL code.
- Native `dbt-snowflake` adapter support, so nothing here is exotic.

## Alternatives considered

| Option | Why not (for *this* project, at *this* scale) |
|---|---|
| Lakehouse (Iceberg/Delta on S3 + a query engine) | Real advantages at very large scale or multi-engine access patterns, but adds file-compaction/table-maintenance operational burden this team doesn't need yet, for no benefit at this data volume. |
| BigQuery / Redshift | Comparable capability class; Snowflake was chosen for its storage/compute separation and cross-cloud portability, but this is a "any of the three would work" decision, not a Snowflake-specific requirement. |
| Postgres | No, once concurrent BI + AI + dbt workloads and semi-structured `COPY INTO` ingestion are in the picture. Postgres would work as an OLTP store, not as this system's analytical warehouse. |

## Consequences
- Snowflake credit cost scales with compute usage; the `AUTO_SUSPEND=60`
  setting on `DELIVERY_WH` (see `snowflake/00_setup.sql`) keeps idle cost near
  zero, which matters more than warehouse size at this scale.
- The platform is not portable to a different SQL engine without touching
  Snowflake-specific SQL (`TRY_TO_DECIMAL`, `QUALIFY`, `MERGE`
  semantics) in a handful of dbt models. That's an acceptable trade-off made
  with eyes open, not an accident.
