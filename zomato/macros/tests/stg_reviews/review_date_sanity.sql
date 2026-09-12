{% test review_date_sanity(model) %}
  {#
  Test: Review date sanity check
  ✓ Ensures review_date is not in future (≤ current date)

  Rationale: Reviews cannot be posted before they're written.
  Future dates indicate:
    - Clock skew in source system
    - Test data that wasn't cleaned before loading
    - Data corruption during ETL

  Severity: error (future reviews break time-based analysis in marts)
  #}
  {{ config(severity='error') }}

  select
    review_id,
    order_id,
    review_date,
    current_date() as today
  from {{ model }}
  where review_date > current_date()
{% endtest %}
