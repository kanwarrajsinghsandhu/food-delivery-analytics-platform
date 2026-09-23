-- models/marts/customer/mart_cohort_retention.sql
-- Purpose: Classic cohort-retention curve -- for each customer acquisition cohort (month of first
--   delivered order), what % of that cohort placed at least one delivered order in each subsequent
--   month. Feeds the cohort-retention heatmap (cohort month x months-since-acquisition) in the BI
--   layer. Complements mart_activation, which tracks specifically the *second* order rather than
--   any repeat order in a given period.
-- Grain: acquisition_cohort_month x period_number (months since acquisition; 0 = acquisition month)
-- No date spine: a (cohort, period) with zero active customers simply produces no row -- same
--   simplification already documented in mart_executive_summary. Power BI's matrix visual leaves
--   those cells blank rather than showing a misleading 0%.
-- Keyspace note: cohort_size/active_customers count the full order-side customer keyspace (~100K),
--   not the dim_customer keyspace (~90K, filtered by stg_users' education field) -- same known
--   sample-data gap documented on fct_order_sales.customer_id. Don't expect this mart's totals to
--   tie out to mart_customer_rfm's customer count.

{{ config(schema='MARTS') }}

with orders as (
    select
        customer_id,
        order_date,
        acquisition_cohort_month,
        datediff(month, acquisition_cohort_month, date_trunc('month', order_date)) as period_number
    from {{ ref('int_customer_order_sequence') }}
),

cohort_sizes as (
    select
        acquisition_cohort_month,
        count(distinct customer_id) as cohort_size
    from orders
    where period_number = 0
    group by acquisition_cohort_month
),

period_activity as (
    select
        acquisition_cohort_month,
        period_number,
        count(distinct customer_id) as active_customers
    from orders
    group by acquisition_cohort_month, period_number
)

select
    p.acquisition_cohort_month,
    p.period_number,
    c.cohort_size,
    p.active_customers,
    p.active_customers::float / c.cohort_size as retention_rate
from period_activity p
inner join cohort_sizes c
    on p.acquisition_cohort_month = c.acquisition_cohort_month
order by p.acquisition_cohort_month, p.period_number
