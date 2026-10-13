import plotly.graph_objects as go
import streamlit as st

from queries import customers as q
from utils.charts import concentration_hero_figure, rf_density_figure, value_decile_figure
from utils.style import inject_style, page_header, context_chips, section_heading, viz_heading, viz_note
from utils.theme import SERIES_1, base_layout

inject_style()

page_header(
    "Customer Value",
    "Where value concentrates across scored customers, and what drives it.",
)

st.sidebar.markdown("### Page filters")
st.sidebar.info(
    "Date and City filters do not apply here — RFM measures are lifetime values anchored to a "
    "fixed recency date and do not recompute per window."
)

try:
    kpis = q.platform_kpis()
    segments = q.all_segments()
    selected_segments = st.sidebar.multiselect(
        "RFM segment", options=segments, default=segments, key="cv_segments"
    )

    context_chips(
        f"Scored: {kpis['customers_scored']:,} of {kpis['total_ordering_customers']:,} customers "
        f"({kpis['customers_scored_pct']*100:.1f}%) · Recency anchored 2026-06-30 · "
        f"Segments: {'All' if len(selected_segments) == len(segments) else f'{len(selected_segments)} selected'}"
    )

    k1, k2, k3, k4, k5 = st.columns(5)
    with k1:
        st.metric("Customers Scored", f"{kpis['customers_scored']:,}", f"{kpis['customers_scored_pct']*100:.1f}% of {kpis['total_ordering_customers']:,}")
    with k2:
        st.metric("Customer Value Covered", f"${kpis['value_covered']/1e6:,.1f}M", f"{kpis['value_covered_pct']*100:.1f}% of platform GMV")
    with k3:
        st.metric("Median Orders / Customer", f"{kpis['median_orders']:,.0f}", f"mean {kpis['mean_orders']:,.0f} — skewed; max {kpis['max_orders']:,}")
    with k4:
        st.metric("Median Customer Value", f"${kpis['median_value']:,.0f}", f"95th pct ${kpis['p95_value']:,.0f}")
    with k5:
        st.metric(
            "Value in Top Segment",
            f"{kpis['top_segment_value_share']*100:.1f}%",
            f"{kpis['top_segment_name']} — {kpis['top_segment_customer_share']*100:.1f}% of customers",
        )

    # -- V2.1 HERO — Value concentration by segment ------------------------------------
    viz_heading(
        "Value concentration by segment",
        "Each segment's share of customers next to its share of lifetime value.",
    )
    conc_df = q.concentration_by_segment(selected_segments)
    st.plotly_chart(concentration_hero_figure(conc_df), width="stretch")
    viz_note("Percentages are of all scored customers even when segments are filtered out, so shares stay comparable.")

    # -- How value is distributed --------------------------------------------------------
    section_heading("How value is distributed")
    c1, c2 = st.columns(2)
    with c1:
        viz_heading(
            "Recency × Frequency density",
            "Customer count per recency/frequency cell — the informative RFM plane (frequency "
            "and monetary value are nearly collinear here, so that pairing isn't).",
        )
        st.plotly_chart(rf_density_figure(q.recency_frequency_density(selected_segments)), width="stretch")
        viz_note("Recency is measured against the dataset's own last order date, not today.")
    with c2:
        viz_heading(
            "Value by customer decile",
            "Customers ranked by lifetime value and split into ten equal groups.",
        )
        st.plotly_chart(value_decile_figure(q.value_by_decile()), width="stretch")
        viz_note("🧮 Derived in-query; independent of the RFM segment definitions.")

    # -- Segment detail --------------------------------------------------------------------
    section_heading("Segment detail")
    viz_heading(
        "RFM segment detail",
        "One row per segment with the numbers a CRM team would act on. AOV is flat across every "
        "segment — value differences come from order frequency, not basket size.",
    )
    seg_df = q.segment_matrix(selected_segments)
    st.dataframe(
        seg_df.rename(
            columns={
                "SEGMENT_LABEL": "Segment",
                "CUSTOMERS": "Customers",
                "PCT_CUSTOMERS": "% customers",
                "VALUE_CAD": "Value (CAD)",
                "PCT_VALUE": "% value",
                "MEAN_ORDERS": "Mean orders",
                "AOV_CAD": "AOV (CAD)",
                "MEAN_RECENCY_DAYS": "Mean recency (days)",
            }
        ),
        column_config={
            "% customers": st.column_config.NumberColumn(format="percent"),
            "% value": st.column_config.ProgressColumn("% value", format="%.1f%%", min_value=0, max_value=100),
            "Value (CAD)": st.column_config.NumberColumn(format="$%.0f"),
            "AOV (CAD)": st.column_config.NumberColumn(format="$%.2f"),
            "Mean orders": st.column_config.NumberColumn(format="%.1f"),
            "Mean recency (days)": st.column_config.NumberColumn(format="%.0f"),
        },
        hide_index=True,
        width="stretch",
        height=360,
    )
    viz_note(
        "AOV range across segments is narrow — a few percent spread. Frequency and monetary value "
        "are highly correlated in this dataset, so the M in RFM adds little beyond F.",
        null_result=True,
    )

    with st.expander("Customer demographics — descriptive only, not associated with value"):
        demo = q.demographics()
        d1, d2 = st.columns(2)
        with d1:
            age_fig = go.Figure(
                go.Bar(x=demo["age"]["BUCKET_MIN"], y=demo["age"]["CUSTOMERS"], marker=dict(color=SERIES_1))
            )
            age_fig.update_layout(**base_layout(300))
            age_fig.update_xaxes(title_text="Age")
            age_fig.update_yaxes(title_text="Customers")
            st.plotly_chart(age_fig, width="stretch")
        with d2:
            income_fig = go.Figure(
                go.Bar(x=demo["income"]["MONTHLY_INCOME"], y=demo["income"]["CUSTOMERS"], marker=dict(color=SERIES_1))
            )
            income_fig.update_layout(**base_layout(300))
            income_fig.update_xaxes(title_text="Monthly income band")
            income_fig.update_yaxes(title_text="Customers")
            st.plotly_chart(income_fig, width="stretch")

        corr = demo["corr"]
        st.caption(
            f"Demographics show no association with customer value in this dataset: "
            f"corr(age, value) = {corr['CORR_AGE_VALUE']:.3f}, "
            f"corr(income, value) = {corr['CORR_INCOME_VALUE']:.3f}, "
            f"corr(family size, value) = {corr['CORR_FAMILY_VALUE']:.3f}. "
            f"These charts describe who the customers are; they do not explain value."
        )

except Exception as e:
    st.error(f"Error loading Customer Value: {e}")
    st.info("Check your Snowflake connection and ensure MART_CUSTOMER_RFM and DIM_CUSTOMER exist.")
