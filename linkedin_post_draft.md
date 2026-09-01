# LinkedIn Post — Draft 2 (Engineering breakdown: the audit system)

**Positioning:** engineering breakdown, not a project update. The reconciliation rule is the setup;
the three decisions *around* the test are the post. Per the revised strategy — hook with
engineering, prove with insight.

**Status:** unpostable until the finding is filled from a real run. See "The finding" below.

---

## What changed from Draft 1, and why

| Cut | Reason |
|---|---|
| The `dbt init` / profiles.yml anecdote | Beginner debugging story. Signals tutorial-following, not system design. |
| "Here's my arithmetic check" as the centrepiece | A row-level `a = b - c + d` test is table stakes. Nobody senior reads past it. |
| "Enterprise-scale" | Unearned on a small dataset, and it's the adjective that gets a post dismissed in one glance. |

| Added | Why it lands with senior readers |
|---|---|
| `store_failures` → failures as a queryable Snowflake table | Turns test output from a boolean into a dataset with history. This is what makes the finding possible at all. |
| `warn_if` / `error_if` thresholds | A data-quality SLO in version control. Most mid-level dbt users have never configured this. |
| Cross-grain roll-up test (`order_items` → `orders`) | Catches fan-out, dropped lines, double loads. This is the failure class that actually corrupts marts. |
| Carrying dimensions into the failure table | The reason the diagnostic queries are one step, not a re-derivation. |

---

## The finding — fill this before posting

The post has one slot, marked `[FINDING]`. It must come from the quarantine table, not from a
guess. Run the four queries in "Diagnostics" below, then write what is actually true.

**The claim you can make depends on which query answers:**

| What the data shows | What you are allowed to write |
|---|---|
| Variance as a % of subtotal is flat across value deciles | Proportional error — a rounding or percentage-application order issue. Say that. |
| Absolute variance is flat, % varies | A fixed component is missing or double-counted (delivery fee, a flat promo). Say that. |
| Failure rate lifts on one `payment_method` | Settlement or wallet-credit path applies after totals are logged. Say that, as a hypothesis. |
| Cumulative failures show a step change on a date | A pricing/tax config change shipped mid-dataset. Strongest story of the four. |
| No clustering anywhere, tiny variance | Rounding noise. Then the honest post is about the tolerance budget, not a finding — and that is still a good post. |

**Do not write a root cause you cannot show from a query.** "A microservice timed out under peak
load" is not observable from a batch CSV extract, and claiming it invites the one comment that sinks
the post. "The variance is proportional to order value, which points at where the discount is
applied in the sequence, not at the arithmetic" is observable, defensible, and reads as more senior
anyway.

---

## The post

