# 07: Data Quality Strategy

## Test taxonomy: blocking vs. warning vs. informational

Not every failed check should stop the pipeline, but some absolutely must.
Severity is set explicitly per test via dbt's `config(severity=...)`, and
documented here so "is this blocking?" is never a guess:

| Severity | Behavior | Used for |
|---|---|---|
| **Blocking** (`severity: error`, dbt default) | `dbt build`/`dbt test` exits non-zero → the Airflow `data_quality` task fails → the DAG **stops before `gold_models`/`ai_enrichment`/`publish`** | Primary key `unique`/`not_null` on every staging and mart model; `relationships` (referential integrity, e.g. `fact_orders.customer_id → dim_customer`); `accepted_values` on `order_status`; source freshness beyond `error_after`. |
| **Warning** (`severity: warn`) | Logged, visible in `dbt build` output and `PIPELINE_RUNS.dq_status='warned'`, does **not** stop the DAG | Freshness beyond `warn_after` but under `error_after`; soft business-rule checks (e.g. `delivery_time_min` outside a plausible range) where a bad value is worth flagging but not worth halting revenue reporting over. |
| **Informational** | dbt docs / column descriptions only, no test | Anything documented for human understanding but not (yet) worth automated enforcement. |

The full list of which test is which severity lives next to the model in
`dbt/delivery_pipeline/models/**/_*.yml` (grep for `severity`), and is
summarized per dataset in [docs/data_contracts/](../data_contracts/).

## Where quality gates sit in the pipeline

```
dbt_staging  →  data_quality (BLOCKING)  →  gold_models  →  semantic_validation (BLOCKING)  →  ai_enrichment
```

This fixes a real gap in the original DAG: it ran
`dbt build --exclude tag:ai` (which *includes* tests, so a failure did stop
the DAG), but there was no separate, visible quality gate. A test failure
and a compile error looked the same in the Airflow UI, with no distinction
between "warn, but keep going" and "stop everything." Splitting
`data_quality` into its own Airflow task group makes the gate explicit and
its pass/warn/fail status queryable from `PIPELINE_RUNS.dq_status`.

## What's tested

- **Sources** (`_sources.yml`): freshness (`loaded_at_field: _ingested_at`,
  `warn_after`/`error_after`) on every `RAW` source table.
- **Staging**: `unique` + `not_null` on every primary key; `not_null` on
  every foreign key used downstream.
- **Marts**: `unique`/`not_null` on fact/dimension primary keys,
  `relationships` from every fact's foreign keys to its dimension,
  `accepted_values` on enumerated business columns (`order_status`).
- **Semantic**: the semantic views are tested for row-count parity against
  their underlying mart (a semantic view must not silently drop rows) and
  for the presence of every column `metrics.yml` claims exists.
- **AI**: `ai_quality_checks` (an Airflow task, not a dbt test, since this
  needs Python) asserts the enrichment batch's failure rate is under a
  threshold and that every `SUCCEEDED` row has a non-null `sentiment_label`
  in the allowed set; a batch that fails this check does not proceed to
  `publish`.

## Data contracts as the "why"

dbt tests are the *enforcement mechanism*; [data contracts](../data_contracts/)
are the *documentation* of what's promised and to whom, so a consumer
(another team, a dashboard, the AI layer) can find, in one file, what
they're allowed to assume about a dataset without reading the dbt YAML.
