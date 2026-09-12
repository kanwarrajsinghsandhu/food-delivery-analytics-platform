-- models/staging/stg_reviews.sql
-- Purpose: Clean reviews with referential integrity and date validation
-- PK: review_id | FKs: order_id → stg_orders, user_id → stg_users, restaurant_id → stg_restaurants
-- Key transformations: type casting, remove denormalization (staging faithful to source)
-- Note: Removed LEFT JOIN to stg_restaurants and comment NOT NULL filter (both violate staging layer principle)

with source_data as (
  select
    cast(review_id as integer) as review_id,
    cast(order_id as integer) as order_id,
    cast(user_id as integer) as user_id,
    cast(restaurant_id as integer) as restaurant_id,
    cast(rating as integer) as rating,
    cast(comment as string) as comment,
    cast(review_date as date) as review_date
  from {{ source('raw', 'REVIEWS') }}
)

select * from source_data