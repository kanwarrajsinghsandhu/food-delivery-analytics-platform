-- models/marts/executive/mart_executive_summary.sql
-- Purpose: CXO dashboard mart (Case Study 1) — one row per calendar day, headline platform KPIs
-- Grain: order_date
--
-- Methodology notes (documented here, not just in YAML, since they're business-rule choices):
--   - MAU is calendar-month active customers (not a rolling 30-day window), repeated across every
--     day in that month. A true rolling-30-day MAU needs a per-day distinct-customer window, which
--     is expensive to compute correctly in Snowflake (no native DISTINCT-in-window support) — calendar
--     month is the standard, cheaper definition and is what's used here.
--   - monthly_retention_rate / monthly_churn_rate: of the customers active in the PRIOR calendar month,
--     what % also ordered in this month. Repeated across every day in the month. Null for the first
--     month in the dataset (no prior month to compare against).
--   - GMV/AOV are computed on delivered orders only (cancelled/refunded orders are tracked as separate
--     operational counts, not included in revenue).
--   - nps_score_proxy: built from 1-5 star customer_rating, not a real 0-10 recommend-likelihood
--     question. Mapping: 5=promoter, 4=passive, <=3=detractor. Score = (promoters - detractors) /
--     rated_orders * 100. Null on days with zero rated orders.
--   - No explicit date-spine: days are derived from actual order activity, not a generated calendar.
--     Given ~10M orders across ~2.5 years, gap days are effectively not expected in this dataset.

with orders as (
    select * from {{ ref('fct_order_sales') }}
),

daily as (
    select
        order_date,
        count(distinct customer_id) as daily_active_users,
        count(*) as total_orders,
        count_if(is_delivered) as delivered_orders,
        count_if(is_cancelled) as cancelled_orders,
        count_if(is_refunded) as refunded_orders,

        sum(case when is_delivered then sales_amount_inr else 0 end) as gmv_inr,
        avg(case when is_delivered then delivery_time_min end) as avg_delivery_time_min,

        count_if(customer_rating is not null) as rated_orders,
        count_if(customer_rating = 5) as nps_promoters,
        count_if(customer_rating = 4) as nps_passives,
        count_if(customer_rating <= 3) as nps_detractors

    from orders
    group by order_date
),

customer_months as (
    select distinct
        customer_id,
        date_trunc('month', order_date) as month_start
    from orders
),

monthly_active as (
    select
        month_start,
        count(distinct customer_id) as monthly_active_users
    from customer_months
    group by month_start
),

monthly_retention as (
    select
        dateadd('month', 1, prev.month_start) as month_start,
        count(distinct prev.customer_id) as prior_month_customers,
        count(distinct case when curr.customer_id is not null then prev.customer_id end) as retained_customers
    from customer_months prev
    left join customer_months curr
        on prev.customer_id = curr.customer_id
        and curr.month_start = dateadd('month', 1, prev.month_start)
    group by prev.month_start
),

final as (
    select
        d.order_date,

        d.daily_active_users,
        ma.monthly_active_users,

        d.total_orders,
        d.delivered_orders,
        d.cancelled_orders,
        d.refunded_orders,

        d.gmv_inr,
        {{ inr_to_cad('d.gmv_inr') }} as gmv_cad,

        case when d.delivered_orders > 0 then d.gmv_inr / d.delivered_orders end as aov_inr,
        case when d.delivered_orders > 0
            then {{ inr_to_cad('d.gmv_inr') }} / d.delivered_orders
        end as aov_cad,

        d.avg_delivery_time_min,

        d.rated_orders,
        d.nps_promoters,
        d.nps_passives,
        d.nps_detractors,
        case when d.rated_orders > 0
            then (d.nps_promoters - d.nps_detractors)::float / d.rated_orders * 100
        end as nps_score_proxy,

        mr.prior_month_customers,
        mr.retained_customers,
        case when mr.prior_month_customers > 0
            then mr.retained_customers::float / mr.prior_month_customers
        end as monthly_retention_rate,
        case when mr.prior_month_customers > 0
            then 1 - (mr.retained_customers::float / mr.prior_month_customers)
        end as monthly_churn_rate

    from daily d
    left join monthly_active ma
        on date_trunc('month', d.order_date) = ma.month_start
    left join monthly_retention mr
        on date_trunc('month', d.order_date) = mr.month_start
)

select * from final
