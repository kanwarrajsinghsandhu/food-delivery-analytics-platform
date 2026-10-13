{% test mau_within_executive_summary(model) %}
  {#
  Test: platform-wide monthly MAU here (summed across acquisition cities) must not exceed
  mart_executive_summary.monthly_active_users for the same month.

  Rationale: this mart counts customers with a *delivered* order; mart_executive_summary counts any
  order status (incl. cancelled/refunded), so it's a superset and the two are expected to differ --
  but this one should never be larger.

  Severity: warn -- the two MAU definitions are known to differ by design (documented on both models),
  so a gap isn't a bug; exceeding it would be suspicious but shouldn't block the build of an executive
  mart that's owned separately.
  #}
  {{ config(severity='warn') }}

  with growth as (
      select activity_month, sum(mau) as mau_delivered
      from {{ model }}
      group by activity_month
  ),

  exec_summary as (
      select distinct
          date_trunc('month', order_date)::date as activity_month,
          monthly_active_users
      from {{ ref('mart_executive_summary') }}
  )

  select
      g.activity_month,
      g.mau_delivered,
      e.monthly_active_users,
      g.mau_delivered - e.monthly_active_users as excess
  from growth g
  inner join exec_summary e
      on g.activity_month = e.activity_month
  where g.mau_delivered > e.monthly_active_users

{% endtest %}
