{% test menu_grain_consistency(model) %}
  {#
  Test: Menu grain consistency
  ✓ Ensures no duplicate (menu_id, restaurant_id, food_id) combinations

  Rationale: Each menu_id should appear only once per restaurant-food pair.
  Duplicates indicate:
    - Source system bug (same item added twice)
    - ETL error during copy-into raw

  Severity: warn (unlikely but flags data quality investigation)
  #}
  {{ config(severity='warn') }}

  select
    menu_id,
    restaurant_id,
    food_id,
    count(*) as dup_count
  from {{ model }}
  group by menu_id, restaurant_id, food_id
  having count(*) > 1
{% endtest %}
