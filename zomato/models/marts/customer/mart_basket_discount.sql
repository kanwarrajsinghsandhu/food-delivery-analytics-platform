-- models/marts/customer/mart_basket_discount.sql
-- Purpose: Discount-dependency diagnostic -- are discount-heavy customers actually valuable/retained,
--   or is the platform subsidizing one-time, price-driven orders?
-- OBSERVATIONAL, NOT CAUSAL: discount usage is a customer choice, not a randomized treatment, so any
--   value/retention gap here may reflect selection bias (price-sensitive customers behave differently
--   regardless of discounts) rather than a causal effect of discounting -- same caveat as
--   mart_retention_diagnostic. Multivariate control is Phase B's job, not this mart's.
-- Grain: customer_id (one row per customer with at least 1 delivered order)
-- Keyspace note: this mart carries the full order-side customer keyspace (~100K, from
--   int_customer_order_sequence/fct_order_sales), while mart_customer_rfm is filtered to the
--   dim_customer keyspace (~90K, after stg_users' education filter) -- same known sample-data gap
--   documented on fct_order_sales.customer_id. Rows for the ~10K customers outside dim_customer will
--   have null monetary_value_cad/rfm_segment_label/did_reorder_within_30d.

{{ config(schema='MARTS') }}

with discount_history as (
    select
        customer_id,
        count(*) as total_orders,
        count_if(is_discounted) as discounted_orders,
        sum(discount_cad) as total_discount_cad,
        avg(case when is_discounted then discount_cad end) as avg_discount_cad_when_used
    from {{ ref('int_customer_order_sequence') }}
    group by customer_id
),

with_dependency as (
    select
        *,
        discounted_orders::float / total_orders as pct_orders_discounted,
        case
            when discounted_orders::float / total_orders >= 0.5 then 'Discount-Reliant'
            when discounted_orders > 0 then 'Occasional Discount User'
            else 'Full-Price'
        end as discount_dependency_segment
    from discount_history
)

select
    d.customer_id,
    d.total_orders,
    d.discounted_orders,
    d.pct_orders_discounted,
    d.total_discount_cad,
    d.avg_discount_cad_when_used,
    d.discount_dependency_segment,

    r.monetary_value_cad,
    r.frequency_orders,
    r.segment_label as rfm_segment_label,

    rd.did_reorder_within_30d

from with_dependency d
left join {{ ref('mart_customer_rfm') }} r
    on d.customer_id = r.customer_id
left join {{ ref('mart_retention_diagnostic') }} rd
    on d.customer_id = rd.customer_id
