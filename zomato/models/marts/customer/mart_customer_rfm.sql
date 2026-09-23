-- models/marts/customer/mart_customer_rfm.sql
-- Purpose: RFM segmentation (Recency, Frequency, Monetary) for customer value tiers
-- Grain: customer_id (one row per customer)
-- RFM scoring: 1-5 quintiles per metric; 5=best, 1=worst
-- Segment labels: Champions, Loyal, At-Risk, Lost, etc.
-- recency_days is anchored to the dataset's own most recent order date (recency_anchor_date, from
--   int_customer_order_sequence), not current_date() -- current_date() would make recency_days grow
--   by 1 every day this pipeline reruns without new data landing, silently drifting the R-score
--   quintiles on a static/historical dataset.

{{ config(schema='MARTS') }}

with customer_orders as (
    select
        c.customer_id,
        max(o.first_order_date) as first_order_date,
        max(o.order_date) as last_order_date,
        max(o.recency_anchor_date) as recency_anchor_date,
        count(distinct o.order_id) as frequency_orders,
        sum(o.sales_amount_cad) as monetary_value_cad
    from {{ ref('dim_customer') }} c
    left join {{ ref('int_customer_order_sequence') }} o
        on c.customer_id = o.customer_id
    group by c.customer_id
),

with_recency as (
    select
        *,
        datediff(day, last_order_date, recency_anchor_date) as recency_days
    from customer_orders
    where frequency_orders > 0  -- only customers with at least 1 delivered order
),

with_quintile_scores as (
    select
        customer_id,
        first_order_date,
        last_order_date,
        recency_days,
        frequency_orders,
        monetary_value_cad,

        -- Recency score: inverted (lower days = higher score, 5 is best/most recent)
        case when recency_days is null then null
             else 6 - ntile(5) over (order by recency_days)
        end as r_score,

        -- Frequency score: higher frequency = higher score (5 is best)
        case when frequency_orders is null then null
             else ntile(5) over (order by frequency_orders)
        end as f_score,

        -- Monetary score: higher value = higher score (5 is best)
        case when monetary_value_cad is null then null
             else ntile(5) over (order by monetary_value_cad)
        end as m_score

    from with_recency
),

with_rfm_segment as (
    select
        *,
        concat(r_score, f_score, m_score) as rfm_segment,

        -- Segment labels based on RFM combination
        case
            when r_score >= 4 and f_score >= 4 and m_score >= 4 then 'Champions'
            when r_score >= 4 and f_score >= 3 and m_score >= 3 then 'Loyal Customers'
            when r_score >= 4 and f_score >= 2 then 'Potential Loyalists'
            when r_score >= 3 and f_score >= 3 and m_score >= 3 then 'Valuable'
            when r_score <= 2 and f_score >= 4 then 'At Risk'
            when r_score <= 2 and f_score >= 3 and m_score >= 3 then 'Needs Attention'
            when r_score <= 2 then 'Lost'
            else 'Other'
        end as segment_label

    from with_quintile_scores
)

select * from with_rfm_segment
