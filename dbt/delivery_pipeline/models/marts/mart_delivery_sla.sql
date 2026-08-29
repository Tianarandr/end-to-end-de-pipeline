-- Grain: one row per (city, order_hour), delivered orders only. Adds
-- late_rate via the shared SLA-threshold macro (dbt_project.yml `vars`).
-- The text-to-SQL prompt already assumed this column existed here; same
-- fix as mart_restaurant_performance.
select
    city,
    hour(order_timestamp)                          as order_hour,
    {{ delivered_orders_expr() }}                     as delivered_orders,
    round(median(delivery_time_min), 1)                 as p50_delivery_min,
    round(percentile_cont(0.9) within group (order by delivery_time_min), 1) as p90_delivery_min,
    {{ late_delivery_rate_expr() }}                        as late_rate
from {{ ref('fact_orders') }}
where is_delivered
group by 1, 2
