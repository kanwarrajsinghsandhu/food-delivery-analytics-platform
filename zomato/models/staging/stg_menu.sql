-- models/staging/stg_menu.sql
-- Purpose: Clean menu items with restaurant/food foreign keys and currency conversion
-- PK: menu_id | FKs: restaurant_id → stg_restaurants.id, food_id → stg_food.food_id
-- Key transformations: rename r_id/f_id, add price_cad

with source_data as (
  select
    cast(menu_id as string) as menu_id,
    cast(r_id as integer) as restaurant_id,
    cast(f_id as string) as food_id,
    cast(cuisine as string) as cuisine,
    -- Extract numeric value from price (handles both plain numeric "8.0" and text-embedded formats)
    -- Confirmed: raw MENU.price has no letters; values range from 0.95 to low hundreds
    cast(
      regexp_substr(price, '[0-9]+(\.[0-9]+)?')
      as decimal(10, 2)
    ) as price_inr
  from {{ source('raw', 'MENU') }}
),

add_cad_price as (
  select
    *,
    {{ inr_to_cad('price_inr') }} as price_cad
  from source_data
)

select * from add_cad_price