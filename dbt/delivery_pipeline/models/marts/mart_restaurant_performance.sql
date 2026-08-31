-- Grain: one row per restaurant. Adds cancel_rate via the shared macro.
-- The text-to-SQL prompt already assumed this column existed here, so
-- this closes that gap instead of leaving the AI layer pointing at a
-- column that didn't exist.
select
    f.restaurant_id,
    r.restaurant_name,
    r.city,
    r.cuisine,
    count(*)                                      as orders,
    {{ gross_merchandise_value_expr(amount_col='f.sales_amount', is_delivered_col='f.is_delivered') }} as revenue,
    round(avg(f.customer_rating), 2)                as avg_customer_rating,
    round(avg(f.delivery_time_min), 1)                as avg_delivery_min,
    {{ cancellation_rate_expr(status_col='f.order_status') }} as cancel_rate
from {{ ref('fact_orders') }} f
left join {{ ref('dim_restaurants') }} r using (restaurant_id)
group by 1, 2, 3, 4
