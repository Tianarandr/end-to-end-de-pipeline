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
| ClickHouse | See below: a real contender on raw query speed and cost at scale, turned down for what it would cost this project specifically. |

### Why not ClickHouse specifically

ClickHouse comes up in this comparison more than the others because it's a
genuinely strong warehouse, not a straw man: sub-second aggregate queries
over billions of rows, excellent price/performance at high query volume,
and it's a fine choice for a lot of analytical workloads. It was turned
down here for three reasons specific to what this platform actually needs:

1. **RBAC granularity is the thing this platform is built on, and
   ClickHouse's isn't there.** The whole AI-governance story
   ([ADR-006](ADR-006-ai-above-governed-data.md),
   [05-security.md](../architecture/05-security.md)) rests on
   `AI_READONLY_ROLE` having `SELECT` on `SEMANTIC` and nothing else,
   enforced by the warehouse itself, not by application code remembering
   to filter. Snowflake's role hierarchy with schema/view-level grants
   makes that a few lines of DDL. ClickHouse's access control (SQL-driven
   RBAC since ~22.x) covers table/column grants but is materially less
   mature for this exact "four least-privilege roles, one of them
   AI-facing" pattern; building the same guarantee would mean leaning more
   on application-level enforcement, which is precisely the weaker,
   easier-to-get-wrong version of this control this project is trying to
   avoid.
2. **This is a batch analytical workload, not the workload ClickHouse is
   built to be fastest at.** ClickHouse's advantage is largest at high
   query concurrency and near-real-time ingestion, e.g. dashboards being
   hammered by hundreds of concurrent users, or data landing continuously.
   This platform runs one dbt build a day and serves a handful of
   interactive text-to-SQL/RAG users; Snowflake's per-workload warehouses
   with auto-suspend already make idle compute cost ~$0 at that usage
   pattern, so ClickHouse's query-speed advantage isn't a cost or latency
   problem this project has today.
3. **Self-managed operational cost outweighs the license-cost savings at
   this scale.** ClickHouse Cloud narrows this gap, but self-hosted
   ClickHouse (replication, sharding, `ReplacingMergeTree`/merge
   tuning, upgrades) is real operational work a small team would be taking
   on for a performance ceiling this project isn't close to hitting. The
   "[zero operational burden](#why)" point above is a deliberate trade of
   some raw performance headroom for engineer-hours, and that trade
   favors Snowflake at this team size.

**Revisit when:** query volume or concurrency grows to where Snowflake
credit cost at that scale genuinely exceeds a self-managed or
ClickHouse-Cloud alternative's total cost (compute *and* the
engineer-hours to operate it), or when a real sub-second/high-concurrency
serving requirement appears that auto-suspend warehouses can't meet
economically. Until then this is a scale-appropriateness call, not a
capability gap.

## Consequences
- Snowflake credit cost scales with compute usage; the `AUTO_SUSPEND=60`
  setting on `DELIVERY_WH` (see `snowflake/00_setup.sql`) keeps idle cost near
  zero, which matters more than warehouse size at this scale.
- The platform is not portable to a different SQL engine without touching
  Snowflake-specific SQL (`TRY_TO_DECIMAL`, `QUALIFY`, `MERGE`
  semantics) in a handful of dbt models. That's an acceptable trade-off made
  with eyes open, not an accident.
