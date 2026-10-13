import pandas as pd
import streamlit as st

from utils.style import inject_style, page_header

inject_style()

page_header(
    "Method & Data Quality",
    "Can I trust this number, and how was it computed? A reference page — no new data work.",
)

tab_dict, tab_proxy, tab_null, tab_lineage, tab_fresh = st.tabs(
    ["Metric dictionary", "Proxies & limitations", "Null results log", "Lineage", "Data freshness"]
)

with tab_dict:
    st.markdown("#### Commercial")
    st.dataframe(
        pd.DataFrame(
            [
                ("GMV (CAD)", "SUM(gmv_cad), delivered orders only", "MART_EXECUTIVE_SUMMARY", "✅ Measured"),
                ("AOV (CAD)", "GMV ÷ delivered orders (ratio of aggregates, never AVG(aov))", "MART_EXECUTIVE_SUMMARY", "✅ Measured"),
                ("Order failure rate", "(cancelled + refunded) ÷ total orders", "MART_EXECUTIVE_SUMMARY", "✅ Measured"),
                ("Discount penetration", "discounted orders ÷ all orders", "FCT_ORDER_SALES", "✅ Measured"),
            ],
            columns=["Metric", "Formula", "Source", "Badge"],
        ),
        hide_index=True, width="stretch",
    )
    st.markdown("#### Customer activity")
    st.dataframe(
        pd.DataFrame(
            [
                ("Monthly active customers", "MAX(monthly_active_users) per month — never AVG across days", "MART_EXECUTIVE_SUMMARY", "⚠️ Proxy (calendar-month, not rolling 30-day)"),
                ("Monthly retention rate", "customers active in month M who were also active in M-1 ÷ customers active in M-1", "MART_EXECUTIVE_SUMMARY", "✅ Measured"),
            ],
            columns=["Metric", "Formula", "Source", "Badge"],
        ),
        hide_index=True, width="stretch",
    )
    st.markdown("#### Retention & activation — all customer-weighted")
    st.dataframe(
        pd.DataFrame(
            [
                ("2nd order ≤7/14/30 days", "customers whose 2nd order fell within N days ÷ all first-time customers (ratio of aggregates, never AVG(pct) across cohorts)", "MART_RETENTION_DIAGNOSTIC", "🧮 Derived"),
                ("Cohort retention rate", "distinct cohort customers active in period p ÷ cohort size", "MART_COHORT_RETENTION", "✅ Measured"),
                ("Platform weighted retention", "Σ active customers ÷ Σ cohort sizes across qualifying cohorts (never AVG(retention_rate))", "MART_COHORT_RETENTION", "🧮 Derived"),
                ("Repeat restaurant rate", "2nd order at same restaurant ÷ customers who reordered", "MART_ACTIVATION", "⛔ Void — ≈0, indistinguishable from chance"),
            ],
            columns=["Metric", "Formula", "Source", "Badge"],
        ),
        hide_index=True, width="stretch",
    )
    st.markdown("#### Customer value")
    st.dataframe(
        pd.DataFrame(
            [
                ("Share of customers / value (segment)", "segment customers ÷ total scored; segment value ÷ total scored value", "MART_CUSTOMER_RFM", "✅ Measured"),
                ("Segment AOV", "segment total value ÷ segment total orders (ratio of aggregates)", "MART_CUSTOMER_RFM", "🧮 Derived"),
                ("Recency (days)", "DATEDIFF(day, last_order_date, recency_anchor_date)", "MART_CUSTOMER_RFM", "✅ Measured"),
            ],
            columns=["Metric", "Formula", "Source", "Badge"],
        ),
        hide_index=True, width="stretch",
    )

