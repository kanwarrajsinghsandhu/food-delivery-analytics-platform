{% test activation_reconciles(model) %}
  {#
  Test: per acquisition cohort, this mart's period_number = 0 rows must reproduce mart_activation --
  (1) the row count equals cohort_size, and (2) the count of is_activated_30d customers equals
  pct_2nd_order_within_30d x cohort_size (within 0.5 for float rounding).

  Rationale: the Power BI activation tile is computed from this mart (so it can be city-filtered), while
  the existing Streamlit dashboard reads mart_activation. Both derive from int_customer_order_sequence;
  if they drift, the two dashboards would show different activation rates for the same cohort.

  Severity: error (cross-mart grain/aggregation mismatch).
  #}
  {{ config(severity='error', store_failures=true, alias='dq_activation_reconciliation') }}

  with this_mart as (
      select
          acquisition_cohort_month,
          count(*) as cohort_size,
          count_if(is_activated_30d) as activated_30d
      from {{ model }}
      where period_number = 0
      group by acquisition_cohort_month
  )

  select
      t.acquisition_cohort_month,
      t.cohort_size,
      a.cohort_size as expected_cohort_size,
      t.activated_30d,
      a.pct_2nd_order_within_30d * a.cohort_size as expected_activated_30d
  from this_mart t
  full outer join {{ ref('mart_activation') }} a
      on t.acquisition_cohort_month = a.acquisition_cohort_month
  where t.cohort_size is distinct from a.cohort_size
     or abs(t.activated_30d - a.pct_2nd_order_within_30d * a.cohort_size) > 0.5

{% endtest %}
