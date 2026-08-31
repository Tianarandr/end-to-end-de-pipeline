-- Grain: one row per customer_id.
select
    customer_id,
    customer_name,
    customer_email,
    customer_age,
    case
        when customer_age < 25 then 'Gen Z'
        when customer_age < 40 then 'Millennial'
        when customer_age < 55 then 'Gen X'
        when customer_age is null then 'Unknown'
        else 'Boomer'
    end as age_segment,
    gender,
    marital_status,
    occupation,
    income_band,
    education,
    family_size
from {{ ref('stg_users') }}
