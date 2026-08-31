-- Grain: one row per restaurant_id.
select
    restaurant_id,
    restaurant_name,
    city,
    rating,
    rating_count,
    cost_for_two,
    cuisine
from {{ ref('stg_restaurants') }}
