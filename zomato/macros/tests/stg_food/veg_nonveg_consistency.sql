{% test veg_nonveg_consistency(model) %}
  {#
  Test: Food category consistency
  ✓ Ensures veg_or_non_veg only has values: Veg, Non-Veg (no typos, inconsistent casing)

  Rationale: After standardization in staging, all values must be exactly "Veg" or "Non-Veg".
  Anything else indicates:
    - Data source error (raw data had unexpected value)
    - Staging CASE statement missed a pattern

  Severity: error (food category is critical for menu filtering)
  #}
  {{ config(severity='error') }}

  select
    food_id,
    item,
    veg_or_non_veg
  from {{ model }}
  where veg_or_non_veg not in ('Veg', 'Non-Veg')
    or veg_or_non_veg is null
{% endtest %}
