{{ config(severity = 'error', store_failures = true, alias = 'dq_grain_mismatch') }}

with items as (
    select order_id, sum(line_amount) as items_total, count(*) as line_count
    from {{ ref('stg_order_items') }}
    group by 1
)

select
    o.order_id, o.items_count, i.line_count,
    o.subtotal, i.items_total,
    o.subtotal - i.items_total as variance
from {{ ref('stg_orders') }} o
join items i using (order_id)
where abs(o.subtotal - i.items_total) > 0.01
   or o.items_count != i.line_count
