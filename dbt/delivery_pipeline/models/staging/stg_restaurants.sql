-- Grain: one row per restaurant_id. Dedupes on the restaurant's natural key,
-- keeping the most recently ingested row if the same id was ever reloaded.
with deduped as (
    select *
    from {{ source('raw', 'restaurants') }}
    where try_to_number(id) is not null
    qualify row_number() over (partition by id order by _ingested_at desc) = 1
)

select
    id::number                                            as restaurant_id,
    name                                                    as restaurant_name,
    trim(coalesce(regexp_substr(city, '[^,]+$'), city))      as city,
    try_to_decimal(nullif(rating, '--'), 3, 1)                 as rating,
    try_to_number(regexp_substr(rating_count, '[0-9]+'))        as rating_count,
    try_to_number(regexp_substr(cost, '[0-9]+'))                 as cost_for_two,
    cuisine,
    lic_no                                                        as license_no,
    _batch_id
from deduped
