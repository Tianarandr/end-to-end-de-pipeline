-- Grain: one row per order_item_id (an order line).
with deduped as (
    select *
    from {{ source('raw', 'order_items') }}
    where try_to_number(order_item_id) is not null
    qualify row_number() over (partition by order_item_id order by _ingested_at desc) = 1
)

select
    order_item_id::number             as order_item_id,
    order_id::number                    as order_id,
    r_id::number                          as restaurant_id,
    f_id,
    try_to_decimal(price, 10, 2)             as price,
    try_to_number(quantity)                    as quantity,
    try_to_decimal(line_amount, 10, 2)           as line_amount,
    _batch_id
from deduped
