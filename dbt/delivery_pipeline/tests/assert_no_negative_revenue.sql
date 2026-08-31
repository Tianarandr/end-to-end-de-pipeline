-- Singular business-rule test (blocking by default for singular tests).
-- Daily GMV should never be negative. A violation means a measure
-- definition broke somewhere, not that a restaurant owes customers money.
select order_date, city, gross_merchandise_value
from {{ ref('sem_revenue_daily') }}
where gross_merchandise_value < 0
