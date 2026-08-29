-- Grain: one row per (order_date, city). Every measure calls the shared
-- macro definitions in macros/metrics.sql. See ADR-005.
select
    order_date,
    city,
    count(*)                                     as orders,
    {{ delivered_orders_expr() }}                   as delivered_orders,
    {{ cancellation_rate_expr() }}                     as cancel_rate,
    {{ gross_merchandise_value_expr() }}                 as gross_merchandise_value,
    {{ average_order_value_expr() }}                       as average_order_value
from {{ ref('fact_orders') }}
group by 1, 2
