-- models/marts/core/dim_customer.sql
-- Purpose: Gold customer dimension — attributes only, no order-derived business logic
-- Grain: customer_id (renamed from stg_users.user_id to match fct_order_sales.customer_id for joins)
-- Order-derived metrics (recency, frequency, monetary, segmentation) belong in mart_customer_rfm, not here

with customers as (
    select * from {{ ref('stg_users') }}
),

final as (
    select
        user_id as customer_id,
        name,
        email,
        age,
        gender,
        marital_status,
        occupation,
        monthly_income,
        monthly_income_midpoint_inr,
        monthly_income_midpoint_cad,
        education,
        family_size
    from customers
)

select * from final
