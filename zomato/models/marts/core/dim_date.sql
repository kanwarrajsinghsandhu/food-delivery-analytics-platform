-- models/marts/core/dim_date.sql
-- Purpose: Gold calendar dimension for the BI layer -- Power BI needs a contiguous, marked date table
--   for month/year slicers and time intelligence (MoM, YoY). Fact tables only carry dates that had orders.
-- Grain: date_day (one row per calendar day, no gaps)
-- Bounds come from fct_order_sales' own min/max order_date (2023-07-01 to 2026-06-30 on RAW_V2), not
--   hardcoded, so the spine follows the data if the dataset is extended.
-- Built with Snowflake's generator + row_number() rather than seq4() directly, since seq4() is not
--   guaranteed gap-free.

{{ config(schema='MARTS') }}

with bounds as (
    select
        min(order_date) as start_date,
        max(order_date) as end_date
    from {{ ref('fct_order_sales') }}
),

offsets as (
    select row_number() over (order by seq4()) - 1 as day_offset
    from table(generator(rowcount => 5000))
),

spine as (
    select dateadd(day, o.day_offset, b.start_date)::date as date_day
    from offsets o
    cross join bounds b
    where dateadd(day, o.day_offset, b.start_date) <= b.end_date
)

select
    date_day,
    date_trunc('month', date_day)::date as month_start,
    year(date_day) as year,
    quarter(date_day) as quarter,
    month(date_day) as month_num,
    monthname(date_day) as month_name,
    to_char(date_day, 'YYYY-MM') as year_month_label,
    (date_day = last_day(date_day)) as is_month_end
from spine
