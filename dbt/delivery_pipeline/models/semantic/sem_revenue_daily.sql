-- Thin, documented pass-through of mart_daily_city_revenue. Not
-- re-deriving GMV/cancel_rate/AOV here, on purpose: per ADR-005, the
-- semantic layer's job is to be the one place consumers are granted
-- access to, not another place metric logic lives.
select
    order_date,
    city,
    orders,
    delivered_orders,
    cancel_rate,
    gross_merchandise_value,
    average_order_value
from {{ ref('mart_daily_city_revenue') }}
