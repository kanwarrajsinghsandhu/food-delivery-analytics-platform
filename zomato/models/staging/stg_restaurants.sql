-- models/staging/stg_restaurants.sql
-- Purpose: Clean restaurant dimension with currency conversion (INR → CAD)
-- PK: id | FKs: none
-- Key transformations:
--   1. Parse cost (₹ 200 → 200 INR → 3 CAD)
--   2. Standardize rating (-- → null)
--   3. Parse rating_count ("100+ ratings" → 100)
--   4. Extract city (last comma-separated value)

with source_data as (
  select
    cast(id as integer) as id,
    cast(name as string) as name,
    trim(coalesce(regexp_substr(city, '[^,]+$'), city)) as city,
    -- Rating: replace "--" with null before casting
    case
      when rating = '--' then null
      else cast(rating as decimal(3,1))
    end as rating,
    -- Rating count: extract numeric value from text ranges
    case
      when rating_count = 'Too Few Ratings' then 0
      when rating_count like '%100%' then 100
      when rating_count like '%50%' then 50
      when rating_count like '%20%' then 20
      else null
    end::integer as rating_count,
    -- Cost: extract numeric INR value (e.g., "₹ 200" → 200)
    -- Confirmed: raw RESTAURANTS.cost has no letters; values range from ₹1 to ₹300350 (one outlier)
    cast(
      regexp_substr(cost, '[0-9]+(\.[0-9]+)?')
      as integer
    ) as cost_inr,
    cast(cuisine as string) as cuisine,
    cast(lic_no as string) as lic_no,
    cast(link as string) as link,
    cast(address as string) as address,
    cast(menu as string) as menu
  from {{ source('raw', 'RESTAURANTS') }}
),

add_cad_cost as (
  select
    *,
    {{ inr_to_cad('cost_inr') }} as cost_cad
  from source_data
)

select * from add_cad_cost