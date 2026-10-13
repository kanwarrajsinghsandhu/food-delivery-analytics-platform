-- models/marts/customer/mart_growth_accounting_monthly.sql
-- Purpose: KPI-tile mart for the Power BI retention page -- monthly growth accounting (MAU split into
--   new / retained / resurrected, with churned as the outflow), per acquisition city.
-- Grain: activity_month x acquisition_city
-- FK: activity_month -> dim_date.month_start
--
-- Additive counts only. Ratios (monthly retention = retained / prior_month_mau, resurrection share =
--   resurrected / mau, quick ratio = (new + resurrected) / churned, orders per active = delivered_orders
--   / mau) are deliberately NOT stored -- they must be computed as SUM/SUM in the BI layer so they stay
--   correct for any city selection. Averaging per-city ratios would be wrong.
-- Additivity across cities holds because each customer has exactly one acquisition_city (see
--   mart_customer_monthly_status). Definitions of each status live in that model's header comment.
-- MAU here is delivered-only, so it is <= mart_executive_summary.monthly_active_users (any order status).

{{ config(schema='MARTS') }}

select
    activity_month,
    acquisition_city,

    count_if(is_active) as mau,
    count_if(lifecycle_status = 'new') as new_customers,
    count_if(lifecycle_status = 'retained') as retained_customers,
    count_if(lifecycle_status = 'resurrected') as resurrected_customers,
    count_if(lifecycle_status = 'churned') as churned_customers,
    count_if(was_active_prev_month) as prior_month_mau,

    sum(delivered_orders) as delivered_orders,
    sum(gmv_cad) as gmv_cad

from {{ ref('mart_customer_monthly_status') }}
group by activity_month, acquisition_city
