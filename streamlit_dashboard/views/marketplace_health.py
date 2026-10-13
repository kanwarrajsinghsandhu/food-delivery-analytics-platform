import streamlit as st

from queries import marketplace as q
from utils.charts import (
    gmv_hero_figure,
    mau_line_figure,
    retention_line_figure,
    delivery_distribution_figure,
    outcome_mix_figure,
    cuisine_bar_figure,
)
from utils.filters import get_filters, chip_text
from utils.style import inject_style, page_header, context_chips, section_heading, viz_heading, viz_note

inject_style()

page_header(
    "Marketplace Health",
    "Commercial scale, customer activity and fulfilment across 10M orders.",
)

filters = get_filters()
context_chips(chip_text(filters))

try:
    kpis = q.platform_kpis(filters)

    delivered_scope = filters["outcome"] == "Delivered"
    orders_label = "Delivered Orders" if delivered_scope else "Total Orders"

    k1, k2, k3, k4, k5 = st.columns(5)
    with k1:
        st.metric(
            "Gross Merchandise Value (GMV)",
            f"${kpis['gmv_cad']/1e6:,.1f}M" if delivered_scope else "—",
            delta=None if kpis["gmv_delta_pct"] is None or not delivered_scope else f"{kpis['gmv_delta_pct']:+.1f}% vs prior 6 months",
            help=None if delivered_scope else "GMV is defined on delivered orders only. Switch Order outcome to Delivered to see it.",
        )
    with k2:
        st.metric(
            orders_label,
            f"{kpis['delivered_orders']:,}",
            delta=None if kpis["orders_delta_pct"] is None else f"{kpis['orders_delta_pct']:+.1f}% vs prior 6 months",
        )
    with k3:
        st.metric(
            "Average Order Value (AOV)",
            f"${kpis['aov_cad']:,.2f}" if delivered_scope else "—",
            delta=None if kpis["aov_delta_pct"] is None or not delivered_scope else f"flat ({kpis['aov_delta_pct']:+.1f}%)",
            delta_color="off",
            help=None if delivered_scope else "AOV is defined on delivered orders only.",
        )
    with k4:
        st.metric(
            "Monthly Active Customers",
            f"{kpis['mau_latest']:,}",
            delta=None if kpis["mau_delta_pct"] is None else f"{kpis['mau_delta_pct']:+.1f}% vs 6 months ago",
        )
    with k5:
        failure_delta = kpis["failure_delta_pp"]
        st.metric(
            "Order Failure Rate",
            f"{kpis['failure_rate']*100:.2f}%",
            delta=None if failure_delta is None else f"{failure_delta:+.1f}pp vs prior 6 months",
            delta_color="inverse",
        )

    # -- V1.1 + V1.2 — GMV hero + order-volume companion -----------------------------
    monthly = q.gmv_orders_monthly(filters)
    viz_heading(
        "Monthly GMV",
        "Gross merchandise value from delivered orders, by calendar month. The lower panel "
        "shows order volume on the same timeline — the two move together because AOV is flat.",
    )
    st.plotly_chart(gmv_hero_figure(monthly), width="stretch")
    viz_note(
        "Monthly totals are affected by calendar length (a 28-day February is not a downturn)."
    )

    # -- Customer activity ------------------------------------------------------------
    section_heading("Customer activity")
    c1, c2 = st.columns(2)
    with c1:
        viz_heading(
            "Monthly active customers",
            "Distinct customers ordering in each calendar month. Calendar-month active, not a rolling 30-day window.",
        )
        st.plotly_chart(mau_line_figure(q.mau_monthly(filters)), width="stretch")
        viz_note("⚠️ Proxy: calendar-month active, not rolling 30-day.")
    with c2:
        viz_heading(
            "Monthly retention rate",
            "Of customers who ordered last month, the share who ordered again this month.",
        )
        st.plotly_chart(retention_line_figure(q.retention_monthly(filters)), width="stretch")
        viz_note("Jan-2024 has no prior month, so it is excluded rather than shown as 0%.")

    # -- Fulfilment ---------------------------------------------------------------------
    section_heading("Fulfilment")
    viz_heading(
        "Delivery time distribution",
        "All delivered orders by delivery minutes. The 30-minute proxy threshold sits at the "
        "median, so it splits the distribution roughly in half — it is not a service-level measure.",
    )
    st.plotly_chart(delivery_distribution_figure(q.delivery_time_distribution(filters)), width="stretch")
    viz_note(
        "⚠️ Proxy: is_late_delivery_proxy = delivery_time_min > 30. No promised-ETA field exists "
        "in source data, so this is an absolute threshold, not an SLA breach."
    )

    c3, c4 = st.columns(2)
    with c3:
        viz_heading(
            "Order outcome mix over time",
            "Share of orders delivered, cancelled and refunded each month.",
        )
        st.plotly_chart(outcome_mix_figure(q.outcome_mix_monthly(filters)), width="stretch")
    with c4:
        viz_heading(
            "Top cuisine tags by GMV",
            "Restaurants carry multiple tags, so an order tagged 'North Indian, Chinese' counts "
            "under both — shares sum to more than 100%.",
        )
        st.plotly_chart(cuisine_bar_figure(q.cuisine_gmv_top(filters)), width="stretch")
        viz_note("🧮 Derived: tags split from a comma-delimited field. Totals exceed platform GMV by design.")

    # -- Where demand sits ----------------------------------------------------------------
    section_heading("Where demand sits")
    viz_heading(
        "City performance",
        "Top 20 cities by order volume — 70% of all orders. Median delivery time and rating are "
        "shown alongside volume so a large city with weak fulfilment is visible.",
    )
    city_df = q.city_matrix(filters)
    st.dataframe(
        city_df.rename(
            columns={
                "CITY": "City",
                "ORDERS": "Orders",
                "GMV_CAD": "GMV (CAD)",
                "AOV_CAD": "AOV (CAD)",
                "AVG_RATING": "Avg rating",
                "MEDIAN_DELIVERY_MIN": "Median delivery (min)",
                "OVER_30_SHARE": ">30 min share",
            }
        ),
        column_config={
            "GMV (CAD)": st.column_config.ProgressColumn(
                "GMV (CAD)", format="$%.0f", min_value=0, max_value=float(city_df["GMV_CAD"].max())
            ),
            "AOV (CAD)": st.column_config.NumberColumn(format="$%.2f"),
            "Avg rating": st.column_config.NumberColumn(format="%.2f"),
            ">30 min share": st.column_config.NumberColumn(format="percent"),
        },
        hide_index=True,
        width="stretch",
        height=460,
    )
    viz_note("Rating covers rated delivered orders only (unrated orders excluded from the mean).")

    with st.expander("Restaurant lookup (148,541 restaurants — minimum 100 orders)"):
        rest_df = q.restaurant_lookup()
        st.dataframe(
            rest_df.rename(
                columns={
                    "RESTAURANT_NAME": "Restaurant",
                    "CITY": "City",
                    "ORDERS": "Orders",
                    "GMV_CAD": "GMV (CAD)",
                    "AOV_CAD": "AOV (CAD)",
                    "AVG_RATING": "Avg rating",
                    "MEDIAN_DELIVERY_MIN": "Median delivery (min)",
                },
            ),
            hide_index=True,
            width="stretch",
            height=420,
        )
        st.caption(
            "Operational lookup, not a leaderboard. No restaurant exceeds ~0.03% of platform GMV, "
            "and performance metrics are flat across volume tiers, so rank order here is not a "
            "meaningful performance signal."
        )

except Exception as e:
    st.error(f"Error loading Marketplace Health: {e}")
    st.info("Check your Snowflake connection and ensure the required MART tables exist.")
