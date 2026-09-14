-- models/marts/core/fct_order_items.sql
-- Purpose: Atomic Gold fact — one row per order line item, foundation for menu/product-level analytics
-- Grain: order_item_id
-- order_date and is_delivered are denormalized from the parent order (single equality join) so
--   item-level analysis doesn't require joining to the much larger fct_order_sales for basic time/status slicing

with order_items as (
    select * from {{ ref('stg_order_items') }}
),

orders as (
    select order_id, order_date, is_delivered
    from {{ ref('stg_orders') }}
),

final as (
    select
        oi.order_item_id,
        oi.order_id,
        oi.restaurant_id,
        oi.food_id,

        o.order_date,
        o.is_delivered,

        oi.quantity,

        oi.price as unit_price_inr,
        {{ inr_to_cad('oi.price') }} as unit_price_cad,

        oi.line_amount as line_amount_inr,
        {{ inr_to_cad('oi.line_amount') }} as line_amount_cad

    from order_items oi
    inner join orders o
        on oi.order_id = o.order_id
)

select * from final
