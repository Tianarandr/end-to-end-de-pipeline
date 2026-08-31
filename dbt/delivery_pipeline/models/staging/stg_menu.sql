-- Grain: one row per menu_id (a restaurant/food/price combination).
with deduped as (
    select *
    from {{ source('raw', 'menu') }}
    where try_to_number(r_id) is not null
      and try_to_number(price, 10, 2) > 0
    qualify row_number() over (partition by menu_id order by _ingested_at desc) = 1
)

select
    menu_id,
    try_to_number(r_id)              as restaurant_id,
    f_id,
    cuisine,
    try_to_number(price, 10, 2)        as price,
    _batch_id
from deduped