> In a marketplace, "does the amount we recorded match what should have been charged" is a question
> finance asks constantly. When systems diverge — a promo engine, a tax calculator, and an order
> service updating independently — nothing crashes. The ledgers stay self-consistent. Someone finds
> the gap at month-end close.
>
> I've been building an ELT pipeline over a Zomato marketplace dataset — Azure Data Lake → Snowflake
> → dbt, medallion layout — and the part worth writing about isn't the architecture. It's what I
> made one test do to catch that gap upstream.
>
> The rule itself is trivial. Every order has to satisfy:
>
> sales_amount = subtotal − discount + delivery_fee + gst
>
> Three decisions turned that one-liner into an audit system.
>
> 1️⃣ The test writes its failures down.
> store_failures = true, so every failing row lands in a real Snowflake table instead of scrolling
> past in a run log. The test's output becomes a dataset with history rather than a boolean.
> Everything below only exists because of that one line of config.
>
> 2️⃣ The test has a budget, not a binary.
> severity: error, with warn_if: ">0" and error_if: ">500". Below the threshold the run warns and
> the marts still build. Above it, dbt fails and the GitHub Actions gate turns the PR red. That's a
> data-quality SLO living in version control — and it's the difference between a test a team
> respects and a test a team learns to rerun until it goes green.
>
> 3️⃣ The check that catches structural damage is one grain up.
> Row-level arithmetic only ever catches arithmetic. The one that matters is cross-grain:
> SUM(order_items.line_amount) per order, against orders.subtotal, plus a line-count check. That's
> what surfaces fan-out from a bad join, dropped line items and double-loaded batches — the failures
> that silently change every number downstream while every column-level test stays green.
>
> Then I stopped guessing and queried the quarantine table. The result: [FINDING_PERCENT]% of GMV
> was at risk of silent misstatement because [FINDING_CAUSE]. The rupee exposure: ₹[FINDING_AMOUNT].
>
> [HYPOTHESIS — one sentence, how you'd frame the cause to a senior engineer or finance]
>
> The takeaway I keep coming back to: the value wasn't catching bad maths. It was having somewhere
> bad rows accumulate, so an anomaly becomes something you can rank, trend and argue about — instead
> of a red X that someone reruns until it passes.
>
> 🔹 Bronze — ADLS blob storage → Snowflake COPY INTO, raw and untouched
> 🔹 Silver — explicit casts, snake_case, PK/FK tests, and the reconciliation macro
> 🔹 Gold — restaurant performance and retention marts, built only if Silver passes
>
> Genuine question for anyone running dbt in production: where do you draw the line between a test
> that blocks the deploy and one that only warns? I've seen both drawn badly.
>
> #DataEngineering #Snowflake #dbt #AnalyticsEngineering #SQL

~2,400 characters. Under LinkedIn's 3,000 limit with room for the finding.

---

## The code (slide 2)

```sql
-- macros/tests/test_order_total_reconciles.sql

{% test order_total_reconciles(model, column_name, tolerance=0.01) %}

  {{ config(
       severity       = 'error',
       warn_if        = '>0',
       error_if       = '>500',
       store_failures = true,
       alias          = 'dq_order_reconciliation'
  ) }}

  select
      order_id,
      restaurant_id,
      order_date,
      payment_method,
      {{ column_name }}                                              as recorded_total,
      subtotal - discount + delivery_fee + gst                       as expected_total,
      {{ column_name }} - (subtotal - discount + delivery_fee + gst) as variance
  from {{ model }}
  where abs({{ column_name }} - (subtotal - discount + delivery_fee + gst)) > {{ tolerance }}

{% endtest %}
```

Selecting the dimensions (not just `order_id`) is the whole trick — it makes the stored failure
table analysable on its own, so the diagnostics below are one query instead of a re-derivation.

```yaml
# models/staging/_staging.yml
      - name: sales_amount
        tests:
          - order_total_reconciles:
              arguments:
                tolerance: 0.01
```

```sql
-- tests/assert_order_items_roll_up_to_orders.sql   (singular test, cross-grain)

{{ config(severity = 'error', store_failures = true, alias = 'dq_grain_mismatch') }}

with items as (
    select order_id, sum(line_amount) as items_total, count(*) as line_count
    from {{ ref('stg_order_items') }}
    group by 1
)

select
    o.order_id, o.items_count, i.line_count,
    o.subtotal, i.items_total,
    o.subtotal - i.items_total as variance
from {{ ref('stg_orders') }} o
join items i using (order_id)
where abs(o.subtotal - i.items_total) > 0.01
   or o.items_count != i.line_count
```

---

## Diagnostics — run these, then write the finding

dbt lands stored failures in a `_dbt_test__audit` schema; `alias` gives the table a stable name.
Adjust the schema prefix to match your target.

```sql
-- 1. Is it material, or is it rounding?
select
    count(*)                     as failing_orders,
    round(sum(abs(variance)), 2) as total_variance_inr,
    round(avg(abs(variance)), 2) as avg_variance_inr,
    round(max(abs(variance)), 2) as worst_case,
    round(100.0 * count(*) /
          (select count(*) from zomato.staging.stg_orders), 2) as pct_of_orders
from zomato.staging_dbt_test__audit.dq_order_reconciliation;
```

```sql
-- 2. Does it cluster? Rank by failure RATE and lift vs. baseline, never by raw count.
with base as (
    select o.order_id, o.payment_method,
           iff(f.order_id is null, 0, 1) as failed
    from zomato.staging.stg_orders o
    left join zomato.staging_dbt_test__audit.dq_order_reconciliation f
           on o.order_id = f.order_id
)
select
    payment_method,
    count(*)                                            as orders,
    sum(failed)                                         as failures,
    round(100.0 * sum(failed) / count(*), 2)            as failure_rate_pct,
    round( (sum(failed) / count(*))
           / nullif(sum(sum(failed)) over () / sum(count(*)) over (), 0), 2) as lift_vs_baseline
from base
group by 1
order by lift_vs_baseline desc;
```

```sql
-- 3. Did it START on a date? A config change is a step, a systemic bug is a trend.
with base as (
    select o.order_date, iff(f.order_id is null, 0, 1) as failed
    from zomato.staging.stg_orders o
    left join zomato.staging_dbt_test__audit.dq_order_reconciliation f
           on o.order_id = f.order_id
)
select
    order_date,
    sum(failed) as failures,
    sum(sum(failed)) over (order by order_date
        rows between unbounded preceding and current row) as cumulative_failures
from base
group by 1
order by order_date;
```

```sql
-- 4. THE ONE THAT DECIDES THE STORY.
-- Flat variance_pct_of_subtotal  => proportional error (rounding / order of operations)
-- Flat avg_variance_inr          => a fixed component missing or double-counted
with f as (
    select f.order_id, o.subtotal, abs(f.variance) as variance,
           ntile(10) over (order by o.subtotal) as value_decile
    from zomato.staging_dbt_test__audit.dq_order_reconciliation f
    join zomato.staging.stg_orders o on f.order_id = o.order_id
)
select
    value_decile,
    count(*)                                                  as failures,
    round(avg(variance), 2)                                   as avg_variance_inr,
    round(100.0 * avg(variance / nullif(subtotal, 0)), 3)     as variance_pct_of_subtotal
from f
group by 1
order by value_decile;
```

Query 4 is also the best thing to drop into the comments when an engineer asks how you ruled out a
code bug — it discriminates between two hypotheses in one pass, which is a stronger signal than any
claim in the post body.

```sql
-- 5. BUSINESS IMPACT: Reconciliation exposure %.
-- What % of total GMV was at risk of silent misstatement?
select
    round(100.0 * sum(abs(variance)) / 
          (select sum(sales_amount) from zomato.staging.stg_orders), 3) as exposure_pct_of_gmv,
    round(sum(abs(variance)), 2) as total_variance_inr,
    count(*) as failing_orders
from zomato.staging_dbt_test__audit.dq_order_reconciliation;
```

This is the number that opens the post: "X% of GMV was at risk."

```sql
-- 6. BUSINESS IMPACT: Cross-grain overstatement amount (from the grain-mismatch test).
-- If items don't roll up to orders, what rupee amount would have inflated GMV?
select
    round(sum(greatest(0, items_total - subtotal)), 2) as potential_gmv_overstatement_inr,
    count(*) as orders_with_fan_out
from zomato.staging_dbt_test__audit.dq_grain_mismatch
where items_total > subtotal;
```

This is the answer to "what did we actually prevent": a rupee amount that would have been silently
added to revenue numbers.

---

## Carousel

| Slide | Asset | Where it comes from |
|---|---|---|
| 1 | Test-severity control flow: pass / warn / error and where failing rows go | `zomato-post-kit` artifact — draw once, it's not in any dbt docs screenshot |
| 2 | The macro, as committed | Real file, Phase 3 |
| 3 | Failed GitHub Actions run, PR gate red | Real run, Phase 5 — break it deliberately once |
| 4 | `dbt docs` lineage graph | Real screenshot, Phase 6 |

Slide 1 is deliberately *not* the lineage graph. Every dbt post has a lineage graph; the severity
branch is the thing the post is actually about and nobody screenshots it.

---

## Held in reserve for the comments

- If anyone calls it a tutorial dataset: "Small dataset, same discipline production pipelines run
  on. The point wasn't catching bugs — it was deciding that GMV risk is worth stopping a build over,
  and having that decision live in code."
- Why Snowflake over local Postgres: zero-copy clone for CI (a PR builds against a clone of prod,
  not a fixture), and separated compute so the CI warehouse can't contend with anything else.
- Query 4 above, verbatim, when someone asks how you separated a proportional error (order of
  operations) from a fixed component (missing fee). This discriminates the two in one pass.
- Queries 5 and 6 together, when someone asks how you went from "40 rows failed" to "X% of GMV was
  at risk": the first turns a row count into a percentage; the second shows the rupee amount from the
  cross-grain check. These are the two numbers the post is actually built on.
