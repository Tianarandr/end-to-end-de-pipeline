select
    restaurant_id,
    restaurant_name,
    city,
    cuisine,
    orders,
    revenue,
    avg_customer_rating,
    avg_delivery_min,
    cancel_rate
from {{ ref('mart_restaurant_performance') }}
