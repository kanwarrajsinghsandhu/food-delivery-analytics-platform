-- models/staging/stg_users.sql
-- Purpose: Clean and standardize user data for downstream analytics
-- PK: user_id | FKs: none
-- Key transformations: exclude PII (password), add income midpoint (INR & CAD)

with source_data as (
  select
    cast(user_id as integer) as user_id,
    cast(name as string) as name,
    cast(email as string) as email,
    cast(age as integer) as age,
    cast(gender as string) as gender,
    cast(marital_status as string) as marital_status,
    cast(occupation as string) as occupation,
    cast(monthly_income as string) as monthly_income,
    case
      when monthly_income = 'No Income' then 0.0
      when monthly_income = 'Below Rs.10000' then 5000.0
      when monthly_income = '10001 to 25000' then 17500.0
      when monthly_income = '25001 to 50000' then 37500.0
      when monthly_income = 'More than 50000' then 75000.0
      else null
    end::float as monthly_income_midpoint_inr,
    cast(education as string) as education,
    cast(family_size as integer) as family_size
  from {{ source('raw', 'USERS') }}
),

add_cad_values as (
  select
    *,
    {{ inr_to_cad('monthly_income_midpoint_inr') }} as monthly_income_midpoint_cad
  from source_data
)

select * from add_cad_values
where education in ('Graduate', 'Post Graduate', 'Undergraduate', 'High School')