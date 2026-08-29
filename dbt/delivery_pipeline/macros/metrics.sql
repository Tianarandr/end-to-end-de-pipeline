{#
    Business-metric SQL expressions. See ADR-005 and
    docs/architecture/03-data-model.md#gold-marts-schema.

    Every mart and semantic view that needs GMV, cancellation rate, average
    order value, or delivered-order count calls one of these instead of
    re-deriving the aggregate. Before this existed, the three marts each
    hand-wrote `SUM(iff(is_delivered, sales_amount, 0))` on their own, which
    meant one could drift from the others without anyone noticing.
    metrics.yml (dbt/delivery_pipeline/metrics/metrics.yml) documents the
    same definitions for human and AI consumers, so keep both in sync when a
    definition changes.
#}

{% macro delivered_orders_expr(is_delivered_col='is_delivered') -%}
    COUNT_IF({{ is_delivered_col }})
{%- endmacro %}

{% macro gross_merchandise_value_expr(is_delivered_col='is_delivered', amount_col='sales_amount') -%}
    SUM(IFF({{ is_delivered_col }}, {{ amount_col }}, 0))
{%- endmacro %}

{% macro cancellation_rate_expr(status_col='order_status', cancelled_value="'Cancelled'") -%}
    ROUND(DIV0(COUNT_IF({{ status_col }} = {{ cancelled_value }}), COUNT(*)), 4)
{%- endmacro %}

{% macro average_order_value_expr(is_delivered_col='is_delivered', amount_col='sales_amount') -%}
    ROUND(DIV0(
        {{ gross_merchandise_value_expr(is_delivered_col, amount_col) }},
        {{ delivered_orders_expr(is_delivered_col) }}
    ), 2)
{%- endmacro %}

{% macro late_delivery_rate_expr(delivery_minutes_col='delivery_time_min') -%}
    ROUND(DIV0(
        COUNT_IF({{ delivery_minutes_col }} > {{ var('delivery_sla_threshold_minutes') }}),
        COUNT(*)
    ), 4)
{%- endmacro %}
