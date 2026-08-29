-- The order-grain semantic view. What any BI tool, RAG, or text-to-SQL
-- query about an individual order should read instead of MARTS.FACT_ORDERS
-- directly. AI_READONLY_ROLE is granted SELECT on SEMANTIC only, see
-- docs/architecture/05-security.md and ADR-006.
select
    o.order_id,
    o.order_timestamp,
    o.order_date,
    o.customer_id,
    c.age_segment,
    o.restaurant_id,
    o.city,
    o.cuisine,
    o.payment_method,
    o.order_status,
    o.is_delivered,
    o.sales_amount,
    o.discount,
    o.delivery_fee,
    o.gst,
    o.customer_rating,
    o.delivery_time_min
from {{ ref('fact_orders') }} o
left join {{ ref('dim_customer') }} c using (customer_id)
