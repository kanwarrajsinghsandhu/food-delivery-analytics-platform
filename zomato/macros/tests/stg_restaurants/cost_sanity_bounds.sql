{% test cost_sanity_bounds(model, tolerance=0.01) %}
  {#
  Test: Cost INR-to-CAD conversion accuracy
  ✓ Ensures cost_cad == cost_inr * 0.015 (within tolerance)

  Rationale: If CAD cost doesn't match INR cost via exchange rate,
  indicates calculation error in staging logic or data corruption.

  Severity: error (must be fixed before marts layer consumes this data)
  #}
  {{ config(severity='error') }}

  select
    id,
    cost_inr,
    cost_cad,
    (cost_inr * 0.015)::decimal(10, 2) as expected_cad,
    abs(cost_cad - (cost_inr * 0.015)::decimal(10, 2)) as variance
  from {{ model }}
  where abs(cost_cad - (cost_inr * 0.015)::decimal(10, 2)) > {{ tolerance }}
{% endtest %}
