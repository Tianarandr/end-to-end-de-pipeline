# 02: Data Flow

## End-to-end flow

```
S3 landing (immutable, partitioned by source/date)
     │  ingestion/ (Python) - one run_id per DAG run, one file-load record per file
     ▼
Snowflake RAW  (Bronze)          - COPY INTO with metadata columns stamped at load time
     │  dbt staging (Silver)      - cast, dedupe, standardize; sources.yml freshness checked
     ▼
Snowflake STAGING (Silver)
     │  dbt marts (Gold)          - star schema + business marts, business logic in macros
     ▼
Snowflake MARTS (Gold)
     │  dbt semantic views        - curated, documented, metric-named views
     ▼
Snowflake SEMANTIC
     │
     ├─────────────────────────────┐
     ▼                              ▼
AI enrichment (batch)          BI / dashboards / text-to-SQL / RAG
writes to Snowflake AI schema       reads SEMANTIC only, read-only role
     │
     ▼
dbt AI-tagged models (blend SEMANTIC + AI schema, e.g. mart_review_insights)
```

## Run identity and traceability

A single Airflow DAG run generates one `run_id` (UUID). That `run_id`
propagates through every stage as `_batch_id`:

- `INGESTION_RUNS.run_id`: one row per source ingested in that run.
- `RAW.*._batch_id`: every row loaded in that run carries it.
- dbt's own `run_started_at` / invocation metadata is captured in
  `dbt build --vars '{run_id: ...}'` where used, and dbt artifacts
  (`target/run_results.json`) are archived as CI/Airflow logs.
- `AI.REVIEW_ENRICHED.batch_id` and `AI.ENRICHMENT_LOG.batch_id`: which
  enrichment run produced/attempted a given row.
- `PIPELINE_RUNS.run_id`: the final observability record for the whole DAG
  run (see [06-observability.md](06-observability.md)).

So given any row in `MARTS.FACT_ORDERS`, you can answer "which source file,
loaded by which run, on what date, did this come from?" with one join back
through `_batch_id` to `INGESTION_RUNS`.

## Ingestion → Bronze (the part most portfolio pipelines skip)

The original pipeline ran `COPY INTO RAW.<table> FROM @stage/<table>/` with
no record of *which* run loaded *which* file, no protection against loading
the same file twice, and no way to tell whether last night's load actually
happened without opening Snowflake.

The redesigned ingestion (`ingestion/`) wraps that same `COPY INTO`
mechanism (Snowflake's native staged-file load history already prevents
literal duplicate-file reloads, so we don't reinvent that) with:

- A `Source` abstraction (`ingestion/sources/base.py`) so **CSV-on-S3 today,
  an API pull or a database CDC extract tomorrow, look the same to the
  loader.** They all yield `(file_ref, row_count)` and let the loader stamp
  metadata and log the run. See [ADR-004](../decisions/ADR-004-s3-landing-zone.md).
- A `SnowflakeLoader` that stamps `_ingested_at`, `_source_file`,
  `_batch_id`, and `_record_hash` on every row via a `COPY INTO ... FROM
  (SELECT ...)` transformation, and writes one row to `INGESTION_RUNS` per
  source per run with `status`, `row_count`, and `error_message`.
- Idempotency at the *run* level: re-running a DAG run for a date that
  already succeeded is a safe no-op (checked against `INGESTION_RUNS`),
  and at the *file* level via Snowflake's load history + `_record_hash`.

## Silver → Gold: incrementality

`fact_orders` and `fact_order_items` are incremental dbt models
(`merge` on the natural key, watermarked on `order_timestamp`), unchanged
from the original design because it was already correct: it avoids
reprocessing the full order history every run while staying idempotent
(a re-run merges, it doesn't duplicate).

## Gold → Semantic → consumers

The original pipeline was missing this layer entirely. See
[ADR-005](../decisions/ADR-005-semantic-layer.md) and
[03-data-model.md](03-data-model.md#semantic-layer). Every consumer
(Streamlit RAG app, text-to-SQL app, future BI tool) reads from
`SEMANTIC.*`, never from `MARTS.*` or `RAW.*` directly.
