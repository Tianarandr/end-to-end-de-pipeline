select
    city,
    order_hour,
    delivered_orders,
    p50_delivery_min,
    p90_delivery_min,
    late_rate
from {{ ref('mart_delivery_sla') }}
