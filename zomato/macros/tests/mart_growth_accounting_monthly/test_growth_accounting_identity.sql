{% test growth_accounting_identity(model) %}
  {#
  Test: for every (activity_month, acquisition_city), mau = new + retained + resurrected.

  Rationale: this is the defining identity of growth accounting -- every active customer is exactly one
  of new, retained or resurrected. If it breaks, the stacked MAU bar on the dashboard won't sum to the
  MAU tile next to it.

  Severity: error (arithmetic/classification bug, not a data quality edge case).
  #}
  {{ config(severity='error', store_failures=true, alias='dq_growth_accounting_identity') }}

  select
      activity_month,
      acquisition_city,
      mau,
      new_customers,
      retained_customers,
      resurrected_customers,
      mau - (new_customers + retained_customers + resurrected_customers) as variance
  from {{ model }}
  where mau != new_customers + retained_customers + resurrected_customers

{% endtest %}