with tab_proxy:
    st.markdown("#### Proxy metrics — stand in for a measurement the source data does not contain")
    st.dataframe(
        pd.DataFrame(
            [
                ("is_late_delivery_proxy", "No promised-ETA/SLA field exists. Fixed 30-min absolute threshold, which sits at the distribution's own median — the resulting ~52% rate is not an operations signal. Shown only as a distribution with the threshold annotated, never as a KPI."),
                ("nps_score_proxy", "Built from 1–5 stars (5=promoter, 4=passive, ≤3=detractor), not a 0–10 recommend question. Excluded from analytical pages — adds no decision value next to the raw rating distribution."),
                ("monthly_active_users", "Calendar-month active, not rolling 30-day. Repeated across every day of the month — always aggregated with MAX per month, never AVG across days."),
                ("repeat_restaurant_rate", "Structurally meaningless in this dataset — observed rate is indistinguishable from a random-chance baseline given ~148K restaurants. Excluded entirely."),
            ],
            columns=["Metric", "Why it is a proxy / how it's handled"],
        ),
        hide_index=True, width="stretch",
    )
    st.markdown("#### Known keyspace / reconciliation gaps")
    st.markdown(
        """
        - **RFM scoring coverage**: `MART_CUSTOMER_RFM` scores customers on the `dim_customer` keyspace,
          which is smaller than the full order-side customer keyspace. A small share of ordering
          customers are not RFM-scored — see the Customer Value page's KPI row for the exact split.
        - **GMV reconciliation**: GMV computed via the mart's currency conversion can differ very
          slightly (a fraction of a percent) from converting each order individually, due to
          rounding order of operations. The mart is the single source of truth used throughout
          this dashboard.
        - **Restaurant rating coverage**: a meaningful share of restaurants have no rating on file,
          and the restaurant dimension's rating is not correlated with actual order-level ratings —
          see the Lineage tab.
        - **Rating buckets**: ratings are whole stars, so this dashboard re-buckets
          `MART_RETENTION_DIAGNOSTIC.first_order_rating` by star count (5, 4, 3, 1-2) rather than
          using the mart's decimal-range `rating_bucket`. Unrated first orders are their own bucket
          in both.
        """
    )

with tab_null:
    st.markdown("#### Documented non-findings")
    st.markdown(
        "Recording null results explicitly is the cheapest credibility gain available on a "
        "dashboard like this — it demonstrates the analysis was allowed to come back empty."
    )
    st.dataframe(
        pd.DataFrame(
            [
                ("First-order delivery speed vs 30-day reorder", "Spread across speed buckets is well under 1 percentage point", "Null — no material association"),
                ("First-order rating vs 30-day reorder", "Spread across rating buckets is well under 1 percentage point", "Null — no material association"),
                ("First-order discount vs 30-day reorder", "Spread between discounted/non-discounted first orders is a fraction of a percentage point", "Null — no material association"),
                ("Repeat restaurant rate", "Observed rate ≈ random-chance baseline", "Void — measures nothing"),
                ("Frequency vs Monetary value (RFM)", "Near-perfect correlation — M is ~a linear restatement of F", "Redundant dimension, not a finding"),
                ("Demographics (age/income/family size) vs value", "Correlations near zero across all three", "Null — descriptive only, doesn't explain value"),
            ],
            columns=["Comparison", "What was found", "Verdict"],
        ),
        hide_index=True, width="stretch",
    )

with tab_lineage:
    st.markdown("#### Raw → staging → marts → visual")
    st.markdown(
        """
        - `RAW` (Snowflake, loaded outside dbt) → `staging` (1:1 views, type casting, minimal parsing)
          → `marts` (core facts/dimension, then subject-area marts) → this dashboard.
        - **Not usable, and why:** menu/food dimension keys are a different data type than the
          order-item keys that reference them, so there is zero overlap between them — dish-level
          and veg/non-veg analysis is not possible with the current source data. Review-text coverage
          is too sparse (well under 5% of orders) to add signal beyond the order-level rating that
          already covers the large majority of delivered orders.
        - **Restaurant-level analysis**: the join from orders to the restaurant dimension is
          complete, but no restaurant carries meaningful share of platform GMV and quality metrics
          are flat across volume tiers — see the Restaurant lookup expander on the Marketplace
          Health page for the honest framing (operational lookup, not a leaderboard).
        """
    )

with tab_fresh:
    st.markdown("#### Data freshness & pipeline")
    st.markdown(
        """
        - Dataset span: 2024-01-01 → 2026-06-30 reported (orders exist from 2023-07-01: a 6-month
          generator burn-in so pre-2024 customers aren't mislabelled as new in Jan 2024)
        - Order behaviour is calibrated synthetic data (data_generator/), not real Zomato performance
        - Recency anchor (`recency_anchor_date`): the dataset's own max(order_date) — not
          `current_date()` — so recency-based scores stay stable across reruns of this static/
          historical dataset instead of drifting by a day every time the pipeline runs without new
          data landing.
        - Query cache TTL: 1 hour (`@st.cache_data(ttl=3600)`) on every query function.
        - Design-system note: chart colors are fixed light-mode hex values (Plotly cannot read CSS
          custom properties), while the HTML chrome around each chart (headings, KPI cards, chips)
          follows the OS light/dark preference via injected CSS. This is an accepted scope limit.
        """
    )
