"""Page 3 — Retention & Activation. Every rate here is a ratio of aggregates, never
AVG(rate) — see spec §2.1/F1. City/cuisine filters do not apply (spec §5.3): cohort
membership is defined by a customer's *first* order, so filtering orders by city would
retroactively redefine cohort membership and silently change cohort sizes.
"""

import pandas as pd
import streamlit as st

from utils.snowflake_connection import query_snowflake


@st.cache_data(ttl=3600, show_spinner=False)
def activation_kpis() -> dict:
    row = query_snowflake(
        """
        select
            count(*) as first_time_customers,
            count_if(days_to_second_order <= 7)::float / count(*) as pct_7d,
            count_if(days_to_second_order <= 14)::float / count(*) as pct_14d,
            count_if(days_to_second_order <= 30)::float / count(*) as pct_30d,
            count_if(days_to_second_order is not null)::float / count(*) as pct_ever,
            median(days_to_second_order) as median_days_to_2nd
        from ZOMATO.MARTS.MART_RETENTION_DIAGNOSTIC
        """
    ).iloc[0]
    return {
        "first_time_customers": int(row["FIRST_TIME_CUSTOMERS"]),
        "pct_7d": row["PCT_7D"],
        "pct_14d": row["PCT_14D"],
        "pct_30d": row["PCT_30D"],
        "pct_ever": row["PCT_EVER"],
        "median_days_to_2nd": row["MEDIAN_DAYS_TO_2ND"],
    }


@st.cache_data(ttl=3600, show_spinner=False)
def cohort_sizes() -> pd.DataFrame:
    return query_snowflake(
        """
        select distinct acquisition_cohort_month, cohort_size
        from ZOMATO.MARTS.MART_COHORT_RETENTION
        order by acquisition_cohort_month desc
        """
    )


@st.cache_data(ttl=3600, show_spinner=False)
def cohort_retention_raw() -> pd.DataFrame:
    return query_snowflake(
        """
        select acquisition_cohort_month, period_number, cohort_size, active_customers, retention_rate
        from ZOMATO.MARTS.MART_COHORT_RETENTION
        order by acquisition_cohort_month, period_number
        """
    )


@st.cache_data(ttl=3600, show_spinner=False)
def platform_weighted_retention(min_cohort_size: int) -> pd.DataFrame:
    return query_snowflake(
        f"""
        select
            period_number,
            sum(active_customers)::float / sum(cohort_size) as retention_rate
        from ZOMATO.MARTS.MART_COHORT_RETENTION
        where cohort_size >= {min_cohort_size}
        group by period_number
        order by period_number
        """
    )


@st.cache_data(ttl=3600, show_spinner=False)
def selected_cohort_curve(cohort_month: str) -> pd.DataFrame:
    return query_snowflake(
        f"""
        select period_number, retention_rate
        from ZOMATO.MARTS.MART_COHORT_RETENTION
        where acquisition_cohort_month = '{cohort_month}'
        order by period_number
        """
    )


@st.cache_data(ttl=3600, show_spinner=False)
def activation_windows() -> pd.DataFrame:
    row = query_snowflake(
        """
        select
            count(*) as n,
            count_if(days_to_second_order <= 7)::float / count(*) as pct_7d,
            count_if(days_to_second_order <= 14)::float / count(*) as pct_14d,
            count_if(days_to_second_order <= 30)::float / count(*) as pct_30d,
            count_if(days_to_second_order is not null)::float / count(*) as pct_ever
        from ZOMATO.MARTS.MART_RETENTION_DIAGNOSTIC
        """
    ).iloc[0]
    return pd.DataFrame(
        {
            "WINDOW": ["≤7 days", "≤14 days", "≤30 days", "Ever"],
            "PCT": [row["PCT_7D"], row["PCT_14D"], row["PCT_30D"], row["PCT_EVER"]],
        }
    )


@st.cache_data(ttl=3600, show_spinner=False)
def delivery_speed_reorder() -> pd.DataFrame:
    return query_snowflake(
        """
        select
            delivery_speed_bucket,
            count(*) as customers,
            count_if(did_reorder_within_30d)::float / count(*) as reorder_rate_30d,
            min(first_order_delivery_time) as sort_key
        from ZOMATO.MARTS.MART_RETENTION_DIAGNOSTIC
        group by delivery_speed_bucket
        order by sort_key
        """
    )


@st.cache_data(ttl=3600, show_spinner=False)
def rating_reorder() -> pd.DataFrame:
    """Re-buckets from the raw integer rating by star count instead of using the mart's
    decimal-range rating_bucket column (ratings are whole stars, so 4.5+ is just 5 stars).

    Groups by the bucket label only (not the raw rating) so 1-star and 2-star first
    orders — both '1-2 stars' — collapse into a single row instead of staying split.
    """
    return query_snowflake(
        """
        with bucketed as (
            select
                case
                    when first_order_rating is null then 'Unrated'
                    when first_order_rating = 5 then '5 stars'
                    when first_order_rating = 4 then '4 stars'
                    when first_order_rating = 3 then '3 stars'
                    else '1-2 stars'
                end as rating_bucket,
                did_reorder_within_30d
            from ZOMATO.MARTS.MART_RETENTION_DIAGNOSTIC
        )
        select
            rating_bucket,
            count(*) as customers,
            count_if(did_reorder_within_30d)::float / count(*) as reorder_rate_30d,
            case rating_bucket
                when '5 stars' then 5
                when '4 stars' then 4
                when '3 stars' then 3
                when '1-2 stars' then 2
                else -1
            end as sort_key
        from bucketed
        group by rating_bucket
        order by sort_key desc
        """
    )


@st.cache_data(ttl=3600, show_spinner=False)
def discount_reorder() -> pd.DataFrame:
    return query_snowflake(
        """
        select
            iff(did_use_discount_on_first_order, 'Used discount', 'No discount') as discount_bucket,
            count(*) as customers,
            count_if(did_reorder_within_30d)::float / count(*) as reorder_rate_30d
        from ZOMATO.MARTS.MART_RETENTION_DIAGNOSTIC
        group by 1
        order by 1
        """
    )


@st.cache_data(ttl=3600, show_spinner=False)
def pooled_reorder_rate() -> float:
    row = query_snowflake(
        "select count_if(did_reorder_within_30d)::float / count(*) as rate from ZOMATO.MARTS.MART_RETENTION_DIAGNOSTIC"
    ).iloc[0]
    return row["RATE"]


@st.cache_data(ttl=3600, show_spinner=False)
def discount_dependency() -> pd.DataFrame:
    return query_snowflake(
        """
        select
            discount_dependency_segment,
            count(*) as customers,
            avg(total_orders) as avg_total_orders,
            avg(pct_orders_discounted) as avg_pct_discounted,
            avg(monetary_value_cad) as avg_value_cad,
            avg(iff(did_reorder_within_30d, 1.0, 0.0)) as reorder_rate_30d,
            count_if(monetary_value_cad is null) as missing_rfm_match
        from ZOMATO.MARTS.MART_BASKET_DISCOUNT
        group by discount_dependency_segment
        order by customers desc
        """
    )
