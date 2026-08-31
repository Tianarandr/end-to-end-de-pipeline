-- Grain: one row per customer_id.
with deduped as (
    select *
    from {{ source('raw', 'users') }}
    where try_to_number(user_id) is not null
    qualify row_number() over (partition by user_id order by _ingested_at desc) = 1
)

select
    user_id::number             as customer_id,
    name                          as customer_name,
    lower(email)                   as customer_email,
    try_to_number(age)               as customer_age,
    gender,
    marital_status,
    occupation,
    monthly_income                     as income_band,
    education,
    try_to_number(family_size)           as family_size,
    _batch_id
from deduped
