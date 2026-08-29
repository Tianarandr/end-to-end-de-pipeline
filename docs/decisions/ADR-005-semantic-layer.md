# ADR-005: Introduce a lightweight, dbt-native semantic layer

## Status
Accepted

## Context
The original pipeline had BI-shaped marts (`mart_daily_city_revenue`, etc.)
and a text-to-SQL app that each *independently* encoded what "GMV" or
"cancellation rate" means (one in dbt SQL, one in a Streamlit prompt's
`SCHEMA` string). Two definitions of the same metric, maintained by hand in
two places, will diverge. And when the AI layer starts answering business
questions too, a third independent definition is the natural next mistake.

## Decision
Introduce a `SEMANTIC` schema: curated, documented dbt views over `MARTS`,
plus a structured `metrics.yml` metric dictionary. Every consumer that
answers a metric-shaped question (BI, RAG, text-to-SQL, any future agent)
reads from `SEMANTIC` and is prompted/documented using `metrics.yml`'s
exact name and SQL, never re-deriving it.

## Why dbt-native instead of a dedicated product
A dedicated semantic-layer product (dbt Semantic Layer/MetricFlow, Cube,
LookML, etc.) would add a query-planning service, a new deployment target,
and a new modeling language for a project with roughly a dozen metrics and
one AI consumer that needs them. That's infrastructure sized for an
organization with many BI tools and many metric consumers competing for a
single governed query interface. Not this one.

What actually solves the stated problem (one definition, reused everywhere)
is:
1. `macros/metrics.sql`: the SQL expression for each metric, defined once.
2. `models/semantic/*.sql`: thin views built from those macros, granted to
   `AI_READONLY_ROLE` and nothing else outside the warehouse's normal BI
   access.
3. `models/semantic/metrics.yml`: a name → description → owning
   view/macro → SQL dictionary, consumed programmatically by
   `ai/text_to_sql/schema_registry.py` to build the LLM's prompt.

This is dbt's own modeling, testing, and documentation machinery, reused:
no new technology, no new operational surface, and any future BI or AI tool
can fully introspect it because it's just views and YAML.

## Alternatives considered

| Option | Why not (yet) |
|---|---|
| dbt Semantic Layer (MetricFlow) | Real value once there are multiple BI tools needing a shared query interface with dynamic dimensional slicing; at ~12 metrics and one programmatic consumer, the YAML dictionary + curated views deliver the same governance with none of the added service. |
| Cube / LookML / a standalone metrics service | Same reasoning: justified at a metric/consumer count this project doesn't have. Revisit if/when a second BI tool or a self-serve dashboard builder needs to query metrics dynamically rather than through fixed dbt views. |
| No semantic layer; let each consumer read `MARTS` directly | This is the status quo the ADR exists to fix. It's how the original repo ended up with metric logic duplicated between dbt and the text-to-SQL prompt. |

## Consequences
- One more schema and one more dbt layer to build and test: a small,
  bounded cost against the alternative of metric definitions drifting
  between dashboards and AI answers.
- If metric complexity grows substantially (many dimensions, multiple BI
  tools needing ad-hoc slicing, need for a query API rather than fixed
  views), migrating `metrics.yml`'s definitions into a dedicated semantic
  layer product is a natural, contained next step. The metric dictionary
  this ADR introduces is exactly the artifact that migration would start
  from.
