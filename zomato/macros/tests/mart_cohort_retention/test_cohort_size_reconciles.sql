{% test cohort_size_reconciles(model) %}
  {#
  Test: cohort_size (at period_number = 0) must equal the count of distinct customers whose first
  delivered order fell in that cohort month, per int_customer_order_sequence.

  Rationale: cohort_size is computed independently in this mart from the same backbone
  (int_customer_order_sequence) that mart_activation and mart_customer_rfm also derive from — if this
  drifts, cohort-based comparisons across marts would silently disagree with each other.

  Severity: error (grain/aggregation mismatch, not a data quality edge case).
  #}
  {{ config(severity='error', store_failures=true, alias='dq_cohort_size_reconciliation') }}

  with expected as (
      select
          acquisition_cohort_month,
          count(distinct customer_id) as expected_cohort_size
      from {{ ref('int_customer_order_sequence') }}
      where order_sequence = 1
      group by acquisition_cohort_month
  )

  select
      m.acquisition_cohort_month,
      m.cohort_size,
      e.expected_cohort_size,
      m.cohort_size - e.expected_cohort_size as variance
  from {{ model }} m
  inner join expected e
      on m.acquisition_cohort_month = e.acquisition_cohort_month
  where m.period_number = 0
    and m.cohort_size != e.expected_cohort_size

{% endtest %}
