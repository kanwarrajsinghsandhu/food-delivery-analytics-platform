-- Canary test: proves assert_order_items_roll_up_to_orders' logic actually
-- catches a fan-out / overcharge, using synthetic data (NOT real orders).
-- Tagged 'canary' so it never runs as part of a normal `dbt build`.

{{ config(severity = 'error', store_failures = true, alias = 'dq_canary_grain_mismatch', tags = ['canary']) }}

with items as (
    select order_id, sum(line_amount) as items_total, count(*) as line_count
    from {{ ref('dq_canary_grain_items') }}
    group by 1
)

select
    o.order_id, o.items_count, i.line_count,
    o.subtotal, i.items_total,
    o.subtotal - i.items_total as variance
from {{ ref('dq_canary_grain_orders') }} o
join items i using (order_id)
where abs(o.subtotal - i.items_total) > 0.01
   or o.items_count != i.line_count
