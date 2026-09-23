-- models/marts/customer/mart_activation.sql
-- Purpose: First-to-second-order activation funnel by acquisition cohort -- how many first-time
--   customers come back, how fast, and at what value. Narrower than mart_cohort_retention (which
--   tracks *any* repeat order per period); this focuses specifically on the second order.
-- Grain: acquisition_cohort_month
-- Customers who never place a second order still count in cohort_size (and pull the conversion
--   percentages down) -- they correctly fail the <=7d/14d/30d checks since days_to_second_order is null.
-- Keyspace note: cohort_size counts the full order-side customer keyspace (~100K), not the
--   dim_customer keyspace (~90K, filtered by stg_users' education field) -- same known sample-data
--   gap documented on fct_order_sales.customer_id.

{{ config(schema='MARTS') }}

with first_orders as (
    select customer_id, acquisition_cohort_month
    from {{ ref('int_customer_order_sequence') }}
    where order_sequence = 1
),

second_orders as (
    select
        customer_id,
        days_since_first_order as days_to_second_order,
        sales_amount_cad as second_order_aov_cad,
        is_same_restaurant_as_first_order
    from {{ ref('int_customer_order_sequence') }}
    where order_sequence = 2
),

joined as (
    select
        f.customer_id,
        f.acquisition_cohort_month,
        s.days_to_second_order,
        s.second_order_aov_cad,
        s.is_same_restaurant_as_first_order
    from first_orders f
    left join second_orders s
        on f.customer_id = s.customer_id
)

select
    acquisition_cohort_month,
    count(distinct customer_id) as cohort_size,

    count_if(days_to_second_order <= 7)::float / count(distinct customer_id) as pct_2nd_order_within_7d,
    count_if(days_to_second_order <= 14)::float / count(distinct customer_id) as pct_2nd_order_within_14d,
    count_if(days_to_second_order <= 30)::float / count(distinct customer_id) as pct_2nd_order_within_30d,

    median(days_to_second_order) as median_days_to_2nd_order,
    avg(second_order_aov_cad) as second_order_aov_cad,

    count_if(is_same_restaurant_as_first_order)::float
        / nullif(count(days_to_second_order), 0) as repeat_restaurant_rate

from joined
group by acquisition_cohort_month
order by acquisition_cohort_month
