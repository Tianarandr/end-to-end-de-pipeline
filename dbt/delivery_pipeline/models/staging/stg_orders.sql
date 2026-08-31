-- Grain: one row per order_id. RAW.orders is loaded as all-STRING columns
-- (Bronze principle: no casting at load time), so this model owns every cast.
with deduped as (
    select *
    from {{ source('raw', 'orders') }}
    where try_to_number(order_id) is not null
    qualify row_number() over (partition by order_id order by _ingested_at desc) = 1
)

select
    order_id::number                                              as order_id,
    order_timestamp::timestamp_ntz                                  as order_timestamp,
    order_date::date                                                  as order_date,
    user_id::number                                                     as customer_id,
    r_id::number                                                          as restaurant_id,
    trim(coalesce(regexp_substr(restaurant_city, '[^,]+$'), restaurant_city)) as city,
    cuisine,
    try_to_number(items_count)                                              as items_count,
    try_to_number(sales_qty)                                                  as sales_qty,
    try_to_decimal(subtotal, 12, 2)                                             as subtotal,
    try_to_decimal(discount, 12, 2)                                               as discount,
    try_to_decimal(delivery_fee, 12, 2)                                            as delivery_fee,
    try_to_decimal(gst, 12, 2)                                                       as gst,
    try_to_decimal(sales_amount, 12, 2)                                                as sales_amount,
    currency,
    payment_method,
    order_status,
    (order_status = 'Delivered')                                                          as is_delivered,
    try_to_number(customer_rating)                                                           as customer_rating,
    try_to_number(delivery_time_min)                                                           as delivery_time_min,
    _batch_id
from deduped
