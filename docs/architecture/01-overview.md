# 01: Architecture Overview

## Business problem

A food-delivery marketplace (orders, restaurants, customers, reviews) needs:

1. Trustworthy, governed numbers for revenue, cancellations, delivery SLA, and
   restaurant performance that finance, ops, and product all agree on.
2. A way to turn a growing pile of free-text customer reviews into structured
   signal (sentiment, topic, recurring issues) without a team of analysts
   manually tagging them.
3. Self-serve analytics for non-SQL stakeholders ("what were our top 10 cities
   by GMV last month?") without opening every question as a data-team ticket.
4. All of the above built by a small team, on a small budget, without betting
   the platform on infrastructure sized for a company 100x this one's scale.

This repository is a reference implementation of that platform, scoped to
what a **2-5 person data team supporting tens of millions of rows** would
actually run in production in 2026, not a simulation of a FAANG-scale data
platform.

## Architectural goals

- **One source of truth for business logic.** A metric defined once, reused
  by dashboards, AI agents, and text-to-SQL alike.
- **Governed AI.** LLMs read curated, tested data, never raw tables, and
  write through auditable, idempotent, retryable pipelines.
- **Traceable data.** Every row in the warehouse can be traced back to a
  source file, a batch, and a point in time.
- **Fail loud, fail early.** A broken upstream contract blocks downstream
  publication instead of quietly corrupting a dashboard three layers down.
- **Boring technology, used well.** Every component earns its place against
  the problem it solves at this scale. See
  [ADR-007](../decisions/ADR-007-no-kafka-spark-k8s.md) for what got left out
  and why.
- **Understandable in 10 minutes.** A new data engineer should be able to
  read this repo's `README.md` and know where to make a change.

## Logical layers

```
DATA SOURCES
     │
     ▼
INGESTION / LANDING        ← immutable landing, control-table metadata, idempotent load
     │
     ▼
BRONZE / RAW                ← verbatim source shape + technical metadata columns
     │
     ▼
SILVER / STAGING            ← typed, deduplicated, standardized, one row per business key
     │
     ▼
GOLD / BUSINESS DATA        ← star schema (facts + dimensions) + business marts
     │
     ▼
SEMANTIC LAYER               ← canonical, documented metric definitions & curated views
     │
     ├──────────────┐
     ▼              ▼
 AI / ML        BI / ANALYTICS
     │
     ▼
AI APPLICATIONS
(RAG, Text-to-SQL, future agents)
```

Cross-cutting, applied at every layer instead of bolted on at the end:
**Security · Governance · Data Quality · Lineage · Observability · CI/CD.**

## How the layers fit together

Each arrow above is a contract, not just a data hop:

| Boundary | Contract |
|---|---|
| Sources → Ingestion | The loader owns idempotency and metadata; sources own nothing about how they're loaded. |
| Ingestion → Bronze | Bronze is byte-faithful to the source plus `_ingested_at` / `_source_file` / `_batch_id` / `_record_hash`. No business logic. |
| Bronze → Silver | Silver is the first layer safe to `SELECT *` from: typed, deduplicated, one row per grain. |
| Silver → Gold | Gold encodes business logic exactly once (via dbt macros), never duplicated across marts. |
| Gold → Semantic | The semantic layer is the only place AI and BI are allowed to read from for anything metric-shaped. |
| Semantic → AI/BI | Consumers never invent a metric definition; they call it by name. |

See [02-data-flow.md](02-data-flow.md) for the physical implementation of
this flow, [03-data-model.md](03-data-model.md) for the schema, and
[04-ai-architecture.md](04-ai-architecture.md) for how AI plugs into this
without becoming a second, ungoverned analytics stack.

## Non-goals

This is **not**:

- A streaming platform. Nothing here needs sub-minute freshness; see
  [ADR-007](../decisions/ADR-007-no-kafka-spark-k8s.md).
- A multi-tenant, multi-region enterprise data platform.
- A demonstration of every trendy tool in the modern data stack. Every
  addition earns its place against a concrete problem it solves (see each
  ADR's "what we didn't do" section).
