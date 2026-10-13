-- models/marts/customer/mart_customer_monthly_status.sql
-- Purpose: Customer lifecycle fact for growth accounting -- every customer's status in every month from
--   their acquisition month to the dataset's last month: new / retained / resurrected / churned / dormant.
--   Feeds mart_growth_accounting_monthly (the KPI-tile mart) and lets the BI layer slice lifecycle
--   metrics by acquisition city and build a city-filterable cohort heatmap (period_number x is_active).
-- Grain: customer_id x activity_month
-- FK: customer_id -> dim_customer; activity_month -> dim_date.month_start
--
-- Definitions (business-rule choices, documented here not just in YAML):
--   - Active = >=1 *delivered* order in the calendar month (same delivered-only basis as every other
--     lifecycle mart built on int_customer_order_sequence). mart_executive_summary's MAU counts any order
--     status, so its MAU is >= this one -- see the mau_within_executive_summary test.
--   - lifecycle_status (standard growth-accounting definition, prior-month based):
--       new         = acquisition month (period_number = 0)
--       retained    = active this month and last month
--       resurrected = active this month, inactive last month, acquired before this month
--       churned     = inactive this month, active last month
--       dormant     = inactive this month and last month
--     Identity: MAU(t) = new + retained + resurrected; MAU(t-1) = retained(t) + churned(t).
--   - City = acquisition_city (city of first delivered order), fixed per customer -- so counts add up
--     across cities. Not cuisine-filterable by design: status is platform-level, not per-cuisine.
--   - Activation fields (days_to_second_order, is_activated_30d, is_activation_window_complete) are
--     customer-level, repeated on every row -- count them on period_number = 0 rows only, or each
--     customer is counted once per month they're in the spine.
--   - is_activation_window_complete = the customer has had a full 30 days of data after their first
--     order. Late-June-2026 acquisitions haven't, so the latest cohort's 30-day activation reads
--     artificially low unless restricted to complete windows.
-- Keyspace note: covers the full order-side customer keyspace (~100K), not the dim_customer keyspace
--   (~90K, filtered by stg_users' education field) -- same known gap as fct_order_sales.customer_id.

{{ config(schema='MARTS') }}

with seq as (
    select * from {{ ref('int_customer_order_sequence') }}
),

customers as (
    select
        customer_id,
        first_order_date,
        acquisition_cohort_month,
        acquisition_city,
        recency_anchor_date
    from seq
    where order_sequence = 1
),

second_orders as (
    select
        customer_id,
        days_since_first_order as days_to_second_order
    from seq
    where order_sequence = 2
),

months as (
    select distinct month_start
    from {{ ref('dim_date') }}
),

spine as (
    select
        c.customer_id,
        c.first_order_date,
        c.acquisition_cohort_month,
        c.acquisition_city,
        c.recency_anchor_date,
        m.month_start as activity_month
    from customers c
    inner join months m
        on m.month_start >= c.acquisition_cohort_month
        and m.month_start <= date_trunc('month', c.recency_anchor_date)
),

monthly_activity as (
    select
        customer_id,
        date_trunc('month', order_date)::date as activity_month,
        count(*) as delivered_orders,
        sum(sales_amount_cad) as gmv_cad,
        max(order_date) as last_order_date_in_month
    from seq
    group by customer_id, date_trunc('month', order_date)::date
),

joined as (
    select
        s.customer_id,
        s.activity_month,
        s.acquisition_cohort_month,
        s.acquisition_city,
        s.first_order_date,
        s.recency_anchor_date,
        datediff(month, s.acquisition_cohort_month, s.activity_month) as period_number,

        coalesce(a.delivered_orders, 0) as delivered_orders,
        coalesce(a.gmv_cad, 0) as gmv_cad,
        (a.delivered_orders is not null) as is_active,

        max(a.last_order_date_in_month) over (
            partition by s.customer_id
            order by s.activity_month
            rows between unbounded preceding and current row
        ) as last_order_date_to_date

    from spine s
    left join monthly_activity a
        on s.customer_id = a.customer_id
        and s.activity_month = a.activity_month
),

with_prev as (
    select
        *,
        coalesce(
            lag(is_active) over (partition by customer_id order by activity_month),
            false
        ) as was_active_prev_month
    from joined
)

select
    p.customer_id,
    p.activity_month,
    p.acquisition_cohort_month,
    p.acquisition_city,
    p.period_number,

    p.delivered_orders,
    p.gmv_cad,
    p.is_active,
    p.was_active_prev_month,

    case
        when p.period_number = 0 then 'new'
        when p.is_active and p.was_active_prev_month then 'retained'
        when p.is_active then 'resurrected'
        when p.was_active_prev_month then 'churned'
        else 'dormant'
    end as lifecycle_status,

    datediff(
        day,
        p.last_order_date_to_date,
        least(last_day(p.activity_month), p.recency_anchor_date)
    ) as days_since_last_order_at_month_end,

    s.days_to_second_order,
    coalesce(s.days_to_second_order <= 30, false) as is_activated_30d,
    (dateadd(day, 30, p.first_order_date) <= p.recency_anchor_date) as is_activation_window_complete

from with_prev p
left join second_orders s
    on p.customer_id = s.customer_id
