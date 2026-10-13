-- models/marts/customer/mart_retention_diagnostic.sql
-- Purpose: Observed association between first-order experience (delivery speed, rating, discount)
--   and repeat ordering behavior. One row per customer.
-- OBSERVATIONAL, NOT CAUSAL: this mart reports raw associations with no controls for confounders
--   (city, cuisine, customer segment, restaurant, etc.) -- a bucket showing a higher repeat rate is
--   a hypothesis to test, not a finding. Discount usage in particular is a customer choice, not a
--   randomized treatment, so any discount/retention gap may reflect selection bias (price-sensitive
--   customers behave differently regardless of the discount) rather than the discount causing the
--   behavior. Multivariate control for these factors is Phase B's job, not this mart's.
-- Grain: customer_id (one row per customer)
-- Key question: Is a faster/higher-rated first order associated with a second order within 30 days?

{{ config(schema='MARTS') }}

with first_orders as (
    select
        customer_id,
        order_id as first_order_id,
        order_date as first_order_date,
        acquisition_cohort_month,
        delivery_time_min as first_order_delivery_time,
        customer_rating as first_order_rating,
        discount_cad as first_order_discount_cad
    from {{ ref('int_customer_order_sequence') }}
    where order_sequence = 1
),

second_orders as (
    select
        customer_id,
        order_date as second_order_date,
        days_since_first_order as days_to_second_order
    from {{ ref('int_customer_order_sequence') }}
    where order_sequence = 2
),

repeat_summary as (
    select
        customer_id,
        max(order_sequence) as total_orders,
        count_if(order_sequence > 1) as repeat_order_count,
        avg(case when order_sequence > 1 then sales_amount_cad end) as repeat_aov_cad
    from {{ ref('int_customer_order_sequence') }}
    group by customer_id
),

with_experience_buckets as (
    select
        f.*,

        -- Delivery speed buckets
        case
            when f.first_order_delivery_time <= 20 then 'Very Fast (0-20 min)'
            when f.first_order_delivery_time <= 30 then 'Fast (20-30 min)'
            when f.first_order_delivery_time <= 40 then 'Moderate (30-40 min)'
            else 'Slow (40+ min)'
        end as delivery_speed_bucket,

        -- Rating buckets. Unrated first orders get their own bucket: without the null branch they
        -- fell through to 'Poor (<3.0)' (~30% of customers), so 'Poor' was mostly unrated orders.
        case
            when f.first_order_rating is null then 'Unrated'
            when f.first_order_rating >= 4.5 then 'Excellent (4.5-5.0)'
            when f.first_order_rating >= 4.0 then 'Good (4.0-4.5)'
            when f.first_order_rating >= 3.0 then 'Fair (3.0-4.0)'
            else 'Poor (<3.0)'
        end as rating_bucket

    from first_orders f
),

final as (
    select
        b.customer_id,
        b.first_order_id,
        b.first_order_date,
        b.acquisition_cohort_month,
        b.first_order_delivery_time,
        b.delivery_speed_bucket,
        b.first_order_rating,
        b.rating_bucket,
        b.first_order_discount_cad,
        (b.first_order_discount_cad > 0) as did_use_discount_on_first_order,
        (r.total_orders > 1) as did_reorder,
        case
            when r.total_orders > 1 and so.days_to_second_order <= 30 then true
            else false
        end as did_reorder_within_30d,
        so.second_order_date,
        so.days_to_second_order,
        r.repeat_order_count,
        r.repeat_aov_cad
    from with_experience_buckets b
    inner join repeat_summary r
        on b.customer_id = r.customer_id
    left join second_orders so
        on b.customer_id = so.customer_id
)

select * from final
