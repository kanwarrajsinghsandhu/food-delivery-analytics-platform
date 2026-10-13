# Streamlit Dashboard — Data Lineage Map

Traces every table/view queried by `streamlit_dashboard/` back through the dbt medallion layers
(Bronze `ZOMATO.RAW` → Silver `models/staging/` → Gold `models/marts/`) to the raw source CSVs.
Generated from the current state of `streamlit_dashboard/pages/*.py` and `zomato/models/`.

Three pages, four marts family groups:

```
app.py ──switch_page──▶ pages/1_business_health.py   (lands here by default)
                        pages/2_customer_value.py
                        pages/3_retention_activation.py
```

---

## Page 1 — `1_business_health.py` ("Business Health")

**Objective of the page:** platform-level pulse check — is GMV/orders growing, is retention moving
with it, and where are the operational soft spots (late deliveries, order status/payment mix, city
and cuisine performance)?

### Lineage diagram

```
RAW.ORDERS (CSV: orders.csv)
      │
      ▼
stg_orders (view)                  [Silver]
      │
      ▼
fct_order_sales (table, MARTS)     [Gold — core fact, grain=order_id]  ───┐
      │                                                                  │
      ▼                                                                  │ (queried directly,
mart_executive_summary (table, MARTS)                                    │  aggregated ad hoc
   [Gold — subject mart, grain=order_date]                               │  by the dashboard)
      │                                                                  │
      ▼                                                                  ▼
  ┌─────────────────────────┐                              ┌──────────────────────────┐
  │ SELECT * ORDER BY        │                              │ GROUP BY order_date/      │
  │ order_date                │                              │ order_status/payment_     │
  │ → KPI row + trend charts │                              │ method/city/cuisine        │
  └─────────────────────────┘                              └──────────────────────────┘
```

### Tables/views used

#### `ZOMATO.RAW.ORDERS` (raw CSV: `orders.csv`)
- **Objective:** bronze source — one row per order as dumped from the operational system, no cleaning.
- **Fields:** `order_id, order_timestamp, order_date, user_id, r_id, restaurant_city, cuisine, items_count, sales_qty, subtotal, discount, delivery_fee, gst, sales_amount, currency, payment_method, order_status, customer_rating, delivery_time_min`

#### `stg_orders` (view, Silver)
- **Objective:** cast/rename raw order columns to conformed types and names; splits `restaurant_city` into `city_area`/`city`; derives `is_delivered`. Faithful to raw grain — no joins, no aggregation.
- **Fields:** `order_id, order_timestamp, order_date, customer_id, restaurant_id, city_area, city, cuisine, items_count, sales_qty, subtotal, discount, delivery_fee, gst, sales_amount, currency, payment_method, order_status, customer_rating, delivery_time_min, is_delivered`

#### `ZOMATO.MARTS.FCT_ORDER_SALES` (table, Gold — core)
- **Grain:** `order_id`
- **Objective:** atomic Gold fact — one row per order with every commercial measure in both INR and CAD, plus fulfillment/payment attributes. Foundation fact table that all order-derived marts build from. Directly queried by the dashboard for order-status mix, payment-method mix, late-delivery rate, and city/cuisine leaderboards (all computed as on-the-fly `GROUP BY`s, not pre-aggregated marts).
- **Fields:** `order_id, customer_id, restaurant_id, order_timestamp, order_date, city_area, city, cuisine, items_count, sales_qty, subtotal_inr, subtotal_cad, discount_inr, discount_cad, delivery_fee_inr, delivery_fee_cad, gst_inr, gst_cad, sales_amount_inr, sales_amount_cad, original_currency, payment_method, order_status, is_delivered, is_cancelled, is_refunded, is_discounted, customer_rating, delivery_time_min, is_late_delivery_proxy`
- **Caveat surfaced on the page:** `is_late_delivery_proxy` is a fixed 30-minute threshold, not a real ETA/SLA breach (no promised-delivery-time field in source data).

