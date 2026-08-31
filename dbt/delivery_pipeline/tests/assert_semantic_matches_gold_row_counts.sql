-- Singular test: a semantic view must never silently drop rows relative to
-- the gold mart it wraps (docs/architecture/07-data-quality.md#whats-tested).
-- dbt singular tests fail the build (blocking) if this returns any rows.

with gold as (
    select count(*) as n from {{ ref('mart_daily_city_revenue') }}
),
semantic as (
    select count(*) as n from {{ ref('sem_revenue_daily') }}
)

select gold.n as gold_row_count, semantic.n as semantic_row_count
from gold, semantic
where gold.n != semantic.n
