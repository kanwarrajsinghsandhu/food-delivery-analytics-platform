import pandas as pd
import streamlit as st

from queries import retention as q
from utils.charts import (
    cohort_heatmap_figure,
    cohort_curve_figure,
    activation_windows_figure,
    diagnostic_panel_figure,
)
from utils.style import inject_style, page_header, context_chips, section_heading, viz_heading, viz_note

inject_style()

page_header(
    "Retention & Activation",
    "How fast new customers return, and what is — and isn't — associated with it.",
)

st.sidebar.markdown("### Page filters")
st.sidebar.info(
    "City and cuisine filters do not apply to cohort analysis — cohorts are defined by a "
    "customer's first order, so filtering by city would retroactively redefine cohort membership."
)

try:
    kpis = q.activation_kpis()
    sizes = q.cohort_sizes()

    min_size = st.sidebar.select_slider(
        "Minimum cohort size", options=[100, 500, 1000, 5000], value=100, key="ret_min_size"
    )
    qualifying = sizes[sizes["COHORT_SIZE"] >= min_size]

    context_chips(
        f"{kpis['first_time_customers']:,} customers · {len(sizes)} cohorts · "
        f"min cohort size {min_size} ({len(qualifying)} cohorts shown)"
    )

    k1, k2, k3, k4, k5 = st.columns(5)
    with k1:
        st.metric("2nd Order within 7 Days", f"{kpis['pct_7d']*100:.1f}%", f"of {kpis['first_time_customers']:,} first-time customers")
    with k2:
        st.metric("2nd Order within 14 Days", f"{kpis['pct_14d']*100:.1f}%", f"+{(kpis['pct_14d']-kpis['pct_7d'])*100:.1f}pp vs 7-day")
    with k3:
        st.metric("2nd Order within 30 Days", f"{kpis['pct_30d']*100:.1f}%", f"+{(kpis['pct_30d']-kpis['pct_14d'])*100:.1f}pp vs 14-day")
    with k4:
        st.metric("Median Days to 2nd Order", f"{kpis['median_days_to_2nd']:.0f}", "among those who reordered")
    with k5:
        st.metric("Ever Placed a 2nd Order", f"{kpis['pct_ever']*100:.1f}%", "near-universal — time windows carry the signal")

    # -- V3.1 HERO — Cohort retention heatmap ------------------------------------------
    viz_heading(
        "Cohort retention",
        "For each acquisition cohort, the share still ordering in each subsequent month. "
        "Cohort size is shown beside each row because sizes range widely.",
    )
    raw = q.cohort_retention_raw()
    raw["COHORT_LABEL"] = raw.apply(
        lambda r: f"{pd.Timestamp(r['ACQUISITION_COHORT_MONTH']):%b %Y} (n={int(r['COHORT_SIZE']):,})", axis=1
    )
    qualifying_months = set(qualifying["ACQUISITION_COHORT_MONTH"])
    raw_shown = raw[raw["ACQUISITION_COHORT_MONTH"].isin(qualifying_months)]
    pivot_pct = raw_shown.pivot(index="COHORT_LABEL", columns="PERIOD_NUMBER", values="RETENTION_RATE") * 100
    label_order = (
        raw_shown[["COHORT_LABEL", "ACQUISITION_COHORT_MONTH"]]
        .drop_duplicates()
        .sort_values("ACQUISITION_COHORT_MONTH", ascending=False)["COHORT_LABEL"]
    )
    pivot_pct = pivot_pct.reindex(label_order)
    suppressed_mask = pivot_pct.isna()
    st.plotly_chart(cohort_heatmap_figure(pivot_pct, suppressed_mask), width="stretch")
    small_cohorts = len(sizes) - len(qualifying)
    viz_note(
        f"{small_cohorts} of {len(sizes)} cohorts have fewer than {min_size} customers and are "
        f"hidden by default. A (cohort, period) pair with no active customers renders blank, not 0%."
    )

    # -- Retention in detail --------------------------------------------------------------
    section_heading("Retention in detail")
    c1, c2 = st.columns(2)
    with c1:
        cohort_options = sorted(qualifying["ACQUISITION_COHORT_MONTH"].tolist(), reverse=True)
        default_cohort = qualifying.sort_values("COHORT_SIZE", ascending=False).iloc[0]["ACQUISITION_COHORT_MONTH"]
        selected_cohort = st.selectbox(
            "Cohort",
            options=cohort_options,
            index=cohort_options.index(default_cohort) if default_cohort in cohort_options else 0,
            format_func=lambda d: f"{pd.Timestamp(d):%b %Y}",
            key="ret_cohort_select",
        )
        viz_heading(
            "Selected cohort retention curve",
            "One cohort's retention over time, with the platform-wide weighted curve behind it for comparison.",
        )
        sel_df = q.selected_cohort_curve(str(selected_cohort))
        bench_df = q.platform_weighted_retention(min_size)
        st.plotly_chart(
            cohort_curve_figure(sel_df, bench_df, f"{pd.Timestamp(selected_cohort):%b %Y}"),
            width="stretch",
        )
        viz_note(f"Cohorts below {min_size} customers are not offered — small cohorts swing on sampling noise alone.")
    with c2:
        viz_heading(
            "Activation windows",
            "Share of first-time customers placing a second order within each window. These are "
            "cumulative and nested, not a drop-off funnel.",
        )
        st.plotly_chart(activation_windows_figure(q.activation_windows()), width="stretch")
        viz_note("Presented as nested cumulative shares — the windows overlap by construction.")

    # -- First-order experience diagnostics (null result) ---------------------------------
    section_heading("First-order experience — observed association, no causal claim")
    pooled = q.pooled_reorder_rate()
    viz_note(
        f"No material difference found. All three comparisons sit close to the {pooled*100:.1f}% "
        f"platform reorder rate. Axes are fixed 0–100% so the size of the difference is legible.",
        null_result=True,
    )
    d1, d2, d3 = st.columns(3)
    with d1:
        st.markdown("**Delivery speed**")
        st.plotly_chart(diagnostic_panel_figure(q.delivery_speed_reorder(), "DELIVERY_SPEED_BUCKET", "REORDER_RATE_30D", pooled), width="stretch")
    with d2:
        st.markdown("**First-order rating**")
        st.plotly_chart(diagnostic_panel_figure(q.rating_reorder(), "RATING_BUCKET", "REORDER_RATE_30D", pooled), width="stretch")
    with d3:
        st.markdown("**First-order discount**")
        st.plotly_chart(diagnostic_panel_figure(q.discount_reorder(), "DISCOUNT_BUCKET", "REORDER_RATE_30D", pooled), width="stretch")
    viz_note(
        "🔬 Observational, not causal — no controls for city, cuisine, restaurant or customer "
        "segment. These are null results; a bucket difference this small is a hypothesis for "
        "future multivariate work, not a finding.",
        null_result=True,
    )

    # -- Discount dependency ----------------------------------------------------------------
    section_heading("Discount dependency")
    viz_heading(
        "Discount dependency by segment",
        "Read the 'avg orders' column first — segment membership is largely determined by order "
        "count, so the value and retention differences are an exposure artefact, not a discount effect.",
    )
    disc_df = q.discount_dependency()
    st.dataframe(
        disc_df.rename(
            columns={
                "DISCOUNT_DEPENDENCY_SEGMENT": "Segment",
                "CUSTOMERS": "Customers",
                "AVG_TOTAL_ORDERS": "Avg orders",
                "AVG_PCT_DISCOUNTED": "Avg % discounted",
                "AVG_VALUE_CAD": "Avg value (CAD)",
                "REORDER_RATE_30D": "30-day reorder rate",
                "MISSING_RFM_MATCH": "No RFM match",
            }
        ),
        column_config={
            "Avg orders": st.column_config.NumberColumn(format="%.1f"),
            "Avg % discounted": st.column_config.NumberColumn(format="percent"),
            "Avg value (CAD)": st.column_config.NumberColumn(format="$%.2f"),
            "30-day reorder rate": st.column_config.NumberColumn(format="percent"),
        },
        hide_index=True,
        width="stretch",
        height=200,
    )
    viz_note(
        "🔬 Observational and mechanically confounded. At the platform's discount rate, a "
        "high-order-count customer essentially cannot be 'Full-Price'. Customers with no RFM "
        "match are counted here but excluded from the value average.",
        null_result=True,
    )

except Exception as e:
    st.error(f"Error loading Retention & Activation: {e}")
    st.info("Check your Snowflake connection and ensure all MART tables exist.")
