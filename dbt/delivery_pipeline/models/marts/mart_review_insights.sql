{{ config(tags=['ai']) }}

-- Grain: one row per (city, topic, sentiment_label). Blends governed review
-- data with AI-enriched sentiment/topic. Built only after ai_enrichment has
-- run (Airflow `publish` stage: dbt build --select tag:ai). See
-- docs/architecture/04-ai-architecture.md#a-batch-ai-enrichment-aienrichment.
select
    sr.city,
    e.topic,
    e.sentiment_label,
    count(*)                                 as reviews,
    round(avg(e.sentiment_score), 3)           as avg_sentiment_score,
    round(avg(sr.rating), 2)                     as avg_star_rating,
    count_if(e.key_issue is not null)              as flagged_issues
from {{ source('ai', 'review_enriched') }} e
inner join {{ ref('stg_reviews') }} sr using (review_id)
group by 1, 2, 3