#### `ZOMATO.MARTS.MART_EXECUTIVE_SUMMARY` (table, Gold — executive subject mart)
- **Grain:** `order_date` (one row per calendar day)
- **Objective:** CXO dashboard mart — headline platform KPIs per day: DAU, calendar-month MAU, GMV/AOV (delivered orders only), an NPS proxy from star ratings, and month-over-month retention/churn. Directly powers the KPI row and the two primary trend line charts on this page.
- **Fields:** `order_date, daily_active_users, monthly_active_users, gmv_inr, aov_inr, nps_score_proxy, monthly_retention_rate, monthly_churn_rate`
  - Dashboard also references `GMV_CAD`, `AOV_CAD`, `TOTAL_ORDERS` — these exist as CAD-equivalent/order-count columns produced by the model's SQL alongside the documented INR ones (see `mart_executive_summary.sql` for the full `select *` column set beyond the YAML-documented subset).
- **Proxy caveats:** MAU is calendar-month active (not rolling 30-day); NPS is built from 1-5 star ratings, not a real 0-10 recommend question.

---

## Page 2 — `2_customer_value.py` ("Customer Value")

**Objective of the page:** which customer segments (via RFM — Recency/Frequency/Monetary quintile
scoring) carry the most value, and who are these customers demographically?

### Lineage diagram

```
RAW.ORDERS                                    RAW.USERS (CSV: users.csv)
    │                                                │
    ▼                                                ▼
stg_orders (view)                              stg_users (view)      [Silver]
    │                                                │  (education-filtered:
    ▼                                                │   ~90,428 of 100K raw rows survive)
fct_order_sales (table, MARTS)  [Gold-core]           │
    │                                                ▼
    ▼                                          dim_customer (table, MARTS)  [Gold-core, grain=customer_id]
int_customer_order_sequence (table, MARTS)            │        │
[Gold-core backbone, grain=customer_id×order_sequence] │        │
    │                                                  │        │
    └───────────────────┬────────────────────────────┘        │
                         ▼                                      │
              mart_customer_rfm (table, MARTS)                  │
           [Gold — customer subject mart, grain=customer_id]     │
                         │                                      │
                         ▼                                      ▼
          SELECT * ORDER BY monetary_value_cad DESC     SELECT age, gender,
          → segment filter, KPIs, bar/treemap/           occupation, monthly_income,
            bubble charts, segment value table            family_size → demographics
```

### Tables/views used

#### `ZOMATO.RAW.USERS` (raw CSV: `users.csv`)
- **Objective:** bronze source — one row per registered user, includes PII (name, email, password).
- **Fields:** `(index), user_id, name, email, password, Age, Gender, Marital Status, Occupation, Monthly Income, Educational Qualifications, Family size`

#### `stg_users` (view, Silver)
- **Objective:** casts types, drops `password` (PII exclusion enforced by the `no_pii_exposure` test), standardizes income into a categorical band plus a numeric midpoint (INR & CAD). Filters to rows with a recognized `education` value (~90,428 of 100,000 raw rows survive — this is the source of the "~90K vs ~100K keyspace mismatch" documented across the mart layer).
- **Fields:** `user_id, name, email, age, gender, marital_status, occupation, monthly_income, monthly_income_midpoint_inr, monthly_income_midpoint_cad, education, family_size`

#### `ZOMATO.MARTS.DIM_CUSTOMER` (table, Gold — core)
- **Grain:** `customer_id`
- **Objective:** Gold customer dimension — demographic attributes only (renamed key to `customer_id` to match the fact tables for joins). Deliberately holds **no** order-derived metrics (recency/frequency/monetary, segmentation) — those live in `mart_customer_rfm`. Directly queried by the dashboard for the demographic breakdown charts (gender mix, age histogram, occupation, income bracket).
- **Fields:** `customer_id, name, email, age, gender, marital_status, occupation, monthly_income, monthly_income_midpoint_inr, monthly_income_midpoint_cad, education, family_size`

#### `ZOMATO.MARTS.FCT_ORDER_SALES` — *(see Page 1; upstream input to the backbone below, not queried directly on this page)*

