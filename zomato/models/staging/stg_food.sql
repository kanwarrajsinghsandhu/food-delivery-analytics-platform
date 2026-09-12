-- models/staging/stg_food.sql
-- Purpose: Clean food items dimension
-- PK: food_id | FKs: none
-- Key transformations: rename f_id → food_id, standardize veg/non-veg casing

with source_data as (
  select
    cast(f_id as string) as food_id,
    cast(item as string) as item,
    -- Standardize veg/non-veg to consistent casing: [Veg, Non-Veg]
    case
      when veg_or_non_veg = 'Veg' then 'Veg'
      when veg_or_non_veg in ('Non-veg', 'Non-Veg') then 'Non-Veg'
      else null
    end as veg_or_non_veg
  from {{ source('raw', 'FOOD') }}
  where cast(item as string) is not null
    and (veg_or_non_veg in ('Veg', 'Non-veg', 'Non-Veg'))
)

select * from source_data