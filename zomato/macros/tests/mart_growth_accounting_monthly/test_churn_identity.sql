{% test churn_identity(model) %}
  {#
  Test: for every acquisition_city, mau(t-1) = retained(t) + churned(t), comparing each month's
  outflow against the PREVIOUS month's own mau row (not against prior_month_mau, which is derived from
  the same flag and would make this check circular).

  Rationale: every customer active last month is either still active (retained) or not (churned) this
  month. A mismatch means the customer-month spine dropped or duplicated rows between months, or a
  customer's acquisition_city changed between months (it must be fixed per customer).
  The dataset's first month has no prior month, so it's naturally excluded by the inner join.

  Severity: error (cross-month grain inconsistency).
  #}
  {{ config(severity='error', store_failures=true, alias='dq_churn_identity') }}

  select
      curr.activity_month,
      curr.acquisition_city,
      prev.mau as prior_month_mau_actual,
      curr.retained_customers,
      curr.churned_customers,
      prev.mau - (curr.retained_customers + curr.churned_customers) as variance
  from {{ model }} curr
  inner join {{ model }} prev
      on prev.acquisition_city = curr.acquisition_city
      and prev.activity_month = dateadd(month, -1, curr.activity_month)
  where prev.mau != curr.retained_customers + curr.churned_customers

{% endtest %}
