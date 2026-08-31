-- What ai/rag/prepare.py actually reads (never STAGING.STG_REVIEWS
-- directly, see docs/architecture/04-ai-architecture.md#b-retrieval--rag-airag).
-- Excludes customer_id on purpose: RAG only needs review content and
-- restaurant/city context to answer "what are people saying," not who
-- said it. Least data necessary, not just least privilege by role.
select
    review_id,
    city,
    rating,
    comment,
    review_date
from {{ ref('stg_reviews') }}
