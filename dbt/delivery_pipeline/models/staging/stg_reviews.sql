-- Grain: one row per review_id, comment always non-null (filtered here).
-- A review with no comment can never be enriched or retrieved, so it's
-- out of scope for every downstream AI/analytics consumer from the start.
with deduped as (
    select *
    from {{ source('raw', 'reviews') }}
    where try_to_number(review_id) is not null
      and comment is not null
    qualify row_number() over (partition by review_id order by _ingested_at desc) = 1
)

select
    r.review_id::number         as review_id,
    r.order_id::number            as order_id,
    r.user_id::number               as customer_id,
    r.restaurant_id::number           as restaurant_id,
    try_to_number(r.rating)             as rating,
    r.comment::string                     as comment,
    r.review_date::date                     as review_date,
    res.city                                  as city,
    r._batch_id
from deduped r
left join {{ ref('stg_restaurants') }} res on r.restaurant_id::number = res.restaurant_id
