-- Grain: one row per f_id.
with deduped as (
    select *
    from {{ source('raw', 'food') }}
    where f_id is not null
    qualify row_number() over (partition by f_id order by _ingested_at desc) = 1
)

select
    f_id,
    item                                as food_name,
    initcap(veg_or_non_veg)               as veg_or_non_veg,
    _batch_id
from deduped
