"""Page 2 — Customer Value. Date/City filters are visually disabled on this page (RFM
measures are lifetime values anchored to recency_anchor_date, not a rolling window) —
see spec §5.3. Only the RFM segment multiselect scopes anything here.
"""

import pandas as pd
import streamlit as st

from utils.filters import sql_quote_list
from utils.snowflake_connection import query_snowflake


def _segment_where(segments: list) -> str:
    return f"where segment_label in ({sql_quote_list(segments)})" if segments else ""


@st.cache_data(ttl=3600, show_spinner=False)
def all_segments() -> list:
    df = query_snowflake("select distinct segment_label from ZOMATO.MARTS.MART_CUSTOMER_RFM")
    return sorted(df["SEGMENT_LABEL"].tolist())


@st.cache_data(ttl=3600, show_spinner=False)
def platform_kpis() -> dict:
    row = query_snowflake(
        """
        select
            count(*) as customers_scored,
            sum(monetary_value_cad) as value_covered,
            median(frequency_orders) as median_orders,
            avg(frequency_orders) as mean_orders,
            max(frequency_orders) as max_orders,
            median(monetary_value_cad) as median_value,
            percentile_cont(0.95) within group (order by monetary_value_cad) as p95_value
        from ZOMATO.MARTS.MART_CUSTOMER_RFM
        """
    ).iloc[0]
    top_segment = query_snowflake(
        """
        select segment_label,
            sum(monetary_value_cad) / (select sum(monetary_value_cad) from ZOMATO.MARTS.MART_CUSTOMER_RFM) as value_share,
            count(*)::float / (select count(*) from ZOMATO.MARTS.MART_CUSTOMER_RFM) as customer_share
        from ZOMATO.MARTS.MART_CUSTOMER_RFM
        group by segment_label
        order by value_share desc
        limit 1
        """
    ).iloc[0]

    total_ordering_customers = query_snowflake(
        "select count(distinct customer_id) as n from ZOMATO.MARTS.FCT_ORDER_SALES where is_delivered = true"
    ).iloc[0]["N"]
    platform_gmv = query_snowflake(
        "select sum(gmv_cad) as gmv from ZOMATO.MARTS.MART_EXECUTIVE_SUMMARY"
    ).iloc[0]["GMV"]

    return {
        "customers_scored": int(row["CUSTOMERS_SCORED"]),
        "value_covered": row["VALUE_COVERED"],
        "median_orders": row["MEDIAN_ORDERS"],
        "mean_orders": row["MEAN_ORDERS"],
        "max_orders": int(row["MAX_ORDERS"]),
        "median_value": row["MEDIAN_VALUE"],
        "p95_value": row["P95_VALUE"],
        "top_segment_name": top_segment["SEGMENT_LABEL"],
        "top_segment_value_share": top_segment["VALUE_SHARE"],
        "top_segment_customer_share": top_segment["CUSTOMER_SHARE"],
        "customers_scored_pct": row["CUSTOMERS_SCORED"] / total_ordering_customers,
        "total_ordering_customers": int(total_ordering_customers),
        "value_covered_pct": row["VALUE_COVERED"] / platform_gmv,
        "platform_gmv": platform_gmv,
    }


@st.cache_data(ttl=3600, show_spinner=False)
def concentration_by_segment(segments: list) -> pd.DataFrame:
    where = _segment_where(segments)
    return query_snowflake(
        f"""
        select
            segment_label,
            count(*)::float / (select count(*) from ZOMATO.MARTS.MART_CUSTOMER_RFM) as customer_share,
            sum(monetary_value_cad) / (select sum(monetary_value_cad) from ZOMATO.MARTS.MART_CUSTOMER_RFM) as value_share
        from ZOMATO.MARTS.MART_CUSTOMER_RFM
        {where}
        group by segment_label
        """
    )


@st.cache_data(ttl=3600, show_spinner=False)
def recency_frequency_density(segments: list) -> pd.DataFrame:
    where = _segment_where(segments)
    return query_snowflake(
        f"""
        select
            width_bucket(recency_days, 0, 120, 24) as recency_bin,
            width_bucket(frequency_orders, 0, 300, 20) as freq_bin,
            (width_bucket(recency_days, 0, 120, 24) - 1) * 5 || '-' ||
                (width_bucket(recency_days, 0, 120, 24)) * 5 as recency_bin_label,
            (width_bucket(frequency_orders, 0, 300, 20) - 1) * 15 || '-' ||
                (width_bucket(frequency_orders, 0, 300, 20)) * 15 as freq_bin_label,
            count(*) as customers
        from ZOMATO.MARTS.MART_CUSTOMER_RFM
        {where}
        group by 1, 2, 3, 4
        """
    )


@st.cache_data(ttl=3600, show_spinner=False)
def value_by_decile() -> pd.DataFrame:
    return query_snowflake(
        """
        with deciled as (
            select monetary_value_cad,
                ntile(10) over (order by monetary_value_cad desc) as decile
            from ZOMATO.MARTS.MART_CUSTOMER_RFM
        )
        select
            decile,
            sum(monetary_value_cad) / (select sum(monetary_value_cad) from ZOMATO.MARTS.MART_CUSTOMER_RFM) as value_share,
            count(*) as customers
        from deciled
        group by decile
        order by decile
        """
    )


@st.cache_data(ttl=3600, show_spinner=False)
def segment_matrix(segments: list) -> pd.DataFrame:
    where = _segment_where(segments)
    return query_snowflake(
        f"""
        select
            segment_label,
            count(*) as customers,
            count(*)::float / (select count(*) from ZOMATO.MARTS.MART_CUSTOMER_RFM) as pct_customers,
            sum(monetary_value_cad) as value_cad,
            sum(monetary_value_cad) / (select sum(monetary_value_cad) from ZOMATO.MARTS.MART_CUSTOMER_RFM) as pct_value,
            avg(frequency_orders) as mean_orders,
            sum(monetary_value_cad) / sum(frequency_orders) as aov_cad,
            avg(recency_days) as mean_recency_days
        from ZOMATO.MARTS.MART_CUSTOMER_RFM
        {where}
        group by segment_label
        order by value_cad desc
        """
    )


@st.cache_data(ttl=3600, show_spinner=False)
def demographics() -> dict:
    age = query_snowflake(
        """
        select width_bucket(age, 18, 78, 20) as bucket, min(age) as bucket_min, max(age) as bucket_max, count(*) as customers
        from ZOMATO.MARTS.DIM_CUSTOMER
        group by 1
        order by 1
        """
    )
    income = query_snowflake(
        """
        select monthly_income, count(*) as customers
        from ZOMATO.MARTS.DIM_CUSTOMER
        group by monthly_income
        order by monthly_income
        """
    )
    corr = query_snowflake(
        """
        select
            corr(d.age, r.monetary_value_cad) as corr_age_value,
            corr(d.monthly_income_midpoint_cad, r.monetary_value_cad) as corr_income_value,
            corr(d.family_size, r.monetary_value_cad) as corr_family_value
        from ZOMATO.MARTS.DIM_CUSTOMER d
        join ZOMATO.MARTS.MART_CUSTOMER_RFM r on d.customer_id = r.customer_id
        """
    ).iloc[0]
    return {"age": age, "income": income, "corr": corr}
