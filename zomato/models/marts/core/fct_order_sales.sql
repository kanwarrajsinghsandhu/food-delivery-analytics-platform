-- models/marts/core/fct_order_sales.sql
-- Purpose: Atomic Gold fact — one row per order, all commercial measures in INR + CAD
-- Grain: order_id
-- order_status has exactly 3 values in source data: Delivered, Cancelled, Refunded (confirmed against live data)
-- is_late_delivery_proxy: no ETA/promised-delivery-time field exists in source data, so this is an
--   absolute-threshold proxy (delivery_time_min > 30), not the real dynamic-ETA SLA-breach definition

{{ config(schema='MARTS') }}

with orders as (
    select * from {{ ref('stg_orders') }}
),

final as (
    select
        order_id,
        customer_id,
        restaurant_id,

        order_timestamp,
        order_date,

        city_area,
        city,
        cuisine,

        items_count,
        sales_qty,

        subtotal as subtotal_inr,
        {{ inr_to_cad('subtotal') }} as subtotal_cad,

        discount as discount_inr,
        {{ inr_to_cad('discount') }} as discount_cad,

        delivery_fee as delivery_fee_inr,
        {{ inr_to_cad('delivery_fee') }} as delivery_fee_cad,

        gst as gst_inr,
        {{ inr_to_cad('gst') }} as gst_cad,

        sales_amount as sales_amount_inr,
        {{ inr_to_cad('sales_amount') }} as sales_amount_cad,

        currency as original_currency,
        payment_method,
        order_status,

        is_delivered,
        (order_status = 'Cancelled') as is_cancelled,
        (order_status = 'Refunded') as is_refunded,
        (discount > 0) as is_discounted,

        customer_rating,
        delivery_time_min,
        case
            when delivery_time_min is null then null
            else delivery_time_min > 30
        end as is_late_delivery_proxy

    from orders
)

select * from final
