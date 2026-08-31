# ADR-006: AI sits above governed data, never beside it

## Status
Accepted

## Context
The original `text_to_sql.py` connected to Snowflake with a role that
(per the setup scripts) had broad grants, and defended itself purely with a
client-side keyword blocklist. The RAG app read directly from `STAGING`.
Neither AI capability was constrained by the warehouse's own access
control, only by the correctness of hand-written Python string checks.

## Decision
Every AI capability reads exclusively from `SEMANTIC` (enrichment's writer
path reads `STAGING` and writes only to `AI`) under a role
(`AI_READONLY_ROLE` / `AI_ENRICH_ROLE`) that has no grants outside that
boundary. See [05-security.md](../architecture/05-security.md).

## Why
- **Defense in depth, with the database as the real enforcement point.**
  Application-level validation (`ai/text_to_sql/guardrails.py`) catches bad
  queries early and gives a clear error message, but the guarantee that
  matters, that the LLM cannot read `RAW.USERS.PASSWORD` or write anywhere,
  comes from the Snowflake grant, which no prompt-injection or validator
  bug can bypass.
- **AI answers inherit the same trust as BI answers.** Because AI reads the
  same `SEMANTIC` views and the same metric definitions
  ([ADR-005](ADR-005-semantic-layer.md)) as any dashboard, "what did the AI
  say GMV was" and "what does the dashboard say GMV was" can never disagree
  due to the AI having a different/looser view of the data.
- **Unenriched or in-flight data never leaks into an AI answer.** `RAW` can
  contain partially-loaded batches, and `STAGING` can contain rows that
  haven't passed the [data-quality gate](../architecture/07-data-quality.md)
  yet; `SEMANTIC` is only populated after `data_quality` and
  `semantic_validation` pass, so the AI layer only ever sees data that
  already cleared the pipeline's own quality bar.

## Alternatives considered

| Option | Why not |
|---|---|
| Give AI direct access to `MARTS`/`RAW` with only client-side query validation | This is the original design's actual risk: a validator is code, and code has bugs; a grant is a database-enforced boundary. |
| A separate AI-only replica/warehouse | Real option at much larger scale for compute isolation, but adds infrastructure this project's query volume doesn't justify; a role-scoped grant achieves the access-control goal without the extra warehouse. |

## Consequences
- Any new AI capability must be built against `SEMANTIC`, which means any
  data it needs must first be modeled there. That's a speed bump on
  purpose: it keeps the AI layer from becoming an ungoverned second path
  into the warehouse.
