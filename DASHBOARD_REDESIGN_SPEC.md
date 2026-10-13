# Streamlit Dashboard — Redesign Specification

**Version:** 1.0 · **Date:** 2026-09-29 · **Scope:** UI/UX + visual/analytical redesign of `streamlit_dashboard/`
**Constraint honoured:** no new dbt marts. Every visual below is served by an existing mart, an existing
staging model, or an in-query aggregation over one of them. One **bug fix** to an existing mart is
recommended (§2.6) — that is a correction, not a new model.

> **All numbers in this document were verified live against Snowflake on 2026-09-29**, not inferred from
> model comments. Where a figure contradicts existing documentation, the live value is used and the
> discrepancy is called out.

---

## Table of contents

| Part | Section |
|---|---|
| 0 | [Executive summary — what changes and why](#part-0--executive-summary) |
| 1 | [Verified data reality](#part-1--verified-data-reality) |
| 2 | [Defects found in the current dashboard](#part-2--defects-found-in-the-current-dashboard) |
| 3 | [Information architecture & navigation](#part-3--information-architecture--navigation) |
| 4 | [Design system — colour, typography, spacing](#part-4--design-system) |
| 5 | [Filters & interaction model](#part-5--filters--interaction-model) |
| 6 | [Page 1 — Marketplace Health](#part-6--page-1--marketplace-health) |
| 7 | [Page 2 — Customer Value](#part-7--page-2--customer-value) |
| 8 | [Page 3 — Retention & Activation](#part-8--page-3--retention--activation) |
| 9 | [Page 4 — Method & Data Quality](#part-9--page-4--method--data-quality) |
| 10 | [Optional Page 5 — Restaurant & Food: verdict](#part-10--optional-restaurant--food-page-verdict) |
| 11 | [Metric dictionary — exact formulas](#part-11--metric-dictionary) |
| 12 | [Responsive behaviour](#part-12--responsive-behaviour) |
| 13 | [What NOT to show](#part-13--what-not-to-show) |
| 14 | [Implementation notes](#part-14--implementation-notes) |

---

# Part 0 — Executive summary

## 0.1 The redesign is driven by six findings, not by taste

Profiling the marts surfaced six facts that change *what the dashboard should say*, not just how it
looks. These drive nearly every decision below.

| # | Finding | Verified evidence | Design consequence |
|---|---|---|---|
| **F1** | **The headline activation KPIs are wrong by ~35 points.** The current page averages per-cohort percentages unweighted, across 30 cohorts whose sizes span 63,144 → 3 customers. | Unweighted 30-day activation = **29.49%**. Customer-weighted = **64.82%** (confirmed two ways: weighted from `mart_activation`, and recomputed at customer grain from `mart_retention_diagnostic`). Median days to 2nd order: shown **58.8**, actual **18**. | Every cohort-grain rate must be **customer-weighted**. §2.1, §11.3 |
| **F2** | **Acquisition is effectively one event.** The Jan-2024 cohort is 63,144 of 99,963 customers (63.2%). 15 of 30 cohorts have <100 customers; 10 have <30. | Cohort sizes: 63,144 / 16,359 / 8,182 / 4,008 / 2,586 / 1,573 / 994 … / 3. | The heatmap must **default to the 6 large cohorts** and **suppress cells where n<100**. The current default (`cohorts[-12:]`) shows the 12 *smallest* cohorts — i.e. almost pure noise. §2.2, §8 |
| **F3** | **First-order experience has no association with reordering. It is a null result.** | 30-day reorder rate by delivery-speed bucket: 64.52 / 64.77 / 64.83 / 65.17% (spread **0.65pp**). By rating: 64.68–64.95% (spread **0.27pp**). By first-order discount: 64.78% vs 64.85% (**0.06pp**). | Auto-scaled bar axes currently make a 0.65pp difference look like a large effect. Redesign uses **fixed 0–100% axes with a reference line** and states the null result explicitly. This is a *strength* in interview terms. §2.3, §8 |
| **F4** | **RFM's M dimension is redundant.** AOV is flat (~$7.24) across every segment, so monetary value is ~a linear restatement of frequency. | `corr(frequency_orders, monetary_value_cad) = 0.9975`. Segment AOV range: $7.09–$7.41 across all 8 segments. | The proposed *Frequency vs Monetary* hero scatter would render a near-perfect diagonal — no information. Replaced with a **value-concentration hero** + a **Recency × Frequency** density plane (`corr(R,F) = −0.225`, real structure). §2.4, §7 |
| **F5** | **`is_late_delivery_proxy` splits the distribution at its own median.** Delivery time is a symmetric bell over 8–87 min, median 31, mean 31.07. The 30-minute cut yields a 51.81% "late" rate. | 4,740,847 late ÷ 9,150,122 delivered = **51.81%**. | "Late Delivery %" is not an operations metric here — it is "which side of the median". Demoted from KPI; replaced by a **delivery-time distribution with the threshold drawn on it**. §2.5, §6 |
| **F6** | **Item-level analysis is impossible; restaurant-level analysis has no signal.** `stg_food`/`stg_menu` keys are text (`'fd0'`); `fct_order_items.food_id` is numeric — **zero overlap**. Restaurant metrics are flat across volume tiers. | 0 of 371,561 menu food_ids match any of 369,279 item food_ids. Top restaurant = **0.023%** of GMV; GMV/order 6.26–6.89 and avg rating 4.1448–4.1460 across all volume tiers; `corr(dim rating, actual order rating) = 0.0009`. | **Do not build a Restaurant & Food page.** Restaurant context becomes a detail lookup inside Page 1. §10 |

## 0.2 What the redesign does

| | Before | After |
|---|---|---|
| **Pages** | 3 analytical pages | 3 analytical pages + 1 **Method & Data Quality** reference page |
| **Navigation** | Streamlit default file list; `app.py` immediately redirects away | Named sidebar sections with a persistent context header, active-filter chips, and a reset control |
| **Filters** | Page-local date inputs on Page 1 only; a metric radio *inside* a chart card | One **global filter bar** (date, city, cuisine, outcome) in the sidebar, shared across pages via `st.session_state` |
| **Visual count** | 15 visuals, several redundant | 18 elements across 4 pages, each with a stated business question, arranged Overview → Trend → Diagnosis → Detail |
| **Aggregation** | Unweighted means over cohorts and days (5 instances) | Weighted/ratio-of-aggregates throughout, formulas documented per metric |
| **Colour** | Plotly `category10` defaults; `RdYlGn` diverging used for a magnitude scale; 8 categorical hues on a scatter | One validated design system: 1-hue sequential for magnitude, ≤3 validated hues for identity, reserved status tokens for order outcome |
| **Data transfer** | `SELECT *` pulls ~100k rows per mart into pandas, then aggregates client-side | Aggregation pushed into SQL; only presentation-grain rows cross the wire |
| **Caveats** | Inline `st.warning` blocks competing with the charts | Short per-visual footnotes + one consolidated Method page |
| **Charts removed** | — | 2 donuts, 1 dual-axis chart, 2 value-ramp-on-nominal bars, 1 redundant scatter (§13) |

---

# Part 1 — Verified data reality

## 1.1 Platform shape (verified 2026-09-29)

| Measure | Value |
|---|---|
| Orders | 10,000,000 |
| Date span | 2024-01-01 → 2026-06-30 (912 days, 30 months) |
| Delivered / Cancelled / Refunded | 9,150,122 (91.50%) / 599,251 (5.99%) / 250,627 (2.51%) |
| GMV (delivered, CAD) | 66,272,550.64 |
| AOV (CAD) | 7.2428 |
| Customers (order side) | 99,969 |
| Customers in `dim_customer` | 90,462 · scored in `mart_customer_rfm`: **90,428** |
| Restaurants | 148,541 (100% joinable to `stg_restaurants`) |
| Cities | 552 · top-10 = 57.46% of orders · top-20 = 67.37% |
| Cuisine tag strings | 2,133 distinct **comma-delimited combinations** |
| Orders rated | 64.07% of all · 70.02% of delivered · mean rating 4.145 |
| Orders discounted | 35.01% · total discount 6,339,786.52 CAD (**9.57% of GMV**) |
| Delivery time | 8–87 min · median 31 · mean 31.07 |
| Items per order | 1–6 (mean 2.30), from 22,998,179 item rows covering all 10M orders |

**Growth story (clean and strong):** monthly orders 190,767 → 485,479; GMV 1.26M → 3.22M CAD; MAU
65,459 → 85,613; monthly retention 75.3% → 90.0%. All four move up together over 30 months.

> **Month-length artefact:** monthly bars/lines are affected by 28/30/31-day months (Feb-2026 = 402,771
> vs Jan-2026 = 441,277 is calendar length, not a downturn). Specified treatment in §6, V1.1.

## 1.2 Metric classification

Every metric surfaced in the UI carries one of four badges. The badge appears in the Method page table
and, where it changes interpretation, as a one-line footnote under the visual.

### ✅ Measured — directly computed from available fields

GMV, orders, delivered/cancelled/refunded counts, AOV, DAU, discount amount and rate, delivery-time
distribution, customer rating distribution, order counts per customer, recency, frequency, monetary
value, cohort sizes, activation windows, items per order, city and restaurant order/GMV totals.

### ⚠️ Proxy — stands in for a measurement the source data does not contain

| Metric | Why it is a proxy | How the UI must present it |
|---|---|---|
| `is_late_delivery_proxy` | No promised-ETA/SLA field exists. Fixed 30-min absolute threshold. **And it sits at the distribution's median (F5)**, so the resulting 51.81% is not an ops signal. | Never as a headline KPI. Show the **distribution** with the threshold drawn as an annotated rule. Footnote: "30-minute proxy threshold — not a promised-delivery SLA." |
| `nps_score_proxy` | Built from 1–5 stars (5=promoter, 4=passive, ≤3=detractor), not a 0–10 recommend question. | Optional, Method page only. Excluded from the analytical pages — a proxy NPS adds no decision value next to the raw rating distribution. |
| `monthly_active_users` | Calendar-month active, not rolling 30-day. Repeated across every day of the month. | Label axis/tile "Monthly active customers (calendar month)". Never average it across days (§2.1). |
| `repeat_restaurant_rate` | **Structurally meaningless in this dataset** — max observed 1.58e-05 vs 6.7e-06 random baseline (1/148,541). Indistinguishable from chance. | **Excluded entirely.** Documented as a null/void metric on the Method page. |

### 🔬 Observational — association only, no causal claim

`mart_retention_diagnostic` buckets (delivery speed, rating, first-order discount) → reorder rate;
`mart_basket_discount` discount-dependency segments → value/retention. All three are **null results**
(F3) and the discount comparison is additionally **mechanically confounded** by order count (§2.4).

### 🧮 Derived — computed in the dashboard query from existing fields

Customer-weighted activation rates; ratio-of-aggregates AOV; delivery-time histogram bins;
cuisine tag split via `SPLIT_TO_TABLE`; share-of-customers/share-of-value by segment; restaurant
volume tiers; city performance matrix columns; value deciles. **No new marts.**

### ⛔ Not possible with current data — do not attempt

| Wanted | Blocker |
|---|---|
| Dish / item name analysis, veg vs non-veg mix, menu-price vs sold-price | `stg_food.food_id` and `stg_menu.food_id` are TEXT (`'fd0'`, `'fd669322'`); `fct_order_items.food_id` is NUMBER (0–1,048,562). **Zero key overlap.** `fct_order_items` supports basket *size* only. |
| Restaurant quality benchmarking | `stg_restaurants.rating` populated for only 61,441/148,541 (41.4%) and **uncorrelated** with actual order ratings (r = 0.0009, n = 35,748). |
| Review text / sentiment | `stg_reviews` covers 295,541 of 10M orders (**2.96%**) and adds only a free-text `comment`. `customer_rating` on `fct_order_sales` already covers 6.4M orders. |
| True SLA breach, real NPS, rolling 30-day MAU, predictive LTV, causal discount effect | Not in source data / out of Phase A scope (Phase B). |

---

# Part 2 — Defects found in the current dashboard

These are specific, reproducible problems in the code as it stands. Fixing them is the analytical half
of the redesign.

## 2.1 Unweighted means over unequal groups (5 instances) — **highest severity**

| File | Line | Current code | Problem | Correct value |
|---|---|---|---|---|
| `3_retention_activation.py` | 42 | `activation_df["PCT_2ND_ORDER_WITHIN_7D"].mean()` | Unweighted mean over 30 cohorts sized 63,144→3 | **29.35%** shown as 8.76% |
| `3_retention_activation.py` | 46 | `…WITHIN_14D"].mean()` | same | **44.82%** shown as 15.40% |
| `3_retention_activation.py` | 50 | `…WITHIN_30D"].mean()` | same | **64.82%** shown as 29.49% |
| `1_business_health.py` | 63 | `df_filtered["AOV_CAD"].mean()` | Mean of daily AOVs, not GMV ÷ orders | 7.2428 vs 7.2414 (benign here, method still wrong) |
| `1_business_health.py` | 67, 71 | `MONTHLY_ACTIVE_USERS.mean()`, `MONTHLY_RETENTION_RATE.mean()` | Day-weighted mean of a month-repeated value | MAU: latest 84,972 / peak 85,613, shown as 77,372. Retention: latest 89.2%, shown as 84.6% |

**Rule for the redesign:** any percentage or average over groups of unequal size is computed as a
**ratio of aggregates** (`SUM(numerator) / SUM(denominator)`), never as `AVG(rate)`. Every formula in
§11 is written this way.

## 2.2 The cohort heatmap defaults to the noisiest possible view

`3_retention_activation.py:63` — `default=cohorts[-12:]`. The last 12 cohorts are the **smallest**
(n = 161, 127, 122, 77, 67, 52, 38, 44, 26, 28, 18, 18, 16, 6, 6, 14, 7, 3). At n=16, retention swings
12.5% → 43.75% → 12.5% between adjacent periods — that is sampling noise rendered as a red/green
signal. Fix: default to cohorts with n ≥ 1,000 (6 cohorts), suppress cells below n = 100, and show
`cohort_size` beside every cohort label.

## 2.3 Null results presented as findings

`3_retention_activation.py:167–217` renders delivery-speed and rating reorder rates as horizontal bars
on a **Plotly auto-scaled axis**. With values spanning 64.52–65.17%, the axis auto-fits to ~64–65% and a
**0.65pp difference fills the full bar width**, reading as a dramatic effect. Same for rating (0.27pp).
Fix: `range=[0,1]` on the value axis, a reference line at the pooled rate (64.82%), and an explicit
"no material difference" verdict in the subheading.

## 2.4 Discount-dependency segments are mechanically confounded

| Segment | Customers | Avg total orders | Avg value (CAD) | 30-day reorder |
|---|---|---|---|---|
| Occasional Discount User | 94,632 | **95.7** | 693.29 | 66.8% |
| Discount-Reliant | 4,777 | **19.0** | 130.48 | 31.3% |
| Full-Price | 554 | **4.4** | 35.28 | 9.4% |

Platform discount rate is 35.01%. A customer with 96 orders essentially *cannot* be "never discounted"
(0.65⁹⁶ ≈ 0), so **segment membership is determined by order count**, and the value/retention gradient
is an artefact of exposure, not of discount responsiveness. The current table presents it as a value
comparison. Fix: add `avg_total_orders` as an adjacent column so the confound is visible in the same
table, and state it in the subheading. Comparison *within* frequency bands is the honest framing.

## 2.5 `Late Delivery %` used as a health metric

See F5. A 51.81% rate reads alarming and means nothing. Demoted from KPI to a distribution visual.

## 2.6 Recommended mart bug fix — `rating_bucket` swallows NULLs

`mart_retention_diagnostic.sql:60–65`: the `else` branch of the rating CASE catches **NULL** ratings.

| `rating_bucket` | Customers | of which NULL rating |
|---|---|---|
| `Poor (<3.0)` | 31,225 | **30,039 (96.2%)** |

So "Poor" is 96% *unrated* first orders and only 1,186 genuinely low-rated ones. Also, because
`customer_rating` is an integer 1–5, the continuous-looking labels actually mean: `Excellent (4.5-5.0)`
= exactly 5★, `Good (4.0-4.5)` = 4★, `Fair (3.0-4.0)` = 3★, `Poor (<3.0)` = 1–2★ **+ unrated**.

**Recommended fix** (one line, existing mart — not a new model):

```sql
case
    when f.first_order_rating is null then 'Unrated'
    when f.first_order_rating = 5 then '5 stars'
    when f.first_order_rating = 4 then '4 stars'
    when f.first_order_rating = 3 then '3 stars'
    else '1-2 stars'
end as rating_bucket
```

This changes `accepted_values` in `_customer.yml` accordingly. **If the mart is not changed**, the
dashboard must exclude NULL-rated customers in the query (`where first_order_rating is not null`) and
relabel the buckets as star counts — never display "Poor" for a missing rating.

## 2.7 Client-side aggregation of ~100k-row pulls

`SELECT *` is issued against `MART_CUSTOMER_RFM` (90,428 rows), `MART_BASKET_DISCOUNT` (99,963),
`MART_RETENTION_DIAGNOSTIC` (99,963) and `DIM_CUSTOMER` (90,462) — then `groupby` runs in pandas. Four
pulls ≈ 380k rows per cold page load. All of these aggregate to ≤ 25 presentation rows. Push the
`GROUP BY` into Snowflake (§14.3).

## 2.8 Minor

- `1_business_health.py:159–207` — **dual-axis chart** (GMV vs late-delivery rate). Two arbitrary scales
  invent a visual correlation. Remove (§13).
- `1_business_health.py:82–87` — a metric-selector radio **inside** a chart card; filters belong in one
  row above everything they scope.
- Order-status and gender **donuts** — part-to-whole at a glance for ≤6 segments only; both are better
  as a bar or a trend.
- `color="ORDER_COUNT"` on the payment bars and `color="Customer Count"` on the occupation/income bars
  double-encode bar length as hue, burning the only free channel.
- `RdYlGn` on the cohort heatmap is a **diverging** scale applied to a **magnitude** measure; retention
  has no meaningful zero-point or polarity. Use a single-hue sequential ramp.
- `app.py` exists only to `st.switch_page` away, so the sidebar's first entry is dead weight.
- GMV reconciles to 66,272,550.64 via `mart_executive_summary` but 66,295,518.20 direct from
  `fct_order_sales` — a **0.035%** gap from `inr_to_cad(SUM(...))` vs `SUM(inr_to_cad(...))` rounding.
  Harmless, but pick one source per number and note it (§11.1).

---

# Part 3 — Information architecture & navigation

## 3.1 Page set

| # | Page | Business question | Primary user |
|---|---|---|---|
| 1 | **Marketplace Health** | What is happening across the marketplace, and is it healthy? | Exec / GM — weekly review |
| 2 | **Customer Value** | Where is customer value concentrated, and what drives it? | Growth / CRM lead |
| 3 | **Retention & Activation** | Where do customers drop off, and what is associated with coming back? | Retention analyst — the project's central storyline |
| 4 | **Method & Data Quality** | Can I trust this number, and how was it computed? | Anyone questioning a figure; interviewers |

Page 4 is the highest-leverage addition: it removes caveat clutter from the analytical pages while
*strengthening* the analytical-integrity story, and it costs no new data work.

## 3.2 Navigation mechanism

**Sidebar navigation via `st.navigation` + `st.Page`** (grouped sections), not the implicit `pages/`
directory listing.

```python
# app.py  — becomes the real entry point, not a redirect
nav = st.navigation({
    "Overview":  [st.Page("views/marketplace_health.py", title="Marketplace Health", icon=":material/insights:")],
    "Customers": [st.Page("views/customer_value.py",     title="Customer Value",     icon=":material/group:")],
    "Retention": [st.Page("views/retention.py",          title="Retention & Activation", icon=":material/replay:")],
    "Reference": [st.Page("views/method.py",             title="Method & Data Quality",  icon=":material/rule:")],
})
render_global_filters()   # sidebar, below nav — shared by all pages
nav.run()
```

Why this over the alternatives:

| Option | Verdict |
|---|---|
| **Sidebar page nav** | ✅ Chosen. Persistent, shows all four destinations at once, leaves the full main column for content, and is the only place a *global* filter panel can live without repeating per page. |
| Top nav / `st.tabs` as primary | ❌ Tabs lose state awkwardly, don't scale past ~4 items, and consume the prime above-the-fold band that KPIs need. |
| Tabs *within* a page | ✅ Used sparingly — only for the Method page's reference tables. |
| `st.expander` for deep dives | ✅ Used for detail/lookup sections only, never to hide a caveat that changes interpretation. |
| Drill-down sub-pages | ❌ Rejected. With 552 cities and 148,541 restaurants and no per-entity signal (F6), a drill-down page would be a lookup table with a URL. An in-page expander does the same job. |

## 3.3 The five orientation questions, answered on every page

| Question | Mechanism |
|---|---|
| Where am I? | Sidebar item highlighted; page title `H1`; section label above it |
| What does this page represent? | One-sentence subtitle under the title, always present |
| What filters are active? | **Context chip row** directly under the subtitle: `Period: Jan 2024 – Jun 2026 · City: All (552) · Cuisine: All · Outcome: Delivered` |
| How do I get back to the overview? | Sidebar "Overview → Marketplace Health" is always the first entry |
| Where can I investigate further? | Each page's final section is a detail expander; footnotes link to **Method & Data Quality** |

---

# Part 4 — Design system

## 4.1 Colour

Base palette is the validated reference instance from the `dataviz` skill. **Every subset below was run
through `scripts/validate_palette.js`** — results recorded, not assumed.

### Roles

| Role | Light | Dark | Used for |
|---|---|---|---|
| Series 1 (primary) | `#2a78d6` | `#3987e5` | GMV, the main line in any single-series chart, selected state |
| Series 2 | `#eb6834` | `#d95926` | The one supporting series (e.g. share-of-value vs share-of-customers) |
| Series 3 | `#1baf7a` | `#199e70` | Third identity slot only (max 3 on any scatter — see validation note) |
| Sequential ramp | blue `#cde2fb` → `#0d366b` | same steps | Cohort retention, density heatmaps, matrix conditional fills |
| Ordinal ramp (3-step) | `#86b6ef` → `#2a78d6` → `#104281` | — | 7/14/30-day activation windows (ordered, not nominal) |
| Reference / benchmark rule | `#898781` | `#898781` | Pooled-average lines, the 30-min threshold rule |
| Status: good | `#0ca30c` | `#0ca30c` | Delivered |
| Status: warning | `#fab219` | `#fab219` | Refunded |
| Status: critical | `#d03b3b` | `#d03b3b` | Cancelled |
| Neutral / suppressed | `#e1e0d9` | `#2c2c2a` | Cells below minimum sample size |
| Chart surface | `#fcfcfb` | `#1a1a19` | — |
| Primary ink | `#0b0b0b` | `#ffffff` | Values, titles |
| Secondary ink | `#52514e` | `#c3c2b7` | Subheadings, legends |
| Muted ink | `#898781` | `#898781` | Axis labels, footnotes |
| Gridline | `#e1e0d9` | `#2c2c2a` | Solid hairline, one shade off surface — never dashed |

### Validation results (run 2026-09-29)

| Subset | Mode | Result |
|---|---|---|
| `#2a78d6, #eb6834` (2-series, adjacent) | light | **ALL PASS** — CVD ΔE 24.7, normal ΔE 33.6, contrast ≥3:1 |
| `#3987e5, #d95926` | dark | **ALL PASS** — CVD ΔE 26.8, normal ΔE 31.8 |
| `#2a78d6, #eb6834, #1baf7a` (3-series, **all-pairs** — scatter/bubble) | light | PASS with one **WARN**: `#1baf7a` contrast 2.74:1 → **relief required: direct labels + table view** |
| same, dark steps | dark | **ALL PASS** — worst all-pairs CVD ΔE 9.4 |
| `#86b6ef, #2a78d6, #104281` (ordinal) | light | **ALL PASS** — monotone L, ΔL gaps ≥0.06, light end 2.06:1, hue spread 3° |

### Hard rules

1. **Maximum 3 identity hues on any scatter/bubble/density chart.** The 8-slot palette only clears the
   all-pairs gate for its first three slots. This is why the 8-segment RFM scatter is replaced — the
   palette *cannot* safely carry 8 categories in that form. Beyond 3: fold to "Other", facet, or move
   to a matrix.
2. **Sequential = one hue, light→dark.** Never `RdYlGn` for a magnitude measure.
3. **Diverging only where there is a true midpoint** — nothing in this dashboard qualifies, so no
   diverging scale is used anywhere.
4. **Colour follows the entity, never the rank.** `Delivered` is `#0ca30c` on every page, in every
   chart, whatever the sort order. Filtering out a series never repaints the survivors.
5. **Status tokens are reserved.** `good/warning/critical` mean order outcome only, never "series 4",
   and always ship with a text label (on light surface `#fab219` is sub-3:1, so the label is the
   mitigation, not decoration).
6. **No value-ramp on nominal categories.** One series → one colour for every bar.
7. **Text wears ink tokens, never the series colour.**

## 4.2 Typography

Single family: `system-ui, -apple-system, "Segoe UI", sans-serif`. No display or serif face.

| Element | Size / weight / colour | Notes |
|---|---|---|
| Page title (H1) | 30px / 650 / primary ink | One per page, sentence case |
| Page subtitle | 15px / 400 / secondary ink | One sentence, always present |
| Context chip row | 13px / 500 / muted ink | Monospace-ish tabular feel via `tabular-nums` |
| Section heading (H2) | 20px / 600 / primary ink | Preceded by 40px space, hairline rule above |
| Visual heading (H3) | 15px / 600 / primary ink | Directly above the chart, no colon |
| Visual subheading | 13px / 400 / secondary ink | What it shows + why it matters, ≤ 2 lines |
| KPI value | 34px / 600 / primary ink · **proportional figures** | Never `tabular-nums` at display size |
| KPI label | 12px / 500 / muted ink, letter-spacing 0.02em | Acronyms spelled out on first use |
| KPI comparison | 12px / 500 / status or muted | Only when the comparison is meaningful |
| Axis ticks / table cells | 12px / 400 / muted ink · **`tabular-nums`** | Vertical alignment matters here |
| Footnote / caveat | 12px / 400 / muted ink | Italic reserved for proxy/null-result flags |
| Tooltip | 12px / 400 | ≤ 4 lines, label-value pairs |

Avoid: bold runs longer than a few words, more than two weights in one block, all-caps beyond KPI labels.

## 4.3 Spacing

An 8px base scale. Streamlit needs a small CSS injection to hit these reliably.

| Token | Value | Applied to |
|---|---|---|
| `--sp-1` | 8px | Inside KPI cards (label→value gap); chart title→plot |
| `--sp-2` | 16px | **Between KPI cards**; between a visual heading block and its plot |
| `--sp-3` | 24px | **Between charts in the same row** (horizontal gutter) |
| `--sp-4` | 32px | Between rows of visuals inside one section |
| `--sp-5` | 48px | **Between major sections** (with a hairline rule) |
| Page margin | 32px left/right at ≥1400px; 24px at 1100–1400px; 16px below | `.block-container` padding |
| Page top padding | 24px | Reduced from Streamlit's default ~96px, which wastes the fold |
| Chart internal padding | `l=56, r=24, t=8, b=48` | `t=8` because the title lives in HTML above, not in Plotly |
| Filter row spacing | 16px between controls, 24px below the row | Sidebar |
| Table | 8px cell padding, 32px above/below, header hairline only | No vertical rules, no zebra striping |
| KPI card | min-height 104px, 16px internal padding, 1px hairline ring, 8px radius | Equal heights across the row |

```css
/* utils/style.py — injected once per page via st.markdown(..., unsafe_allow_html=True) */
:root{--sp-1:8px;--sp-2:16px;--sp-3:24px;--sp-4:32px;--sp-5:48px;
      --ink-1:#0b0b0b;--ink-2:#52514e;--ink-3:#898781;--rule:#e1e0d9;--surface:#fcfcfb;}
.block-container{padding-top:var(--sp-3);padding-bottom:var(--sp-5);
                 max-width:1560px;padding-left:var(--sp-4);padding-right:var(--sp-4);}
div[data-testid="stHorizontalBlock"]{gap:var(--sp-3);}          /* chart gutter */
div[data-testid="stMetric"]{background:var(--surface);border:1px solid var(--rule);
  border-radius:8px;padding:var(--sp-2);min-height:104px;}
div[data-testid="stMetricValue"]{font-size:34px;font-weight:600;font-variant-numeric:proportional-nums;}
div[data-testid="stMetricLabel"]{font-size:12px;font-weight:500;color:var(--ink-3);letter-spacing:.02em;}
.section-rule{border-top:1px solid var(--rule);margin:var(--sp-5) 0 var(--sp-4);}
.viz-h{font-size:15px;font-weight:600;color:var(--ink-1);margin:0 0 4px;}
.viz-sub{font-size:13px;color:var(--ink-2);margin:0 0 var(--sp-2);}
.viz-note{font-size:12px;color:var(--ink-3);margin:var(--sp-1) 0 0;}
.chips{font-size:13px;font-weight:500;color:var(--ink-3);font-variant-numeric:tabular-nums;
       margin:var(--sp-1) 0 var(--sp-4);}
@media (prefers-color-scheme:dark){:root{--ink-1:#fff;--ink-2:#c3c2b7;--rule:#2c2c2a;--surface:#1a1a19;}}
```

**Anti-patterns to avoid** (all present today): charts flush against each other; unequal KPI card
heights; Plotly titles fighting HTML headings; a table tall enough to fill the viewport; more than
four visuals visible without scrolling.

---

# Part 5 — Filters & interaction model

## 5.1 Global filters (sidebar, persist across pages via `st.session_state`)

| Filter | Control | Select | Default | "All"? | Scopes | Notes |
|---|---|---|---|---|---|---|
| **Date range** | `st.date_input` (range) | range | 2024-01-01 → 2026-06-30 (full span) | n/a | Pages 1, 2, 3 | Presets alongside: *Full history · Last 12 months · Last 6 months · Last 90 days*. Full history is the default because cohort analysis is meaningless on a truncated window. |
| **City** | `st.multiselect` | multi | All (empty = all 552) | ✅ | Pages 1, 2 | Options listed as **top 20 by order volume** (67.4% of orders) plus a searchable long tail. Not applied to Page 3 — see §5.3. |
| **Cuisine tag** | `st.multiselect` | multi | All | ✅ | Page 1 only | Operates on **split tags**, not the 2,133 raw combination strings. Footnote: an order tagged `North Indian,Chinese` counts under both. |
| **Order outcome** | `st.segmented_control` | single | `Delivered` | ✅ (`All`) | Page 1 only | Default `Delivered` because GMV/AOV are defined on delivered orders. Switching to `All` re-scopes counts, and the GMV tile shows "—" with a note rather than a wrong number. |
| **Reset filters** | `st.button` ("Reset all filters") | — | — | — | Global | Clears `st.session_state` filter keys back to defaults. Present whenever ≥1 filter is off-default. |

**Why no more than these four:** each answers a question a reviewer actually asks ("is growth
broad-based or one city?", "does this hold for delivered orders only?"). A segment filter is *not*
global — it belongs to Page 2, where segments exist.

## 5.2 Page-specific filters

| Page | Filter | Control | Default | Scopes |
|---|---|---|---|---|
| 2 | RFM segment | `st.multiselect` | All 8 | The segment matrix + concentration hero (not the KPI row, which stays platform-level for comparison) |
| 3 | Cohort selector | `st.selectbox` | `2024-01` (largest, n=63,144) | The single-cohort retention curve only |
| 3 | Minimum cohort size | `st.select_slider` (100 / 500 / 1,000 / 5,000) | **100** | Cell suppression in the heatmap + which cohorts appear |
| 3 | Experience dimension | `st.radio` (horizontal, above the row) | Show all three | The null-result panel — above the charts, never inside a card |

## 5.3 Deliberate filter exclusions

- **City/cuisine are not applied to Page 3.** Cohort membership is defined by a customer's *first
  order*; filtering orders by city retroactively redefines cohorts and silently changes cohort sizes.
  The page states: "Cohort analysis uses the full platform population; city and cuisine filters do not
  apply here." This is an integrity decision, not an omission.
- **No restaurant filter.** 148,541 options with no per-entity signal (F6).
- **No date filter on Page 2's RFM metrics.** Recency/frequency/monetary are lifetime measures anchored
  to `recency_anchor_date` (2026-06-30); a date filter would imply they recompute, which they do not.
  Stated in the page subtitle.

## 5.4 Interaction rules

| Element | Controls | Updates | Reset | Default | Discoverable? |
|---|---|---|---|---|---|
| Global filter bar | Date, city, cuisine, outcome | All visuals on the active page | "Reset all filters" | Full history, All, All, Delivered | Yes — sidebar, labelled, above the fold |
| Context chips | Nothing (read-only) | — | — | Reflects live state | Yes — mirrors filter state in words |
| Chart hover | Tooltip only | — | — | Off | Yes — crosshair on lines, per-mark on bars/cells |
| Cohort selectbox | Which cohort's curve is drawn | V3.2 only | Back to `2024-01` | `2024-01` | Yes — labelled, directly above the chart |
| Min-cohort-size slider | Suppression threshold | V3.1 + V3.2 cohort list | Back to 100 | 100 | Yes — labelled with its consequence |
| Segment multiselect | Which segments appear | V2.1, V2.4 | Back to all 8 | All 8 | Yes |
| Table sort | Row order | That table | Click again | GMV desc | Yes — native `st.dataframe` |
| Detail expanders | Section visibility | Contents | Collapse | Collapsed | Yes — labelled with what's inside |

**No cross-filtering by clicking a mark.** Streamlit's rerun model makes click-to-filter slow and
non-obvious, and with one filter row already scoping everything it would create two competing filter
states. Hover reads values; the filter row changes scope. That boundary stays crisp.

**No skeleton flash on refetch:** all queries are `@st.cache_data(ttl=3600)`; on re-filter, hold the
previous render rather than dropping to a spinner.

---

# Part 6 — Page 1 — Marketplace Health

## A. Page objective

Answer **"what is happening across the marketplace, and is it healthy?"** in one screen: commercial
scale and trajectory, customer activity, fulfilment reliability, and where demand sits geographically.
Used by an exec or GM in a weekly review to decide whether anything needs investigating.

## B. User journey

Land → read five KPIs (scale + trajectory) → read the GMV hero (is growth real and sustained?) → check
customer activity and retention move with it → check fulfilment (delivery-time distribution, outcome
mix) → scan the city matrix for a geographic outlier → optionally open the restaurant lookup.

## C. Navigation

Sidebar section **Overview**, first entry, default landing page. Sidebar carries the global filter bar.

## D. Global filters

Date range, City, Cuisine tag, Order outcome (all four — this is the only page using all of them).

## E. Page-specific filters

None. The metric-selector radio currently inside the GMV card is removed; both measures are shown as
linked panels instead.

## F. Above / below the fold

| Band | Content |
|---|---|
| **Above the fold** (~900px) | Title + subtitle + context chips · 5 KPI tiles · GMV hero with its order-volume companion panel |
| **Below the fold** | Customer activity (2 charts) · Fulfilment (delivery distribution, outcome mix) · Geography (city matrix, cuisine bar) |
| **Optional / expandable** | Restaurant lookup table · "How these numbers are computed" |

## G. Wireframe

```text
┌──────────────────────────────────────────────────────────────────────────────┐
│ Marketplace Health                                                    (H1)   │
│ Commercial scale, customer activity and fulfilment across 10M orders  (sub)  │
│ Period: Jan 2024 – Jun 2026 · City: All (552) · Cuisine: All · Delivered     │
├───────────┬───────────┬───────────┬───────────┬──────────────────────────────┤
│ GMV       │ Delivered │ AOV       │ Monthly   │ Order Failure Rate           │
│ $66.3M    │ 9.15M     │ $7.24     │ Active    │ 8.50%                        │
│ CAD       │ orders    │ CAD       │ 84,972    │ cancelled + refunded         │
├───────────┴───────────┴───────────┴───────────┴──────────────────────────────┤
│  V1.1  HERO — Monthly GMV                              (full width, 300px)   │
│  ┌────────────────────────────────────────────────────────────────────────┐  │
│  │                                                             ╱          │  │
│  │                                            ╱╲      ╱╲     ╱            │  │
│  │                        ╱╲        ╱╲      ╱    ╲  ╱    ╲ ╱              │  │
│  │      ╱╲      ╱╲      ╱    ╲    ╱    ╲  ╱                               │  │
│  └────────────────────────────────────────────────────────────────────────┘  │
│  V1.2  companion panel — Monthly orders   (full width, 110px, shared x-axis) │
│  ┌────────────────────────────────────────────────────────────────────────┐  │
│  │ ▁▁▂▂▂▃▃▃▄▄▄▅▅▅▅▆▆▆▆▇▇▇▇███                                             │  │
│  └────────────────────────────────────────────────────────────────────────┘  │
├══════════════════════════════════════════════════════════════════════════════┤
│  Customer activity                                                    (H2)   │
├───────────────────────────────────┬──────────────────────────────────────────┤
│ V1.3 Monthly active customers     │ V1.4 Monthly retention rate              │
│      (half width, 280px)          │      (half width, 280px)                 │
├═══════════════════════════════════╧══════════════════════════════════════════┤
│  Fulfilment                                                           (H2)   │
├──────────────────────────────────────────────────────────────────────────────┤
│  V1.5 Delivery time distribution        (full width, 300px)                   │
│        ▁▂▃▄▅▆▇█▇▆▅▄▃▂▁      ╎ 30-min proxy threshold                          │
├───────────────────────────────────┬──────────────────────────────────────────┤
│ V1.6 Order outcome mix over time  │ V1.7 Top cuisine tags by GMV             │
│      (half width, 280px)          │      (half width, 280px)                 │
├═══════════════════════════════════╧══════════════════════════════════════════┤
│  Where demand sits                                                    (H2)   │
├──────────────────────────────────────────────────────────────────────────────┤
│  V1.8 City performance matrix                    (full width, ~420px)         │
│  City │ Orders │ GMV │ AOV │ Rating │ Median delivery │ >30 min share          │
├──────────────────────────────────────────────────────────────────────────────┤
│  ▸ Restaurant lookup (148,541 restaurants — min 100 orders)        [expander] │
│  ▸ How these numbers are computed                                 [expander] │
└──────────────────────────────────────────────────────────────────────────────┘
```

## H. Visual specifications

### KPI row (5 tiles, equal width, 104px min-height, 16px gaps)

| # | Label | Value | Format | Unit | Comparison | Colour | Source |
|---|---|---|---|---|---|---|---|
| K1.1 | Gross Merchandise Value (GMV) | `$66.3M` | `$0.0`+M/K, 1 dp | CAD | `+8.4% vs prior 6 months` | Ink only; delta in `good`/`critical` **only because revenue direction is unambiguous** | `MART_EXECUTIVE_SUMMARY.gmv_cad` |
| K1.2 | Delivered Orders | `9,150,122` | thousands separator, 0 dp | orders | `+9.1% vs prior period` | Ink only | `…delivered_orders` |
| K1.3 | Average Order Value (AOV) | `$7.24` | 2 dp | CAD | `flat (±0.3%)` in muted ink | **Neutral — never coloured.** AOV is flat by construction here (F4); a coloured delta would imply a signal that isn't there | `SUM(gmv_cad)/SUM(delivered_orders)` |
| K1.4 | Monthly Active Customers | `84,972` | thousands separator | customers | `+3.4% vs 6 months ago` | Ink only | `MAX(monthly_active_users)` of the latest complete month |
| K1.5 | Order Failure Rate | `8.50%` | 2 dp | % | `−0.2pp vs prior period` | `critical` only above a stated 10% threshold; otherwise ink | `SUM(cancelled+refunded)/SUM(total_orders)` |

**Not in the KPI row, deliberately:** Late Delivery % (F5 — meaningless at 51.81%), NPS proxy (adds
nothing next to the rating distribution), Repeat Order Rate (belongs on Page 3 where it is defined
against a cohort), Total Customers (a static 99,969 — not a health metric).

### V1.1 + V1.2 — GMV hero with order-volume companion

| Element | Specification |
|---|---|
| **Section** | Hero (primary analysis) |
| **Heading** | Monthly GMV |
| **Subheading** | Gross merchandise value from delivered orders, by calendar month. The lower panel shows order volume on the same timeline — the two move together because AOV is flat. |
| **Business question** | Is commercial growth real, sustained, and driven by volume or by basket size? |
| **Data source** | `ZOMATO.MARTS.MART_EXECUTIVE_SUMMARY` |
| **Grain** | Source `order_date`; aggregated to `date_trunc('month', order_date)` |
| **Metrics** | Panel A: `gmv_cad`. Panel B: `total_orders` (or `delivered_orders` when Outcome = Delivered) |
| **Calculation** | `SUM(gmv_cad) GROUP BY month`; `SUM(delivered_orders) GROUP BY month` |
| **Numerator ÷ denominator** | n/a (both are sums, not ratios) |
| **Unit** | CAD (A) · orders (B) |
| **Aggregation** | SUM |
| **X-axis** | `month`, monthly ticks, `Mmm YYYY`, ascending, **shared between both panels** |
| **Y-axis** | A: GMV CAD, linear, **zero-based**, `$0.0M`. B: orders, linear, zero-based, `0.0M`. Independent scales in separate panels — **not** a dual axis |
| **Legend** | None — one series per panel; each panel's heading names it |
| **Data labels** | Off, except a direct label on the **final point** of each panel |
| **Tooltip** | Unified crosshair across both panels: month · GMV (CAD) · delivered orders · AOV (CAD) · days in month |
| **Colours** | Panel A line `#2a78d6` 2px + 12% fill to zero; Panel B line `#2a78d6` 2px, no fill (recessive companion) |
| **Size** | Full width. A = 300px, B = 110px. `make_subplots(rows=2, shared_xaxes=True, row_heights=[0.73,0.27], vertical_spacing=0.06)` |
| **Position** | Row 3, immediately under the KPI row — the single largest element on the page |
| **Filters** | Date, city, cuisine, outcome |
| **Interaction** | Hover crosshair; Plotly range-zoom on x; double-click resets. No click-to-filter |
| **Default state** | Full 30-month history, delivered orders, all cities/cuisines |
| **Footnote** | *"Monthly totals are affected by calendar length (Feb-2026's dip is 28 days, not a downturn). Hover shows days in month."* |

> **Why one hero instead of two equal charts:** with AOV flat at $7.24, GMV ≈ orders × 7.24, so the two
> series are the same shape. Presenting them as co-equal hero visuals would spend the page's most
> valuable space on one story told twice. The companion panel keeps volume verifiable without
> pretending it's independent information.

### V1.3 — Monthly active customers

| Element | Specification |
|---|---|
| **Section** | Customer activity (secondary) |
| **Heading** | Monthly active customers |
| **Subheading** | Distinct customers ordering in each calendar month. Calendar-month active, not a rolling 30-day window. |
| **Business question** | Is the active customer base growing alongside revenue, or is growth coming from existing customers ordering more? |
| **Data source** | `MART_EXECUTIVE_SUMMARY.monthly_active_users` |
| **Grain** | One value per calendar month (the field is month-constant, repeated per day) |
| **Metric** | Monthly active customers |
| **Calculation** | `MAX(monthly_active_users) GROUP BY month` — **`MAX`, not `AVG`**, because the value is already a month-level constant repeated across days (§2.1) |
| **Numerator ÷ denominator** | n/a |
| **Unit** | customers |
| **Aggregation** | MAX within month (de-duplication, not averaging) |
| **X-axis** | month, `Mmm YYYY`, ascending |
| **Y-axis** | customers, linear, zero-based, `0,000` |
| **Legend** | None (single series) |
| **Data labels** | Final point only |
| **Tooltip** | month · monthly active customers · daily active customers (month mean) · orders per active customer |
| **Colour** | `#2a78d6` 2px line, ≥8px markers on hover |
| **Size** | Half width, 280px |
| **Position** | Row 4 left |
| **Filters** | Date (city/cuisine do not apply — MAU is a platform-level distinct count and cannot be filtered without recomputation from `fct_order_sales`; footnoted) |
| **Interaction** | Hover only |
| **Default state** | Full history |
| **Footnote** | *⚠️ Proxy: calendar-month active, not rolling 30-day.* |

### V1.4 — Monthly retention rate

| Element | Specification |
|---|---|
| **Section** | Customer activity (secondary) |
| **Heading** | Monthly retention rate |
| **Subheading** | Of customers who ordered last month, the share who ordered again this month. Rising from 75% to 90% over the period. |
| **Business question** | Is the platform holding onto its active base month over month? |
| **Data source** | `MART_EXECUTIVE_SUMMARY.monthly_retention_rate` |
| **Grain** | One value per calendar month |
| **Metric** | Month-over-month retention rate |
| **Calculation** | `MAX(monthly_retention_rate) GROUP BY month` |
| **Numerator ÷ denominator** | **Customers active in month *M* who were also active in month *M−1*  ÷  customers active in month *M−1*** |
| **Unit** | % |
| **Aggregation** | Ratio of distinct counts (computed in the mart); MAX for month de-duplication |
| **X-axis** | month, ascending |
| **Y-axis** | %, **fixed `[0.60, 1.00]`** with a gridline every 5pp — a fixed, clearly-labelled window, not an auto-fit that exaggerates |
| **Legend** | None |
| **Data labels** | First and last point (75.3% → 89.2%) |
| **Tooltip** | month · retention rate · prior-month customers · retained customers · churn rate |
| **Colour** | `#2a78d6` 2px line |
| **Size** | Half width, 280px |
| **Position** | Row 4 right |
| **Filters** | Date |
| **Interaction** | Hover only |
| **Default state** | Full history; Jan-2024 absent (no prior month) |
| **Footnote** | *"Jan-2024 has no prior month, so it is excluded rather than shown as 0%."* |

### V1.5 — Delivery time distribution

| Element | Specification |
|---|---|
| **Section** | Fulfilment (diagnostic) |
| **Heading** | Delivery time distribution |
| **Subheading** | All 9.15M delivered orders by delivery minutes. The 30-minute proxy threshold sits at the median (31 min), so it splits the distribution roughly in half — it is not a service-level measure. |
| **Business question** | How long do deliveries actually take, and is the "late" threshold telling us anything? |
| **Data source** | `ZOMATO.MARTS.FCT_ORDER_SALES` |
| **Grain** | `order_id`, binned to 1-minute `delivery_time_min` |
| **Metric** | Delivered order count per minute bin |
| **Calculation** | `SELECT delivery_time_min, COUNT(*) FROM fct_order_sales WHERE is_delivered GROUP BY 1` |
| **Numerator ÷ denominator** | Optional secondary y as share: **orders in bin ÷ total delivered orders** |
| **Unit** | orders (and % of delivered) |
| **Aggregation** | COUNT |
| **X-axis** | `delivery_time_min`, 8–87, integer ticks every 10 |
| **Y-axis** | orders, zero-based, `0,000` |
| **Legend** | None (single series) |
| **Data labels** | Off — annotations instead: median 31 min, and the 8-minute floor spike (187,516 orders, a data artefact) |
| **Tooltip** | minutes · orders · % of delivered · cumulative % |
| **Colours** | Bars `#2a78d6`, 2px surface gap between bars. **Vertical rule at 30 min** in `#898781`, solid 1.5px, labelled *"30-min proxy threshold — 51.8% of orders fall above"* |
| **Size** | Full width, 300px |
| **Position** | Row 5, full width — it replaces the removed dual-axis chart |
| **Filters** | Date, city, cuisine |
| **Interaction** | Hover per bar; x-range zoom |
| **Default state** | Full history, all cities |
| **Footnote** | *⚠️ Proxy: `is_late_delivery_proxy` = delivery_time_min > 30. No promised-ETA field exists in source data, so this is an absolute threshold, not an SLA breach.* |

> **Why a distribution instead of a rate:** a 51.81% "late rate" invites the reader to conclude the
> operation is failing. The distribution shows the truth — a tight symmetric bell from 8 to 87 minutes
> centred on 31 — and makes the threshold's arbitrariness self-evident.

### V1.6 — Order outcome mix over time

| Element | Specification |
|---|---|
| **Section** | Fulfilment (diagnostic) |
| **Heading** | Order outcome mix over time |
| **Subheading** | Share of orders delivered, cancelled and refunded each month. Stable at roughly 91.5% / 6.0% / 2.5%. |
| **Business question** | Is fulfilment reliability stable, or is the failure rate drifting? |
| **Data source** | `MART_EXECUTIVE_SUMMARY` (`delivered_orders`, `cancelled_orders`, `refunded_orders`) |
| **Grain** | Calendar month |
| **Metrics** | Share of each outcome |
| **Calculation** | `SUM(<outcome>_orders) / SUM(total_orders) GROUP BY month` |
| **Numerator ÷ denominator** | **Orders with that outcome in the month ÷ all orders in the month** |
| **Unit** | % of orders |
| **Aggregation** | Ratio of summed counts |
| **X-axis** | month, ascending |
| **Y-axis** | % of orders, `[0,100]` stacked to 100% |
| **Legend** | Yes — required (3 series). Fixed order: Delivered, Cancelled, Refunded. Never reordered by size |
| **Data labels** | Off; the legend plus tooltip carry identity and value |
| **Tooltip** | month · outcome · orders · % of month |
| **Colours** | **Status tokens, fixed platform-wide:** Delivered `#0ca30c`, Cancelled `#d03b3b`, Refunded `#fab219`. Each legend entry carries its text label (on the light surface `#fab219` is sub-3:1, so the label is the required mitigation) |
| **Size** | Half width, 280px |
| **Position** | Row 6 left |
| **Filters** | Date, city, cuisine. Outcome filter is **ignored** here (this chart *is* the outcome breakdown) — noted in the subheading |
| **Interaction** | Hover; legend click isolates a band |
| **Default state** | Full history, 100% stacked |
| **Footnote** | — (measured metric, no caveat needed) |

> Replaces the order-status donut. A donut showed one static mix; this shows the same mix *plus*
> whether it is drifting, in the same space.

### V1.7 — Top cuisine tags by GMV

| Element | Specification |
|---|---|
| **Section** | Fulfilment / demand mix (diagnostic) |
| **Heading** | Top cuisine tags by GMV |
| **Subheading** | GMV attributed to each cuisine tag. Restaurants carry multiple tags, so an order tagged "North Indian, Chinese" counts under both — shares sum to more than 100%. |
| **Business question** | Which cuisines carry the most revenue? |
| **Data source** | `FCT_ORDER_SALES`, `cuisine` split with `LATERAL SPLIT_TO_TABLE(cuisine, ',')` |
| **Grain** | Order × cuisine tag (a deliberate fan-out from `order_id`) |
| **Metric** | GMV per cuisine tag |
| **Calculation** | `SUM(IFF(is_delivered, sales_amount_cad, 0)) GROUP BY TRIM(tag)`, top 12 |
| **Numerator ÷ denominator** | If shown as a share: **GMV for the tag ÷ SUM of GMV across all tag-order pairs** (*not* ÷ platform GMV — that denominator would be wrong given the fan-out) |
| **Unit** | CAD |
| **Aggregation** | SUM |
| **X-axis** | GMV CAD, zero-based, `$0.0M` |
| **Y-axis** | cuisine tag, **sorted by GMV descending** (longest bar at top) |
| **Legend** | None (single series) |
| **Data labels** | On, at the bar end, `$0.0M`, 1 dp |
| **Tooltip** | tag · GMV (CAD) · orders · share of tagged orders · AOV |
| **Colour** | **One hue for every bar: `#2a78d6`.** Not a value ramp (§4.1 rule 6) |
| **Size** | Half width, 280px, 12 bars |
| **Position** | Row 6 right |
| **Filters** | Date, city, outcome. The cuisine filter narrows which tags appear |
| **Interaction** | Hover per bar |
| **Default state** | Top 12 tags, full history |
| **Footnote** | *🧮 Derived: tags split from a comma-delimited field (2,133 raw combinations). Orders are counted once per tag, so totals exceed platform GMV.* |

> Replaces charting the 2,133 raw combination strings, where "North Indian,Chinese" and
> "Chinese,North Indian" were separate categories. Splitting is an in-query transform — no new mart.

### V1.8 — City performance matrix

| Element | Specification |
|---|---|
| **Section** | Where demand sits (detail) |
| **Heading** | City performance |
| **Subheading** | Top 20 cities by order volume — 67% of all orders. Median delivery time and rating are shown alongside volume so a large city with weak fulfilment is visible. |
| **Business question** | Which cities drive volume, and does any of them underperform on fulfilment or satisfaction? |
| **Data source** | `FCT_ORDER_SALES` |
| **Grain** | `city` (one row per city) |
| **Metrics** | Orders · GMV (CAD) · AOV (CAD) · mean rating · median delivery minutes · share over 30 min |
| **Calculation** | `COUNT(*)` · `SUM(IFF(is_delivered, sales_amount_cad,0))` · `GMV ÷ delivered_orders` · `AVG(customer_rating)` on rated delivered orders · `MEDIAN(delivery_time_min)` on delivered · `COUNT_IF(is_late_delivery_proxy) ÷ COUNT_IF(is_delivered)` |
| **Numerator ÷ denominator** | AOV = **GMV ÷ delivered orders in the city**. Over-30-min share = **delivered orders over 30 min in the city ÷ delivered orders in the city** |
| **Unit** | orders · CAD · CAD · rating (1–5) · minutes · % |
| **Aggregation** | COUNT · SUM · ratio of aggregates · AVG · MEDIAN · ratio of counts |
| **X-axis / Y-axis** | n/a (table). Rows = cities sorted by GMV desc; columns as above |
| **Legend** | None. The one conditional column carries an inline scale caption |
| **Data labels** | All values visible as text — this is the page's table view, so nothing is colour-gated |
| **Tooltip** | Native cell tooltip on truncated city names only |
| **Colours** | Text in ink tokens. **One** conditional column — GMV — as a light sequential blue bar (`st.column_config.ProgressColumn`). Rating and delivery columns stay plain text: a second colour scale in one table pushes past the ~7-class limit and turns the table into a heat sheet |
| **Size** | Full width, ~420px (20 rows, no inner scroll) |
| **Position** | Row 7, full width |
| **Filters** | Date, cuisine, outcome. City filter narrows the row set |
| **Interaction** | Click a column header to sort; horizontal scroll suppressed by fitting 7 columns |
| **Default state** | Top 20 by orders, sorted GMV desc |
| **Footnote** | *"Rating covers 70% of delivered orders (unrated orders excluded from the mean). 552 cities exist; the top 20 are 67% of orders."* |

### Expander — Restaurant lookup

Collapsed `st.expander`, label **"Restaurant lookup (148,541 restaurants — minimum 100 orders)"**.
Contains a searchable table: restaurant name · city · orders · GMV · AOV · mean order rating · median
delivery minutes, filtered to ≥100 orders (27,005 qualify), sorted by GMV desc, limit 200 rows.

Framed explicitly as **operational lookup, not a leaderboard** — footnote: *"No restaurant exceeds
0.03% of platform GMV (top restaurant: $15,143 of $66.3M), and performance metrics are flat across
volume tiers, so rank order here is not a meaningful performance signal."* This is the honest home for
restaurant data given F6.

---

# Part 7 — Page 2 — Customer Value

## A. Page objective

Answer **"where is customer value concentrated, and what drives it?"** Establish that value is highly
concentrated, show that the driver is **purchase frequency rather than basket size**, and give the
segment-level detail a CRM team would act on.

## B. User journey

Land → KPIs frame coverage and the typical customer → hero shows value concentration (a quarter of
customers hold ~60% of value) → the Recency × Frequency plane shows *where* customers sit → the segment
matrix gives per-segment numbers to act on → demographics available on demand, clearly marked as
descriptive only.

## C. Navigation

Sidebar section **Customers**.

## D. Global filters

Date range and City apply to nothing on this page and are therefore **visually disabled with an
explanation** — RFM measures are lifetime values anchored to `recency_anchor_date` (2026-06-30) and do
not recompute per window. Showing them as active would be a lie about what the page does.

## E. Page-specific filters

RFM segment `st.multiselect` (default all 8) → scopes the hero and the matrix, **not** the KPI row.

## F. Above / below the fold

| Band | Content |
|---|---|
| **Above the fold** | Title, subtitle, chips · 5 KPI tiles · value-concentration hero |
| **Below the fold** | Recency × Frequency density · value distribution by decile · segment matrix |
| **Optional** | Demographics expander · method expander |

## G. Wireframe

```text
┌──────────────────────────────────────────────────────────────────────────────┐
│ Customer Value                                                        (H1)   │
│ Where value concentrates across 90,428 scored customers, and what drives it  │
│ Scored: 90,428 of 99,969 customers (90.5%) · Recency anchored 2026-06-30     │
│ Segments: All 8                                     [Date/City n/a here ⓘ]   │
├───────────┬───────────┬───────────┬───────────┬──────────────────────────────┤
│ Customers │ Value     │ Median    │ Median    │ Value in Top Segment         │
│ Scored    │ Covered   │ Orders /  │ Customer  │ 59.1%                        │
│ 90,428    │ $59.9M    │ Customer  │ Value     │ Champions (25.6% of          │
│ 90.5%     │ 90.4%     │ 55        │ $398      │ customers)                   │
├───────────┴───────────┴───────────┴───────────┴──────────────────────────────┤
│  V2.1  HERO — Value concentration by segment          (full width, 380px)    │
│  ┌────────────────────────────────────────────────────────────────────────┐  │
│  │ Champions      ████████████ 25.6%  │ ██████████████████████████ 59.1%  │  │
│  │ Valuable       ██████ 13.3%        │ ███████ 15.3%                     │  │
│  │ Lost           █████████████ 28.3% │ ███ 6.8%                          │  │
│  │ At Risk        ██ 4.9%             │ ██ 5.5%                           │  │
│  │ Loyal          ███ 7.2%            │ ██ 4.6%                           │  │
│  │ …              ← share of customers │ share of value →                 │  │
│  └────────────────────────────────────────────────────────────────────────┘  │
├══════════════════════════════════════════════════════════════════════════════┤
│  How value is distributed                                             (H2)   │
├───────────────────────────────────┬──────────────────────────────────────────┤
│ V2.2 Recency × Frequency density  │ V2.3 Value by customer decile            │
│      (half width, 320px)          │      (half width, 320px)                 │
├═══════════════════════════════════╧══════════════════════════════════════════┤
│  Segment detail                                                       (H2)   │
├──────────────────────────────────────────────────────────────────────────────┤
│  V2.4 RFM segment matrix                        (full width, ~360px)          │
│  Segment │ Customers │ % Cust │ Value │ % Value │ Orders │ AOV │ Recency      │
├──────────────────────────────────────────────────────────────────────────────┤
│  ▸ Customer demographics — descriptive only, not associated with value  [exp] │
│  ▸ How RFM is scored                                                   [exp]  │
└──────────────────────────────────────────────────────────────────────────────┘
```

## H. Visual specifications

### KPI row

| # | Label | Value | Format | Unit | Supporting text | Colour | Source |
|---|---|---|---|---|---|---|---|
| K2.1 | Customers Scored | `90,428` | separator | customers | `90.5% of 99,969 ordering customers` | Ink | `COUNT(*) MART_CUSTOMER_RFM` |
| K2.2 | Customer Value Covered | `$59.9M` | `$0.0M` | CAD | `90.4% of $66.3M platform GMV` | Ink | `SUM(monetary_value_cad)` |
| K2.3 | Median Orders per Customer | `55` | 0 dp | orders | `mean 91 — skewed; max 8,284` | Ink | `MEDIAN(frequency_orders)` |
| K2.4 | Median Customer Value | `$398` | 0 dp | CAD | `95th percentile $2,096` | Ink | `MEDIAN(monetary_value_cad)` |
| K2.5 | Value in Top Segment | `59.1%` | 1 dp | % | `Champions — 25.6% of customers` | Ink | derived, see §11.4 |

**Median, not mean, for K2.3/K2.4** — frequency runs 1 → 8,284 and value $1.01 → $60,729. A mean would
describe a customer who doesn't exist. Both tiles name the skew in supporting text.

**Deliberately excluded:** platform GMV/orders/AOV (already on Page 1 — repeating them wastes the
fold), "Repeat Rate" (defined on Page 3 against cohorts).

### V2.1 — Value concentration by segment (HERO)

| Element | Specification |
|---|---|
| **Section** | Hero (primary analysis) |
| **Heading** | Value concentration by segment |
| **Subheading** | Each segment's share of customers next to its share of lifetime value. Champions are 25.6% of customers but 59.1% of value; Lost are 28.3% of customers and 6.8% of value. |
| **Business question** | Is value concentrated, and in whom? |
| **Data source** | `ZOMATO.MARTS.MART_CUSTOMER_RFM` |
| **Grain** | `segment_label` (8 rows, aggregated from `customer_id`) |
| **Metrics** | Share of customers · share of monetary value |
| **Calculation** | `COUNT(*) GROUP BY segment_label` and `SUM(monetary_value_cad) GROUP BY segment_label`, each divided by its total |
| **Numerator ÷ denominator** | Customer share = **customers in segment ÷ 90,428 scored customers**. Value share = **segment monetary value ÷ $59,937,887.66 total scored value** |
| **Unit** | % (both) |
| **Aggregation** | Ratio of aggregates (COUNT and SUM over the same scoped population) |
| **X-axis** | % of total, `[0,60]`, mirrored — customers left-to-right, value right-to-left (paired/tornado bars sharing a centre axis of segment labels) |
| **Y-axis** | `segment_label`, sorted by **share of value descending** |
| **Legend** | Yes — 2 series, required. `Share of customers` / `Share of value`, fixed order, plus axis-side direct labels |
| **Data labels** | **On, all bars** — only 16 marks, and the gap between the pair *is* the finding |
| **Tooltip** | segment · customers · % of customers · value (CAD) · % of value · mean orders · mean AOV · mean recency (days) |
| **Colours** | Customers `#2a78d6`, Value `#eb6834`. Validated all-pass in both modes (CVD ΔE 24.7 light / 26.8 dark) |
| **Size** | Full width, 380px |
| **Position** | Row 3, hero |
| **Filters** | Segment multiselect. Shares always recompute against the **full** scored population so removing a segment doesn't inflate the others — stated in the footnote |
| **Interaction** | Hover; legend click isolates a series |
| **Default state** | All 8 segments, sorted by value share |
| **Footnote** | *"Percentages are of all 90,428 scored customers even when segments are filtered out, so shares stay comparable."* |

> **Why this replaces the proposed Frequency-vs-Monetary bubble scatter:** `corr(F,M) = 0.9975` (F4). A
> Frequency × Monetary scatter renders a near-perfect straight line — it would consume the hero slot to
> show that two axes are the same measure. Additionally, colouring 8 segments on a scatter is barred by
> the palette's all-pairs gate (only 3 slots validate). The paired bar answers the actual question
> ("where is the value?") in one glance, needs 2 validated colours, and needs no overplotting mitigation.

### V2.2 — Recency × Frequency density

| Element | Specification |
|---|---|
| **Section** | How value is distributed (secondary) |
| **Heading** | Recency × Frequency density |
| **Subheading** | Customer count per recency/frequency cell. Recency and frequency are genuinely distinct (r = −0.23), unlike frequency and monetary value (r = 0.998), so this is the informative RFM plane. |
| **Business question** | Where do customers actually sit on the recency/frequency plane — and is there a reachable at-risk mass? |
| **Data source** | `MART_CUSTOMER_RFM` |
| **Grain** | Binned cell: `recency_days` bin × `frequency_orders` bin (aggregated from `customer_id`) |
| **Metric** | Customer count per cell |
| **Calculation** | `COUNT(*) GROUP BY width_bucket(recency_days, 0, 120, 24), width_bucket(frequency_orders, 0, 300, 20)` — binning done **in SQL**, returning ~480 cells instead of 90,428 rows |
| **Numerator ÷ denominator** | n/a (count). Tooltip additionally shows **cell customers ÷ 90,428** |
| **Unit** | customers |
| **Aggregation** | COUNT |
| **X-axis** | `recency_days`, 5-day bins, 0–120, ascending (0 = ordered on the anchor date) |
| **Y-axis** | `frequency_orders`, 15-order bins, 0–300 (95th pct = 289), with a final "300+" band |
| **Legend** | Continuous colourbar, titled "Customers", with tick values |
| **Data labels** | Off — a value in every cell would be 480 numbers (anti-pattern) |
| **Tooltip** | recency band · frequency band · customers · % of scored base · mean value in cell |
| **Colours** | **Sequential single-hue blue**, `#cde2fb` → `#0d366b`, light = few customers |
| **Size** | Half width, 320px |
| **Position** | Row 4 left |
| **Filters** | Segment multiselect |
| **Interaction** | Hover per cell |
| **Default state** | Full scored base, all segments |
| **Footnote** | *"Recency is measured against the dataset's own last order date (2026-06-30), not today, so it is stable across pipeline runs."* |

> A 90,428-point scatter would be a solid ink blob; binning in SQL fixes both the overplotting and the
> data-transfer problem (§2.7) in one move.

### V2.3 — Value by customer decile

| Element | Specification |
|---|---|
| **Section** | How value is distributed (secondary) |
| **Heading** | Value by customer decile |
| **Subheading** | Customers ranked by lifetime value and split into ten equal groups. The top decile holds a disproportionate share — this quantifies the concentration the hero shows by segment. |
| **Business question** | How steep is value concentration, independent of how segments were defined? |
| **Data source** | `MART_CUSTOMER_RFM` |
| **Grain** | Value decile (10 rows) |
| **Metric** | Share of total value per decile |
| **Calculation** | `NTILE(10) OVER (ORDER BY monetary_value_cad DESC)` then `SUM(monetary_value_cad) per decile ÷ total` |
| **Numerator ÷ denominator** | **Decile value ÷ $59,937,887.66 total scored value** |
| **Unit** | % of total value |
| **Aggregation** | SUM, then ratio |
| **X-axis** | decile 1–10 (1 = highest value), ordered |
| **Y-axis** | % of total value, zero-based |
| **Legend** | None (single series) |
| **Data labels** | On — 10 bars, 1 dp |
| **Tooltip** | decile · customers · value (CAD) · % of value · cumulative % · mean orders · value range |
| **Colours** | **Ordinal ramp** (ordered categories, not nominal): validated 3-step blue interpolated across 10 steps, darkest at decile 1. Validated `--ordinal`: monotone L, ΔL ≥ 0.06, light end 2.06:1 |
| **Size** | Half width, 320px |
| **Position** | Row 4 right |
| **Filters** | None — deciles are defined on the full scored base by construction |
| **Interaction** | Hover |
| **Default state** | All 10 deciles, descending |
| **Footnote** | *🧮 Derived in-query; independent of the RFM segment definitions.* |

### V2.4 — RFM segment matrix

| Element | Specification |
|---|---|
| **Section** | Segment detail (detail) |
| **Heading** | RFM segment detail |
| **Subheading** | One row per segment with the numbers a CRM team would act on. Note AOV is flat at ~$7.24 across every segment — value differences come from order frequency, not basket size. |
| **Business question** | For each segment: how many customers, how much value, how often do they order, how recently — and what should we do about it? |
| **Data source** | `MART_CUSTOMER_RFM` |
| **Grain** | `segment_label` (8 rows) |
| **Metrics** | Customers · % of customers · value (CAD) · % of value · mean orders · mean AOV · mean recency (days) |
| **Calculation** | `COUNT(*)` · share · `SUM(monetary_value_cad)` · share · `AVG(frequency_orders)` · `SUM(monetary)/SUM(frequency)` · `AVG(recency_days)` |
| **Numerator ÷ denominator** | % of customers = **segment customers ÷ 90,428**. % of value = **segment value ÷ total scored value**. **AOV = segment total value ÷ segment total orders** (a ratio of aggregates, *not* `AVG(value/orders)`) |
| **Unit** | customers · % · CAD · % · orders · CAD · days |
| **Aggregation** | COUNT · SUM · AVG · **ratio of aggregates for AOV** |
| **X / Y axis** | n/a (table). Rows sorted by value desc |
| **Legend** | None; the one conditional column carries an inline caption |
| **Data labels** | All values as text — this is the page's table view |
| **Tooltip** | Segment definition rule on hovering the segment name (e.g. "Champions: R≥4 and F≥4 and M≥4") |
| **Colours** | Ink text. **One** conditional column — % of value — as a light sequential blue progress bar. Recency shown as plain text, not a red/green scale: "recent" is not inherently good for a low-frequency customer |
| **Size** | Full width, ~360px (8 rows + header) |
| **Position** | Row 5, full width |
| **Filters** | Segment multiselect |
| **Interaction** | Header sort |
| **Default state** | All 8, sorted by value desc |
| **Footnote** | *"AOV range across segments is $7.09–$7.41 — a 4% spread. `corr(frequency, monetary) = 0.998`, so the M in RFM adds little beyond F in this dataset."* |

### Expander — Customer demographics (demoted, with evidence)

Label: **"Customer demographics — descriptive only, not associated with value"**. Two compact
half-width charts: age distribution (histogram, 20 bins, `#2a78d6`) and customers by monthly income
band (bar, single hue, ordered by band not by count).

Required footnote, stating the verified reason for the demotion:

> *Demographics show no association with customer value in this dataset: corr(age, value) = 0.003,
> corr(income midpoint, value) = 0.005, corr(family size, value) = −0.0003. Mean lifetime value across
> the five income bands spans just $658.69–$670.17 (a 1.7% spread). These charts describe who the
> customers are; they do not explain value.*

Gender and occupation donut/bar are **dropped** (§13) — with zero association to value, three
demographic charts is two too many, and the gender donut was a 3-slice pie.

---

# Part 8 — Page 3 — Retention & Activation

The project's central storyline, and the page where analytical integrity matters most — two of its
three diagnostic sections are **null results** that the current design accidentally presents as
findings.

## A. Page objective

Answer **"where do customers drop off, and what patterns are associated with coming back?"** Show how
fast new customers return, how retention differs by acquisition cohort, and report honestly that
first-order experience shows **no** association with reordering.

## B. User journey

Land → activation KPIs (customer-weighted, correct) → cohort heatmap: the shape of retention, with
small cohorts suppressed → pick one cohort and read its curve → see how activation windows stack →
reach the experience diagnostics and read a clearly-labelled null result → see the discount comparison
with its confound exposed in the same table.

## C. Navigation

Sidebar section **Retention**.

## D. Global filters

Date range applies only to the cohort *display* window. **City and cuisine are disabled with an
explanation** — cohorts are defined by a customer's first order, so filtering orders by city
retroactively redefines cohort membership and silently changes cohort sizes (§5.3).

## E. Page-specific filters

Cohort selector (`selectbox`, default `2024-01`); minimum cohort size (`select_slider`, default 100);
experience dimension (`radio`, above the diagnostic row).

## F. Above / below the fold

| Band | Content |
|---|---|
| **Above the fold** | Title, subtitle, chips · 5 activation KPIs · cohort retention heatmap (the hero gets the most space on the page) |
| **Below the fold** | Selected-cohort curve · activation windows · experience diagnostics (null results) · discount dependency |
| **Optional** | Cohort size reference table · method expander |

## G. Wireframe

```text
┌──────────────────────────────────────────────────────────────────────────────┐
│ Retention & Activation                                                (H1)   │
│ How fast new customers return, and what is — and isn't — associated with it  │
│ 99,963 customers · 30 cohorts · min cohort size 100 (15 cohorts shown)       │
│ [City/cuisine filters do not apply to cohort analysis ⓘ]                     │
├───────────┬───────────┬───────────┬───────────┬──────────────────────────────┤
│ 2nd Order │ 2nd Order │ 2nd Order │ Median    │ Ever Placed a 2nd Order      │
│ ≤ 7 days  │ ≤ 14 days │ ≤ 30 days │ Days to   │ 99.9%                        │
│ 29.3%     │ 44.8%     │ 64.8%     │ 2nd Order │ near-universal — use the     │
│           │           │           │ 18        │ time windows instead         │
├───────────┴───────────┴───────────┴───────────┴──────────────────────────────┤
│  V3.1  HERO — Cohort retention                       (full width, 520px)     │
│         Period →   0     1     2     3     4     5     6   …                 │
│  2024-01 (63,144) 100%  73.7% 77.2% 76.8% 78.6% 79.4% 80.5%  ▓▓▓▓▓▓          │
│  2024-02 (16,359) 100%  ...                                  ▓▓▓▓▓▓          │
│  2024-03  (8,182) 100%  ...                                  ▓▓▓▓▓           │
│  2024-04  (4,008) 100%  ...                                  ▓▓▓▓            │
│  2024-05  (2,586) 100%  ...                                  ▓▓▓             │
│  2024-06  (1,573) 100%  ...                                  ▓▓▓             │
│  …  cohorts below the size threshold are greyed, not coloured                │
├══════════════════════════════════════════════════════════════════════════════┤
│  Retention in detail                                                  (H2)   │
├───────────────────────────────────┬──────────────────────────────────────────┤
│ V3.2 Selected cohort curve        │ V3.3 Activation windows                  │
│      [Cohort: 2024-01 ▾]          │      ≤7d → ≤14d → ≤30d → ever            │
│      (half width, 320px)          │      (half width, 320px)                 │
├═══════════════════════════════════╧══════════════════════════════════════════┤
│  First-order experience — observed association, no causal claim        (H2)   │
│  ⓘ No material difference found. All three comparisons sit within 0.7pp      │
│    of the 64.8% platform reorder rate. Axes are fixed 0–100%.                │
├──────────────┬──────────────────┬────────────────────────────────────────────┤
│ Delivery     │ First-order      │ First-order discount                       │
│ speed        │ rating           │                                            │
│ (1/3, 300px) │ (1/3, 300px)     │ (1/3, 300px)                               │
├──────────────┴──────────────────┴────────────────────────────────────────────┤
│  Discount dependency                                                  (H2)   │
│  V3.5 (full width, ~200px) — with avg orders column exposing the confound    │
├──────────────────────────────────────────────────────────────────────────────┤
│  ▸ Cohort sizes and coverage                                          [exp]  │
│  ▸ How activation and retention are calculated                        [exp]  │
└──────────────────────────────────────────────────────────────────────────────┘
```

## H. Visual specifications

### KPI row — all customer-weighted (fixes F1/§2.1)

| # | Label | Value | Format | Unit | Supporting text | Colour | Calculation |
|---|---|---|---|---|---|---|---|
| K3.1 | 2nd Order within 7 Days | `29.3%` | 1 dp | % | `of 99,963 first-time customers` | Ink | §11.3 |
| K3.2 | 2nd Order within 14 Days | `44.8%` | 1 dp | % | `+15.5pp vs 7-day` | Ink | §11.3 |
| K3.3 | 2nd Order within 30 Days | `64.8%` | 1 dp | % | `+20.0pp vs 14-day` | Ink | §11.3 |
| K3.4 | Median Days to 2nd Order | `18` | 0 dp | days | `among those who reordered` | Ink | `MEDIAN(days_to_second_order)` over non-null |
| K3.5 | Ever Placed a 2nd Order | `99.9%` | 1 dp | % | `near-universal — the time windows carry the signal` | Muted ink | `COUNT_IF(days_to_second_order IS NOT NULL) ÷ COUNT(*)` |

**K3.5 is included specifically to defuse a misreading:** with 99.9% of customers eventually
reordering, "did they reorder?" is not a discriminating question in this dataset — which is *why* the
time-bounded windows are the real metric, and why the experience diagnostics below find nothing on the
`did_reorder` flag.

**Excluded: Repeat Restaurant Rate.** Verified ≈ 0 (max 1.58e-05 across 30 cohorts) against a random
baseline of 1/148,541 = 6.7e-06. It measures nothing. Documented on the Method page.

### V3.1 — Cohort retention heatmap (HERO)

| Element | Specification |
|---|---|
| **Section** | Hero (primary analysis) — the largest element on any page in the dashboard |
| **Heading** | Cohort retention |
| **Subheading** | For each acquisition cohort, the share still ordering in each subsequent month. Cohort size is shown beside each row because sizes range from 63,144 down to 3 customers. |
| **Business question** | Does retention hold up over a customer's lifetime, and are newer cohorts behaving differently from older ones? |
| **Data source** | `ZOMATO.MARTS.MART_COHORT_RETENTION` (464 rows — already at presentation grain) |
| **Grain** | `acquisition_cohort_month` × `period_number` |
| **Metric** | `retention_rate` |
| **Calculation** | Computed in the mart: `active_customers ÷ cohort_size` |
| **Numerator ÷ denominator** | **Distinct customers from the cohort with ≥1 delivered order in period *p*  ÷  distinct customers whose first delivered order fell in the cohort month** |
| **Unit** | % |
| **Aggregation** | Ratio of distinct counts (no further aggregation in the UI) |
| **X-axis** | `period_number`, **months** since acquisition, 0 → 29, integer ticks, ascending. *(The current page labels this "Weeks from Acquisition" — the mart computes `datediff(month, …)`. It is months. Mislabel to fix.)* |
| **Y-axis** | `acquisition_cohort_month`, newest at top, label format `Mmm YYYY (n=63,144)` |
| **Legend** | Continuous colourbar "Retention %", 0–100 |
| **Data labels** | On, in-cell, `0.0%`, only where the cell is ≥ 28px wide and n ≥ the threshold; otherwise tooltip-only. Suppressed cells render as a grey hatch with no number |
| **Tooltip** | cohort · period (months) · retention % · active customers · cohort size · *"below minimum sample size"* when suppressed |
| **Colours** | **Sequential single-hue blue** `#cde2fb` → `#0d366b`. Suppressed cells `#e1e0d9` (light) / `#2c2c2a` (dark). **Replaces `RdYlGn`** — retention is a magnitude, not a polarity, so a diverging red/green scale invents a "bad/good" midpoint that doesn't exist |
| **Size** | Full width, **520px** — roughly 1.7× any other visual, matching its status as the page's central artefact |
| **Position** | Row 3, directly under the KPI row, above the fold |
| **Filters** | Minimum cohort size slider (default 100 → 15 cohorts qualify); date range narrows the cohort rows shown |
| **Interaction** | Hover per cell; clicking a row label sets V3.2's cohort selector (the one link between visuals, and it is signposted) |
| **Default state** | **Cohorts with n ≥ 100, newest at top, all periods.** Explicitly *not* `cohorts[-12:]` — that default showed the 12 smallest cohorts (n = 3 to 161), i.e. sampling noise |
| **Footnote** | *"15 of 30 cohorts have fewer than 100 customers and are hidden by default; 10 have fewer than 30. The Jan-2024 cohort is 63% of all customers, so platform retention is effectively that cohort's retention. A (cohort, period) pair with no active customers produces no row and renders blank, not 0%."* |

### V3.2 — Selected cohort retention curve

| Element | Specification |
|---|---|
| **Section** | Retention in detail (secondary) |
| **Heading** | Selected cohort retention curve |
| **Subheading** | One cohort's retention over time, with the platform-wide weighted curve behind it for comparison. |
| **Business question** | For a specific acquisition cohort, what does the retention decay actually look like? |
| **Data source** | `MART_COHORT_RETENTION` |
| **Grain** | `period_number` for the selected cohort |
| **Metrics** | Selected cohort `retention_rate`; benchmark = customer-weighted retention across all cohorts ≥ threshold |
| **Calculation** | Selected: filter to the chosen cohort. Benchmark: `SUM(active_customers) ÷ SUM(cohort_size) GROUP BY period_number` — **weighted, not `AVG(retention_rate)`** |
| **Numerator ÷ denominator** | Benchmark = **Σ active customers at period *p* across cohorts ÷ Σ cohort sizes of those cohorts** |
| **Unit** | % |
| **Aggregation** | Ratio of aggregates |
| **X-axis** | `period_number` (months since acquisition), 0 → max for that cohort |
| **Y-axis** | retention %, fixed `[0, 100]` |
| **Legend** | Yes — 2 series: selected cohort, platform weighted. Fixed order |
| **Data labels** | Period 0 and the final period of the selected series only |
| **Tooltip** | period · selected cohort retention % · active customers · cohort size · platform weighted % |
| **Colours** | Selected `#2a78d6` 2px solid; benchmark `#898781` 1.5px solid (recessive reference, not a competing series). No dashes on either — dashing reads as "projection" |
| **Size** | Half width, 320px |
| **Position** | Row 4 left |
| **Filters** | Cohort selectbox (default `2024-01`, n = 63,144 — the largest); min cohort size limits the options list |
| **Interaction** | Cohort selectbox above the chart; hover crosshair |
| **Default state** | `2024-01` vs platform weighted |
| **Footnote** | *"Cohorts with fewer than the selected minimum are not offered — at n=16 retention swings between 12.5% and 43.8% on sampling noise alone."* |

### V3.3 — Activation windows

| Element | Specification |
|---|---|
| **Section** | Retention in detail (secondary) |
| **Heading** | Activation windows |
| **Subheading** | Share of first-time customers placing a second order within each window. These are **cumulative and nested** (everyone in the 7-day group is also in the 14-day group), so this is not a drop-off funnel. |
| **Business question** | How quickly do new customers come back? |
| **Data source** | `MART_ACTIVATION` (weighted) or `MART_RETENTION_DIAGNOSTIC` (customer grain) |
| **Grain** | Window (4 ordered categories: ≤7d, ≤14d, ≤30d, ever) |
| **Metric** | Share of first-time customers converting within the window |
| **Calculation** | `SUM(pct_Nd × cohort_size) ÷ SUM(cohort_size)` per window (equivalently, customer-grain `COUNT_IF(days_to_second_order <= N) ÷ COUNT(*)` — both verified identical) |
| **Numerator ÷ denominator** | **First-time customers whose 2nd delivered order fell within N days of their 1st  ÷  all 99,963 first-time customers** (non-converters stay in the denominator) |
| **Unit** | % of first-time customers |
| **Aggregation** | **Ratio of aggregates — never `AVG(pct)` (§2.1)** |
| **X-axis** | window, ordered ≤7d → ≤14d → ≤30d → ever |
| **Y-axis** | % of customers, fixed `[0, 100]` |
| **Legend** | None — one series; the ordinal ramp is explained by the axis order |
| **Data labels** | On, all four bars, 1 dp, plus the **increment** between adjacent bars (`+15.5pp`) as a small annotation, since the increment is the interesting quantity |
| **Tooltip** | window · % of customers · customers converting · incremental vs previous window |
| **Colours** | **Ordinal ramp** `#86b6ef` → `#2a78d6` → `#104281`, plus muted `#898781` for "ever" (it is a different kind of quantity — unbounded in time). Validated `--ordinal`: all pass |
| **Size** | Half width, 320px |
| **Position** | Row 4 right |
| **Filters** | None (platform-level by design) |
| **Interaction** | Hover |
| **Default state** | All four windows |
| **Footnote** | *"Presented as nested cumulative shares, not a funnel: funnel geometry implies mutually exclusive sequential stages, and these windows overlap by construction."* |

> The user's brief flagged this concern directly and it is correct — a conventional funnel chart here
> would misrepresent nested time windows as exclusive stages. Ordered bars on a common 0–100% axis with
> explicit increments say the same thing without the false geometry.

### V3.4 — First-order experience diagnostics (three aligned panels, **null result**)

One spec covers all three panels; they differ only in the grouping column.

| Element | Specification |
|---|---|
| **Section** | First-order experience — observed association, no causal claim (diagnostic) |
| **Heading** | Panel A "Delivery speed" · Panel B "First-order rating" · Panel C "First-order discount" |
| **Section subheading** | **No material difference found.** All three comparisons sit within 0.7pp of the 64.8% platform reorder rate. Axes are fixed 0–100% so the size of the difference is legible. |
| **Business question** | Is a faster, better-rated, or discounted first order associated with the customer coming back within 30 days? |
| **Data source** | `ZOMATO.MARTS.MART_RETENTION_DIAGNOSTIC` |
| **Grain** | Aggregated from `customer_id` to bucket (4 / 4–5 / 2 buckets) |
| **Metric** | 30-day reorder rate per bucket |
| **Calculation** | `COUNT_IF(did_reorder_within_30d) ÷ COUNT(*) GROUP BY <bucket>` — pushed to SQL |
| **Numerator ÷ denominator** | **Customers in the bucket who placed a 2nd delivered order within 30 days of their 1st  ÷  all customers in that bucket** |
| **Unit** | % of customers in bucket |
| **Aggregation** | Ratio of counts |
| **X-axis** | 30-day reorder rate, **fixed `[0, 100]`** — the single most important change on this page |
| **Y-axis** | Bucket. A: Very Fast (8–20) / Fast (21–30) / Moderate (31–40) / Slow (41+), in **speed order, not rate order**. B: 5★ / 4★ / 3★ / 1–2★ / Unrated. C: Used discount / No discount |
| **Legend** | None (single series per panel) |
| **Data labels** | On, bar end, 1 dp, plus bucket n |
| **Tooltip** | bucket · customers · reordered within 30d · rate · **difference vs pooled rate in pp** |
| **Colours** | **One hue for all bars: `#2a78d6`** — no value ramp, because there is no gradient to encode. **Reference rule at 64.8%** in `#898781`, solid, labelled "platform rate" |
| **Size** | Three equal thirds, 300px each, x-axes locked identical across all three so bars are visually comparable panel-to-panel |
| **Position** | Row 5, full-width band of three |
| **Filters** | Experience-dimension radio above the row (show all / one at a time) |
| **Interaction** | Hover |
| **Default state** | All three panels, fixed 0–100% axis, reference line on |
| **Footnote** | *🔬 Observational, not causal — no controls for city, cuisine, restaurant or customer segment. Verified spreads: delivery 0.65pp, rating 0.27pp, discount 0.06pp. **These are null results**; a bucket difference this small is a hypothesis for Phase B's multivariate work, not a finding.* |

**Panel B additional requirement (see §2.6):** `rating_bucket = 'Poor (<3.0)'` currently contains 30,039
NULL ratings out of 31,225 (96.2%). Until the mart is fixed, Panel B must split `Unrated` out
explicitly and relabel buckets as star counts. Never render "Poor" for a missing rating.

### V3.5 — Discount dependency

| Element | Specification |
|---|---|
| **Section** | Discount dependency (diagnostic/detail) |
| **Heading** | Discount dependency by segment |
| **Subheading** | Segments are defined by the share of a customer's orders that were discounted. **Read the "avg orders" column first** — segment membership is largely determined by order count, so the value and retention differences are an exposure artefact, not a discount effect. |
| **Business question** | Are discount-heavy customers less valuable — or does the segmentation just sort customers by how many orders they placed? |
| **Data source** | `ZOMATO.MARTS.MART_BASKET_DISCOUNT` |
| **Grain** | `discount_dependency_segment` (3 rows, aggregated from `customer_id`) |
| **Metrics** | Customers · **avg total orders** · avg % orders discounted · avg lifetime value (CAD) · 30-day reorder rate · customers missing an RFM match |
| **Calculation** | `COUNT(*)` · `AVG(total_orders)` · `AVG(pct_orders_discounted)` · `AVG(monetary_value_cad)` · `AVG(IFF(did_reorder_within_30d,1,0))` · `COUNT_IF(monetary_value_cad IS NULL)` |
| **Numerator ÷ denominator** | Reorder rate = **customers in segment who reordered within 30 days ÷ customers in segment with a non-null flag**. % discounted = **customer's discounted orders ÷ that customer's total orders**, then averaged |
| **Unit** | customers · orders · % · CAD · % · customers |
| **Aggregation** | COUNT, AVG |
| **X / Y axis** | n/a (table), 3 rows, sorted by customer count desc |
| **Legend** | None |
| **Data labels** | All values as text |
| **Tooltip** | Segment definition on hover: `Discount-Reliant = ≥50% of orders discounted` etc. |
| **Colours** | Ink text only. **No conditional formatting** — colour-scaling the value column would visually assert the very comparison the subheading warns is confounded |
| **Size** | Full width, ~200px (3 rows + header) |
| **Position** | Row 6, full width |
| **Filters** | None |
| **Interaction** | Header sort |
| **Default state** | 3 rows, customer count desc |
| **Footnote** | *🔬 Observational and mechanically confounded. Platform discount rate is 35.0%, so a customer with ~96 orders essentially cannot be "Full-Price" (0.65⁹⁶ ≈ 0). Verified avg total orders: Occasional 95.7, Discount-Reliant 19.0, Full-Price 4.4. 9,535 customers (9.5%) have no RFM match (the ~90K/~100K keyspace gap) and carry null value — they are counted in "customers" but excluded from the value average.* |

> **Why the proposed discount scatter (% discounted × value, sized by frequency, coloured by segment)
> is not used:** with 94.7% of customers in one segment and value ≈ a linear function of frequency
> (F4), the scatter would show a single dense cloud whose apparent gradient *is* the frequency
> confound, rendered as if it were a discount insight. The table with `avg total orders` adjacent makes
> the confound visible instead of decorative. Honest framing beats an impressive-looking chart.

---

# Part 9 — Page 4 — Method & Data Quality

A reference page. No new data work; high portfolio and interview value. It is what lets the three
analytical pages stay uncluttered.

## A. Page objective

Let any reader answer "can I trust this number, and how was it computed?" without cluttering the
analytical pages with disclaimers.

## B/C/D/E. Journey, navigation, filters

Sidebar section **Reference**. No filters. Reached from any footnote.

## F. Layout

`st.tabs` — the one justified use of tabs in this dashboard, since these are parallel reference tables
nobody reads top-to-bottom.

| Tab | Content |
|---|---|
| **Metric dictionary** | The full §11 table: metric · badge (✅/⚠️/🔬/🧮) · formula with explicit numerator ÷ denominator · source · grain |
| **Proxies & limitations** | The §1.2 proxy table, the ~90K/~100K keyspace gap (90,428 scored of 99,969 ordering customers; $59.9M of $66.3M), the 0.035% GMV reconciliation gap, month-length effects, 41% restaurant-rating coverage, rating-bucket NULL handling |
| **Null results log** | **The page's differentiator.** Four verified non-findings with their numbers: first-order delivery speed (0.65pp spread), rating (0.27pp), discount (0.06pp), and `repeat_restaurant_rate` ≈ 0 vs a 6.7e-06 random baseline. Plus `corr(F,M) = 0.998` and demographics ~0. Each with a one-line note on what Phase B would need to test it properly |
| **Lineage** | Raw → staging → marts → visual map (from `STREAMLIT_DASHBOARD_DATA_MAP.md`), and what is **not** usable: `stg_food`/`stg_menu` key-type incompatibility, `stg_reviews` 2.96% coverage |
| **Data freshness** | Dataset span 2024-01-01 → 2026-06-30, `recency_anchor_date` = 2026-06-30, cache TTL 1 hour, row counts per mart |

Recording null results explicitly is the single cheapest credibility gain available here: it
demonstrates that the analysis was allowed to come back empty, which is exactly what an interviewer
probes for.

---

# Part 10 — Optional Restaurant & Food page: verdict

**Recommendation: do not build it.** The brief asked me to verify readiness rather than assume it. Here
is the verification.

| Check | Result | Verdict |
|---|---|---|
| `fct_order_items` row count / coverage | 22,998,179 rows; covers **all 10M** orders; 1–6 items per order (mean 2.30) | ✅ Complete |
| `fct_order_items.food_id` → `stg_food.food_id` | `stg_food.food_id` is **TEXT** (`'fd0'`); item `food_id` is **NUMBER** (0–1,048,562). **0 of 371,561 menu ids match any of 369,279 item ids** | ⛔ **Fatal** — no dish names, no veg/non-veg, no menu price |
| `stg_menu` coverage | 1,179,936 rows but only **12,286 restaurants (8.3%** of 148,541); same TEXT food-id problem | ⛔ Unusable for item analysis |
| `fct_order_sales.restaurant_id` → `stg_restaurants.id` | **148,541 of 148,541 (100%)**; all 10M orders match | ✅ Fully joinable |
| `stg_restaurants` completeness | name 99.94%, cost 99.91%, cuisine 99.93%, **rating only 61,441/148,541 = 41.4%** | 🟡 Partial |
| Restaurant dimension rating vs actual order ratings | `corr = 0.0009` (n = 35,748 restaurants with ≥50 rated orders) | ⛔ The dimension's rating measures nothing observable |
| Restaurant materiality | median **40 orders**; max 501; **top restaurant = 0.023% of GMV** ($15,143 of $66.3M) | ⛔ No restaurant is material; a "top restaurants" leaderboard is a vanity chart |
| Signal across restaurant volume tiers | GMV/order 6.26 / 6.60 / 6.89 / 6.87; avg rating 4.1448 / 4.1460 / 4.1449 / 4.1456 | ⛔ Flat — no differentiation to analyse |
| `stg_reviews` | 300,000 rows over 295,541 orders = **2.96%** coverage; adds only free-text `comment` | ⛔ Too sparse; `customer_rating` already covers 6.4M orders |

**Conclusion.** Restaurant-level aggregation is *technically* sound (a clean 100% join) but
*analytically* empty: no restaurant carries meaningful share, and every quality metric is flat across
volume tiers. Item-level analysis is outright impossible because of the key-type mismatch. A fifth page
built on this would be four charts with no findings — which actively damages a portfolio, because a
reviewer who checks will find the same flatness.

**What to do instead** (already specified):

1. **Restaurant lookup expander on Page 1** (§6) — framed as operational lookup, minimum 100 orders,
   with the 0.023%-share caveat stated.
2. **Cuisine tags on Page 1 (V1.7)** — the one genuinely informative slice of the menu dimension, via
   `SPLIT_TO_TABLE` on `fct_order_sales.cuisine`. No join to the broken food keys needed.
3. **Log the blocker on the Method page** so the gap is a documented finding rather than a silent
   omission. If the key mismatch is ever fixed upstream (e.g. `stg_food` keys cast to match item
   `food_id`), reopen this decision — the coverage is otherwise complete.

---

# Part 11 — Metric dictionary

Every ratio states its numerator and denominator. Verified values as of 2026-09-29, full date range.

## 11.1 Commercial

| Metric | Formula | Verified | Notes |
|---|---|---|---|
| GMV (CAD) | `SUM(gmv_cad)` over `MART_EXECUTIVE_SUMMARY`; delivered orders only | 66,272,550.64 | Direct from `fct_order_sales` gives 66,295,518.20 — a **0.035%** gap from `inr_to_cad(SUM(x))` vs `SUM(inr_to_cad(x))` rounding. **Use the mart as the single source** for GMV on Page 1 |
| Delivered orders | `SUM(delivered_orders)` | 9,150,122 | 91.50% of 10,000,000 |
| **AOV (CAD)** | **GMV ÷ delivered orders** | 7.2428 | Ratio of aggregates. `AVG(aov_cad)` gives 7.2414 — wrong method, benign gap here |
| **Order failure rate** | **(cancelled + refunded) ÷ total orders** | 8.50% | 599,251 + 250,627 ÷ 10,000,000 |
| Cancellation rate | cancelled ÷ total orders | 5.99% | |
| Refund rate | refunded ÷ total orders | 2.51% | |
| **Discount penetration** | **discounted orders ÷ all orders** | 35.01% | 3,501,291 ÷ 10,000,000 |
| **Discount as % of GMV** | **total discount (CAD) ÷ GMV (CAD)** | 9.57% | 6,339,786.52 ÷ 66,272,550.64 |
| Mean discount when used | `AVG(discount_cad)` over discounted orders | 1.81 CAD | |

## 11.2 Customer activity

| Metric | Formula | Verified | Notes |
|---|---|---|---|
| **Monthly active customers** | `MAX(monthly_active_users)` per month, latest complete month | 84,972 (2026-06); peak 85,613 (2026-05) | ⚠️ Calendar-month, not rolling 30-day. **`MAX` per month, never `AVG` across days** — `AVG` gives 77,372 |
| Daily active customers | `daily_active_users` | — | Distinct customers ordering that day |
| **Monthly retention rate** | **customers active in month *M* who were also active in *M−1*  ÷  customers active in *M−1*** | 89.2% (2026-06); range 75.3% → 90.0% | Null for 2024-01. `AVG` across days gives 84.62% — wrong |
| Monthly churn rate | `1 − monthly retention rate` | 10.8% latest | |
| Orders per active customer | orders in month ÷ monthly active customers | ~5.5 latest | 🧮 Derived, tooltip only |

## 11.3 Retention & activation — **all customer-weighted**

| Metric | Formula | Verified (weighted) | Currently shown (unweighted) |
|---|---|---|---|
| **2nd order ≤ 7 days** | **first-time customers whose 2nd delivered order was ≤7 days after their 1st ÷ all 99,963 first-time customers** | **29.35%** | 8.76% ❌ |
| **2nd order ≤ 14 days** | same, ≤14 days | **44.82%** | 15.40% ❌ |
| **2nd order ≤ 30 days** | same, ≤30 days | **64.82%** | 29.49% ❌ |
| Ever placed a 2nd order | customers with a non-null 2nd order date ÷ all first-time customers | 99.89% | — |
| **Median days to 2nd order** | `MEDIAN(days_to_second_order)` over customers who reordered | **18 days** | 58.8 (mean of per-cohort medians) ❌ |
| **Cohort retention rate** | **distinct cohort customers with ≥1 delivered order in period *p* ÷ cohort size** | per cell | Correct in the mart |
| **Platform weighted retention at period *p*** | **Σ active customers ÷ Σ cohort sizes** across qualifying cohorts | per period | Use this as V3.2's benchmark, not `AVG(retention_rate)` |
| 30-day reorder rate (pooled) | customers reordering within 30 days ÷ all customers | 64.82% | Reference line for V3.4 |
| ~~Repeat restaurant rate~~ | ~~2nd order at same restaurant ÷ customers who reordered~~ | **≈0 (max 1.58e-05)** | **Void** — random baseline 6.7e-06 |

Equivalence check performed: weighting `mart_activation` by `cohort_size` and recomputing from
`mart_retention_diagnostic` at customer grain give **identical** results (0.29348 / 0.44820 / 0.64825),
confirming the weighted formula is the right one.

## 11.4 Customer value

| Metric | Formula | Verified |
|---|---|---|
| Customers scored | `COUNT(*) MART_CUSTOMER_RFM` | 90,428 (90.5% of 99,969) |
| Value covered | `SUM(monetary_value_cad)` | 59,937,887.66 (90.4% of platform GMV) |
| Median orders per customer | `MEDIAN(frequency_orders)` | 55 (mean 91.5, p95 289, max 8,284) |
| Median customer value | `MEDIAN(monetary_value_cad)` | 398.39 CAD (p95 2,096, max 60,729) |
| **Share of customers (segment)** | **segment customers ÷ 90,428** | Champions 25.62%, Lost 28.25% |
| **Share of value (segment)** | **segment monetary value ÷ 59,937,887.66** | Champions 59.14%, Lost 6.84% |
| **Segment AOV** | **segment total value ÷ segment total orders** | 7.09–7.41 across all 8 — **flat** |
| Recency (days) | `DATEDIFF(day, last_order_date, recency_anchor_date)` | anchor 2026-06-30 |
| Value decile share | decile value ÷ total scored value | 🧮 Derived in-query |

## 11.5 Fulfilment

| Metric | Formula | Verified |
|---|---|---|
| Median delivery time | `MEDIAN(delivery_time_min)` over delivered | 31 min (mean 31.07, range 8–87) |
| **Over-30-minute share** ⚠️ | **delivered orders with `delivery_time_min > 30` ÷ delivered orders** | **51.81%** — 4,740,847 ÷ 9,150,122 |
| Mean order rating | `AVG(customer_rating)` over rated orders | 4.145 |
| Rating coverage | rated orders ÷ delivered orders | 70.02% (64.07% of all orders) |
| Items per order | `COUNT(*) FCT_ORDER_ITEMS ÷ COUNT(DISTINCT order_id)` | 2.30 (range 1–6) |

## 11.6 Geography & cuisine

| Metric | Formula | Verified |
|---|---|---|
| City AOV | city GMV ÷ city delivered orders | — |
| City over-30-min share | city delivered orders >30 min ÷ city delivered orders | — |
| **Cuisine tag share** | **tag GMV ÷ Σ GMV across all tag-order pairs** (*not* ÷ platform GMV) | Chinese 2.36M orders / $16.1M; North Indian 2.34M / $15.9M |
| Top-20 city concentration | orders in top 20 cities ÷ all orders | 67.37% (top 10: 57.46%) |

---

# Part 12 — Responsive behaviour

Target: desktop 1100–2560px. Streamlit `st.columns` reflow is limited, so breakpoints are handled by
choosing column counts from a measured width where needed, and by never placing more than 3 charts in
one row.

| Row type | ≥1600px | 1280–1600px | 1100–1280px | <1100px |
|---|---|---|---|---|
| KPI row (5 tiles) | 5 across | 5 across, value drops to 30px | **3 + 2** wrap | 2 per row |
| Hero (V1.1, V2.1, V3.1) | Full width | Full width | Full width | Full width, height +15% |
| Hero companion (V1.2) | 110px panel | 110px | 96px | Hidden — the panel becomes unreadable below ~500px wide |
| 2-column rows (V1.3/1.4, V1.6/1.7, V2.2/2.3, V3.2/3.3) | 2 across | 2 across | 2 across | **Stack to 1 column**, each full width |
| 3-column row (V3.4 diagnostics) | 3 across | 3 across | **Stack to 1 column** — three 300px panels below ~1100px are too narrow for their bucket labels | 1 column |
| Tables (V1.8, V2.4, V3.5) | Full width, all columns | Full width | Drop `median delivery` from V1.8 | Horizontal scroll, `city`/`segment` column pinned |
| Sidebar collapsed | Content gains ~300px; hero and tables reflow to use it; column *counts* never change | same | same | same |

Rules:

- **Minimum chart width 320px.** Any layout that would go below it stacks instead.
- **Never 4+ charts in a row.** The widest row in this dashboard is 3, and only for the three
  deliberately-identical diagnostic panels.
- **Heights are fixed, widths are fluid** — prevents Plotly reflow jitter on resize.
- **Charts specify `use_container_width=True`** and never a pixel width.
- **Table heights are set to fit their row count** (8 segments → ~360px; 20 cities → ~420px) so no
  chart card gets its own nested scrollbar.
- **`max-width: 1560px` on `.block-container`** — beyond that, line lengths and chart aspect ratios
  degrade; the page centres instead of stretching.

---

# Part 13 — What NOT to show

The objective is not to maximise chart count. These are the explicit removals, demotions and merges.

## 13.1 Remove entirely

| Item | Where | Why |
|---|---|---|
| **GMV vs Late Delivery Rate dual-axis chart** | P1 `1_business_health.py:159–207` | Two arbitrary scales invent a correlation. The two facts are better served by the GMV hero and the delivery distribution separately |
| **Order Status donut** | P1:225–238 | Pie for part-to-whole with no trend. Replaced by V1.6, which shows mix *and* drift in the same space |
| **Payment Method Mix bar** | P1:249–265 | Answers no stated business question on a marketplace-health page, and double-encodes count as hue. If payment mix is ever needed it belongs in a Method/ops appendix |
| **Gender donut** | P2:196–203 | 3-slice pie, and demographics have **zero** association with value (corr ≤ 0.005) |
| **Occupation bar** | P2:228–242 | Same zero association; three demographic charts is two too many |
| **Cuisine volume-vs-value bubble scatter** | P1:337–357 | Plots 2,133 comma-delimited *combination* strings as categories, with bubble size = GMV = the y-axis (double-encoded). Replaced by V1.7 on split tags |
| **`Repeat Restaurant Rate`** | P3 (proposed as a KPI) | Verified ≈0 (max 1.58e-05 vs 6.7e-06 random baseline). Measures nothing |
| **NPS proxy** | Available in the mart | Adds nothing next to the rating distribution; a proxy NPS is more likely to be misread as a real NPS than to inform a decision. Documented on the Method page instead |
| **`app.py` intro redirect** | `app.py:11` | Replaced by a real `st.navigation` entry point |
| **Per-chart metric radio** | P1:82–87 | Filters belong in one row above what they scope, never inside a chart card |
| **Inline `st.warning` caveat blocks** | P2:265–272, P3:256–264 | Large amber blocks compete with the charts. Replaced by per-visual footnotes + the Method page |

## 13.2 Demote to an expander

| Item | From | To |
|---|---|---|
| Age distribution + income bracket | P2 main column | P2 expander, with the verified "no association with value" footnote |
| Restaurant detail | (would have been Page 5) | P1 expander, framed as operational lookup |
| Cohort size reference table | — | P3 expander |

## 13.3 Replace

| Current | Replacement | Reason |
|---|---|---|
| Two separate GMV / Orders charts with a radio toggle | One GMV hero + linked order-volume panel (V1.1/V1.2) | AOV is flat, so the two series are the same shape; showing them as co-equal tells one story twice |
| RFM bubble map (r/f/m combo level) + customer-count bar + revenue treemap (**3 charts**) | Value-concentration hero (V2.1) + segment matrix (V2.4) (**2 elements**) | The three charts each showed a slice of one table. The matrix carries all of it; the hero carries the single finding |
| Frequency × Monetary scatter (proposed) | Recency × Frequency density (V2.2) | `corr(F,M) = 0.998` — the proposed scatter is a diagonal line |
| `RdYlGn` cohort heatmap | Sequential single-hue blue | Diverging scale on a magnitude measure invents a good/bad midpoint |
| Auto-scaled diagnostic bars | Fixed 0–100% axis + reference line + null-result label | A 0.27–0.65pp spread currently fills the full plot width |
| Discount segment value table | Same table + `avg total orders` column + confound footnote | Makes the mechanical confound visible rather than presenting an artefact as a finding |

## 13.4 Net effect

| | Before | After |
|---|---|---|
| Analytical pages | 3 | 3 (+1 reference) |
| Charts + tables | 15 | 13 across 3 analytical pages (+4 reference tables) |
| Pie/donut charts | 2 | 0 |
| Dual-axis charts | 1 | 0 |
| Unweighted-mean KPIs | 5 | 0 |
| Visuals with a stated business question | 0 | all |
| Documented null results | 0 | 4 |

---

# Part 14 — Implementation notes

## 14.1 File structure

```
streamlit_dashboard/
├── app.py                     # st.navigation entry point + sidebar filters (no redirect)
├── views/
│   ├── marketplace_health.py
│   ├── customer_value.py
│   ├── retention.py
│   └── method.py
├── queries/                   # one module per page; all aggregation in SQL
│   ├── marketplace.py
│   ├── customers.py
│   └── retention.py
└── utils/
    ├── snowflake_connection.py   # unchanged
    ├── theme.py                  # replaced: validated tokens (§4.1)
    ├── style.py                  # NEW: the CSS block from §4.3
    ├── filters.py                # NEW: sidebar filters + session_state + context chips
    └── charts.py                 # NEW: figure factories enforcing the design system
```

`pages/` → `views/` because `st.navigation` supersedes the implicit `pages/` directory, and leaving
both would double the sidebar entries.

## 14.2 Streamlit component mapping

| Need | Component | Note |
|---|---|---|
| Navigation | `st.navigation` + `st.Page` | Grouped sections (§3.2) |
| KPI tiles | `st.columns` + `st.metric` | `border=True`; CSS normalises heights. `delta_color="off"` for AOV (§6 K1.3) |
| Filters | `st.date_input` (range), `st.multiselect`, `st.segmented_control`, `st.select_slider`, `st.selectbox` | All in `st.sidebar`, all keyed into `st.session_state` |
| Section structure | `st.container` + a CSS `.section-rule` div | Gives real 48px section spacing, which `st.divider()` does not |
| Charts | Plotly via `st.plotly_chart(fig, use_container_width=True)` | `template="plotly_white"`, titles in HTML above the chart not inside the figure |
| Tables | `st.dataframe` + `st.column_config` | `ProgressColumn` for the one conditional column; `NumberColumn(format=...)`; `height` set to fit rows |
| Detail sections | `st.expander` | Labelled with what's inside; never hides an interpretation-changing caveat |
| Reference tables | `st.tabs` | Method page only |
| Visual headings/footnotes | `st.markdown` with `.viz-h` / `.viz-sub` / `.viz-note` | Consistent typography (§4.2) |

Avoided: `st.tabs` on analytical pages (hides content that should be scannable), nested expanders,
`st.balloons`/emoji-as-decoration, and `st.header` defaults (CSS-controlled instead).

## 14.3 Push aggregation into SQL

Replaces the `SELECT *` + pandas `groupby` pattern (§2.7). Example — the Page 3 diagnostic panel, from
99,963 rows down to 4:

```sql
-- queries/retention.py :: delivery_speed_reorder()
select
    delivery_speed_bucket,
    count(*)                                             as customers,
    count_if(did_reorder_within_30d)                     as reordered_30d,
    count_if(did_reorder_within_30d)::float / count(*)    as reorder_rate_30d
from ZOMATO.MARTS.MART_RETENTION_DIAGNOSTIC
group by delivery_speed_bucket
order by min(first_order_delivery_time)      -- speed order, not rate order
```

And the corrected activation KPIs (§11.3):

```sql
-- queries/retention.py :: activation_kpis()
select
    sum(pct_2nd_order_within_7d  * cohort_size) / sum(cohort_size) as d7,
    sum(pct_2nd_order_within_14d * cohort_size) / sum(cohort_size) as d14,
    sum(pct_2nd_order_within_30d * cohort_size) / sum(cohort_size) as d30,
    sum(cohort_size)                                               as first_time_customers
from ZOMATO.MARTS.MART_ACTIVATION
```

Expected effect: ~380k rows per cold load → under 1,000. Keep `@st.cache_data(ttl=3600)`; add
`show_spinner=False` and hold the previous render on re-filter rather than flashing a skeleton.

## 14.4 Accessibility checklist (per the design-system rules)

- [ ] Every chart with ≥2 series has a legend **and** ≤4 series are also direct-labelled — identity is never colour-alone
- [ ] Every chart has a table-view twin (the matrices on each page serve this; the delivery histogram gets a "show data" expander)
- [ ] `#1baf7a` (aqua, 2.74:1 on light) appears **only** with visible direct labels — the validator's relief requirement
- [ ] Dark-mode steps declared from the same ramps and validated against `#1a1a19` — not an automatic inversion
- [ ] Gridlines and axis rules are **solid** hairlines, one shade off the surface; no dashes
- [ ] Hover hit areas ≥24px; the cohort heatmap uses cell-sized targets, not point targets
- [ ] No value printed on every data point — direct labels are selective (endpoints, extremes, the ≤12-mark charts)
- [ ] Suppressed heatmap cells are distinguishable by **hatch pattern**, not colour alone
- [ ] Status colours always ship with a text label

## 14.5 Suggested build order

1. `utils/style.py`, `utils/theme.py` (validated tokens), `app.py` + `st.navigation`, `utils/filters.py` — the shell and design system.
2. **Fix the five unweighted-mean KPIs** (§2.1). Highest-value change in the whole redesign; it is a correctness fix, not cosmetics.
3. Page 3 — hero heatmap defaults + suppression, then the null-result panel with fixed axes. The page with the most integrity risk.
4. Page 1 — hero pair, delivery distribution, city matrix; delete the dual-axis chart and the donuts.
5. Page 2 — concentration hero, R×F density, segment matrix; demote demographics.
6. Page 4 — Method & Data Quality (mostly transcription of §1.2, §11 and the null-results log).
7. Optional: the `rating_bucket` mart fix (§2.6) plus its `accepted_values` update and a `dbt build --select mart_retention_diagnostic+`.

---

## Appendix — verification provenance

Every figure in this document came from live Snowflake queries run on 2026-09-29 against
`ZOMATO.MARTS` and `ZOMATO.STAGING` (three profiling passes: platform shape and join coverage; food/menu
joinability, restaurant concentration and delivery distribution; aggregation-bug confirmation and exact
KPI values). Palette subsets were validated with the `dataviz` skill's
`scripts/validate_palette.js` in both light and dark modes, including the `--pairs all` and `--ordinal`
gates. Where this document contradicts an existing model comment, YAML description or planning note,
the live value is authoritative and the discrepancy is flagged in §2.