#### `ZOMATO.MARTS.INT_CUSTOMER_ORDER_SEQUENCE` (table, Gold — core backbone, not queried directly by Streamlit)
- **Grain:** `customer_id` × `order_sequence`
- **Objective:** shared backbone — one row per delivered order per customer, chronologically ordered, carrying order-sequence number (1st, 2nd, 3rd…) and acquisition-cohort month. Every customer-lifecycle mart (RFM, retention diagnostic, cohort retention, activation, discount dependency) builds from this instead of re-deriving "first order"/"cohort month" independently.
- **Fields:** `customer_id, order_id, order_sequence, order_date, acquisition_cohort_month, recency_anchor_date, sales_amount_cad, discount_cad, restaurant_id` *(plus any other passthrough columns from `fct_order_sales` needed by downstream marts — see model SQL)*

#### `ZOMATO.MARTS.MART_CUSTOMER_RFM` (table, Gold — customer subject mart)
- **Grain:** `customer_id` (~90,428 rows — matches `dim_customer`'s education-filtered keyspace)
- **Objective:** RFM segmentation — Recency/Frequency/Monetary quintile scores (1–5) and a human-readable segment label (Champions, Loyal Customers, At Risk, Lost, etc.), counting delivered orders only. This is the primary driver of the page: segment filter, summary KPI tiles, customer-count bar, revenue treemap, RFM bubble map, and segment value matrix all read from this mart.
- **Fields:** `customer_id, first_order_date, last_order_date, recency_days, frequency_orders, monetary_value_cad, r_score, f_score, m_score, rfm_segment, segment_label`
- **Data-quality note surfaced on the page:** RFM is scored on `dim_customer`'s ~90K base; the retention/activation/discount marts on Page 3 use the full ~100K order-side population — the two are not directly comparable and no relationship is modeled between them here.

---

## Page 3 — `3_retention_activation.py` ("Retention & Activation")

**Objective of the page:** how quickly do customers return after their first order, how does that
vary by acquisition cohort, and which first-order experience factors (delivery speed, rating,
discount usage) associate with reordering? All framed as **observational, not causal** (no
confounder controls).

### Lineage diagram

```
RAW.ORDERS
    │
    ▼
stg_orders (view) ──▶ fct_order_sales (table, MARTS) [Gold-core]
                                │
                                ▼
              int_customer_order_sequence (table, MARTS)
            [Gold-core backbone, grain=customer_id × order_sequence]
                                │
        ┌───────────────┬──────┴───────┬───────────────────────────┐
        ▼               ▼              ▼                           ▼
mart_cohort_retention  mart_activation  mart_retention_diagnostic   (feeds into
[grain=cohort_month ×  [grain=cohort_   [grain=customer_id]          mart_basket_discount
 period_number]         month]                  │                    below)
        │               │                       │
        ▼               ▼                       │
  Cohort retention   Activation KPI row +        │
  heatmap             2nd-order-by-cohort bars   │
                                                   ▼
                                     Delivery-speed / rating
                                     reorder-rate bar charts
                                                   │
                     ┌─────────────────────────────┘
                     ▼
     mart_customer_rfm ──┐
                          ├──▶ mart_basket_discount [grain=customer_id]
     mart_retention_diag──┘         │
     (both joined in)               ▼
                          Discount-dependency segment table
```

### Tables/views used

*(`RAW.ORDERS` → `stg_orders` → `fct_order_sales` → `int_customer_order_sequence` — same as Pages 1–2 above; not repeated.)*

#### `ZOMATO.MARTS.MART_COHORT_RETENTION` (table, Gold — customer subject mart)
- **Grain:** `acquisition_cohort_month` × `period_number`
- **Objective:** classic cohort-retention curve — for each monthly acquisition cohort, what % placed at least one delivered order in each subsequent month. Powers the cohort-retention heatmap (rows = cohort, columns = period, values = retention %) and the cohort filter used across the page.
- **Fields:** `acquisition_cohort_month, period_number, cohort_size, active_customers, retention_rate`

#### `ZOMATO.MARTS.MART_ACTIVATION` (table, Gold — customer subject mart)
- **Grain:** `acquisition_cohort_month`
- **Objective:** first-to-second-order activation funnel per cohort — how many first-time customers return, how fast, at what value. Narrower than `mart_cohort_retention` (tracks specifically the *second* order, not any repeat). Powers the "Early Activation Rates" KPI row and the 7/14/30-day conversion bar chart by cohort.
- **Fields:** `acquisition_cohort_month, cohort_size, pct_2nd_order_within_7d, pct_2nd_order_within_14d, pct_2nd_order_within_30d, median_days_to_2nd_order, second_order_aov_cad, repeat_restaurant_rate`

#### `ZOMATO.MARTS.MART_RETENTION_DIAGNOSTIC` (table, Gold — customer subject mart)
- **Grain:** `customer_id`
- **Objective:** observed association between first-order experience (delivery speed, rating, discount use) and 30-day repeat-ordering. Explicitly flagged as observational/non-causal (no confounder controls). Powers the "First-Order Experience Drivers" delivery-speed and rating reorder-rate bar charts.
- **Fields:** `customer_id, first_order_id, first_order_date, acquisition_cohort_month, first_order_delivery_time, delivery_speed_bucket, first_order_rating, rating_bucket, first_order_discount_cad, did_use_discount_on_first_order, did_reorder, did_reorder_within_30d, second_order_date, days_to_second_order, repeat_order_count, repeat_aov_cad`

#### `ZOMATO.MARTS.MART_BASKET_DISCOUNT` (table, Gold — customer subject mart)
- **Grain:** `customer_id` (full ~100K order-side keyspace, wider than `dim_customer`'s ~90K)
- **Objective:** discount-dependency diagnostic — are discount-heavy customers actually valuable/retained, or is the platform subsidizing one-time, price-driven orders? Built on the order-sequence backbone, enriched by joining `mart_customer_rfm` (value) and `mart_retention_diagnostic` (retention). Powers the "Discount Dependency & Segment Value" table. Also observational/non-causal.
- **Fields:** `customer_id, total_orders, discounted_orders, pct_orders_discounted, total_discount_cad, avg_discount_cad_when_used, discount_dependency_segment, monetary_value_cad, frequency_orders, rfm_segment_label, did_reorder_within_30d`

---

## Cross-page summary table

| Mart / Table queried by Streamlit | Grain | Page(s) | Upstream staging | Upstream raw source |
|---|---|---|---|---|
| `FCT_ORDER_SALES` | order_id | 1 | `stg_orders` | `RAW.ORDERS` |
| `MART_EXECUTIVE_SUMMARY` | order_date | 1 | `stg_orders` | `RAW.ORDERS` |
| `MART_CUSTOMER_RFM` | customer_id | 2, 3 (join) | `stg_orders`, `stg_users` | `RAW.ORDERS`, `RAW.USERS` |
| `DIM_CUSTOMER` | customer_id | 2 | `stg_users` | `RAW.USERS` |
| `MART_COHORT_RETENTION` | cohort_month × period | 3 | `stg_orders` | `RAW.ORDERS` |
| `MART_ACTIVATION` | cohort_month | 3 | `stg_orders` | `RAW.ORDERS` |
| `MART_RETENTION_DIAGNOSTIC` | customer_id | 3 (+ join into basket_discount) | `stg_orders` | `RAW.ORDERS` |
| `MART_BASKET_DISCOUNT` | customer_id | 3 | `stg_orders` | `RAW.ORDERS` |

Not directly queried by Streamlit but sit in the lineage as shared building blocks:
`INT_CUSTOMER_ORDER_SEQUENCE` (backbone for every customer-lifecycle mart), `FCT_ORDER_ITEMS`
(item-level fact — no dashboard page currently reads this or the menu/food/restaurant/review
staging models: `stg_menu`, `stg_food`, `stg_restaurants`, `stg_reviews` are all unused by the
current dashboard).

---

*Generated 2026-09-29 from `streamlit_dashboard/pages/*.py` (SQL queries) and `zomato/models/**`
(schema YAML + model SQL). Re-generate if dashboard queries or mart schemas change.*
