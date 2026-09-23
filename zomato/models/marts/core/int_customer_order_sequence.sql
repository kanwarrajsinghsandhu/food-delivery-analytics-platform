-- models/marts/core/int_customer_order_sequence.sql
-- Purpose: Shared Gold backbone -- one row per delivered order per customer, in chronological order,
--   carrying order-sequence and acquisition-cohort fields. Built once here so mart_customer_rfm,
--   mart_retention_diagnostic, mart_cohort_retention, mart_activation, and mart_basket_discount all
--   derive "first order" / "repeat order" / "cohort" the same way instead of independently
--   (previously mart_customer_rfm and mart_retention_diagnostic each re-derived this separately).
-- Grain: customer_id x order_sequence (delivered orders only; order_sequence = 1 is the first order)
-- recency_anchor_date is the dataset's own max(order_date), not current_date() -- keeps recency-based
--   calcs (see mart_customer_rfm) stable across reruns of a static/historical dataset instead of
--   drifting by 1 day every time the pipeline runs without new data landing.

{{ config(schema='MARTS') }}

with orders as (
    select *
    from {{ ref('fct_order_sales') }}
    where is_delivered = true
),

bounds as (
    select max(order_date) as recency_anchor_date
    from {{ ref('fct_order_sales') }}
),

sequenced as (
    select
        o.customer_id,
        o.order_id,
        o.order_date,
        o.restaurant_id,
        o.cuisine,
        o.sales_amount_cad,
        o.delivery_time_min,
        o.customer_rating,
        o.discount_cad,
        o.is_discounted,

        row_number() over (partition by o.customer_id order by o.order_date, o.order_id)
            as order_sequence,
        min(o.order_date) over (partition by o.customer_id)
            as first_order_date,
        first_value(o.restaurant_id) over (partition by o.customer_id order by o.order_date, o.order_id)
            as first_order_restaurant_id,
        lag(o.order_date) over (partition by o.customer_id order by o.order_date, o.order_id)
            as prev_order_date

    from orders o
)

select
    s.customer_id,
    s.order_id,
    s.order_date,
    s.order_sequence,
    s.first_order_date,
    date_trunc('month', s.first_order_date)::date as acquisition_cohort_month,
    b.recency_anchor_date,

    datediff(day, s.first_order_date, s.order_date) as days_since_first_order,
    datediff(day, s.prev_order_date, s.order_date) as days_since_prev_order,

    s.restaurant_id,
    s.cuisine,
    (s.restaurant_id = s.first_order_restaurant_id) as is_same_restaurant_as_first_order,

    s.sales_amount_cad,
    s.delivery_time_min,
    s.customer_rating,
    s.discount_cad,
    s.is_discounted

from sequenced s
cross join bounds b
