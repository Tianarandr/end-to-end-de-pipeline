# 03: Data Model

## Bronze (`RAW` schema)

Purpose: **an exact, replayable copy of the source, plus load metadata.**
No business transformation happens here, not even a `TRIM()`. If a value is
garbage in the source, it's garbage in `RAW`; staging's job is to decide what
to do about that.

Every `RAW` table carries four technical columns, stamped by the loader, not
by dbt:

| Column | Purpose |
|---|---|
| `_ingested_at` | `TIMESTAMP_LTZ`, when the loader wrote this row. |
| `_source_file` | The S3 object key the row came from (`METADATA$FILENAME`). |
| `_batch_id` | The ingestion `run_id` (UUID), joins to `INGESTION_RUNS`. |
| `_record_hash` | `MD5` of the row's raw column values, a cheap way to catch duplicates or changes without re-parsing business columns. |

See [snowflake/02_bronze_tables.sql](../../snowflake/02_bronze_tables.sql).

## Silver (`STAGING` schema, dbt views)

Purpose: **one clean, typed row per business key.** Responsibilities:
type casting, deduplication (`QUALIFY ROW_NUMBER()` on the natural key,
newest `_ingested_at` wins), standardization (e.g. city parsed out of a
free-text address), and source-safe derivations (`is_delivered`). No
cross-entity business logic here (that's Gold's job): `stg_orders` computes
`is_delivered` from `order_status` on the *same row*, but doesn't compute
GMV, which requires a business rule about which orders count.

Every staging model has a grain, a description, column descriptions, an
owner, and `not_null` / `unique` tests on its primary key. See
`dbt/delivery_pipeline/models/staging/_staging.yml`.

## Gold (`MARTS` schema)

### Facts

| Model | Grain | Primary key | Foreign keys | Key measures |
|---|---|---|---|---|
| `fact_orders` | 1 row per order | `order_id` | `customer_id → dim_customer`, `restaurant_id → dim_restaurants` | `sales_amount`, `discount`, `delivery_fee`, `gst`, `delivery_time_min` |
| `fact_order_items` | 1 row per order line | `order_item_id` | `order_id → fact_orders`, `restaurant_id → dim_restaurants`, `f_id → dim_food` | `price`, `quantity`, `line_amount` |

### Dimensions

| Model | Grain | Primary key |
|---|---|---|
| `dim_customer` | 1 row per customer | `customer_id` |
| `dim_restaurants` | 1 row per restaurant | `restaurant_id` |
| `dim_food` | 1 row per food item | `f_id` |
| `dim_date` | 1 row per calendar day | `date_day` |

### Business marts

`mart_daily_city_revenue`, `mart_restaurant_performance`,
`mart_delivery_sla`, `mart_review_insights` (AI-tagged, blends `SEMANTIC`
with `AI.REVIEW_ENRICHED`).

**Single source of truth for business logic:** GMV, cancellation rate,
average order value, and "is this a completed/delivered order" are each
defined **once**, in `dbt/delivery_pipeline/macros/metrics.sql`, and every
mart and semantic view calls the macro instead of re-deriving the
expression. That fixes the original repo's biggest scaling risk: the same
`SUM(iff(is_delivered, sales_amount, 0))` pattern was copy-pasted across
three marts, one edit away from silently diverging.

## Semantic Layer (`SEMANTIC` schema)

See [ADR-005](../decisions/ADR-005-semantic-layer.md) for why this layer
exists and why it's dbt-native rather than a dedicated semantic-layer
product. It contains:

- **Curated, documented views** (`sem_orders`, `sem_revenue_daily`,
  `sem_restaurant_performance`, `sem_reviews`): thin, `SELECT`-only wrappers
  over Gold that the AI layer and BI tools are actually granted access to
  (`AI_READONLY_ROLE` has `SELECT` on `SEMANTIC` only, see
  [05-security.md](05-security.md)).
- **`metrics.yml`**: a structured, versioned dictionary of canonical
  business metrics (revenue, GMV, completed orders, cancellation rate,
  average order value, delivery SLA, customer count), each with a name,
  description, owning mart/macro, and the exact SQL expression that
  computes it. This is the artifact the text-to-SQL prompt and any future
  BI tool are built from. See
  [ai/text_to_sql/schema_registry.yml](../../ai/text_to_sql/schema_registry.yml).

## AI (`AI` schema)

| Table | Purpose |
|---|---|
| `REVIEW_ENRICHED` | One row per successfully enriched review: `sentiment_label`, `sentiment_score`, `topic`, `key_issue`, plus `model_name`, `model_version`, `prompt_version`, `processed_at`. |
| `ENRICHMENT_LOG` | One row per **attempt** (success or failure): `review_id`, `batch_id`, `status`, `error_message`, `attempt_number`, `processed_at`. This is what makes failures visible and reprocessable instead of silently dropped. |

## Data contracts

Machine-readable contracts for the datasets other teams/systems depend on
live in [docs/data_contracts/](../data_contracts/): owner, grain, primary
key, required columns, allowed values, freshness expectation, and which dbt
tests enforce each one.
