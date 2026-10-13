"""Page 1 — Marketplace Health. All aggregation happens in SQL (spec §2.7/§14.3);
only presentation-grain rows cross the wire.
"""

import datetime as dt

import pandas as pd
import streamlit as st

from utils.filters import sql_quote_list
from utils.snowflake_connection import query_snowflake

_ORDER_DATE_WHERE = "order_date between '{start}' and '{end}'"


def _where(filters: dict, table_alias: str = "") -> str:
    p = f"{table_alias}." if table_alias else ""
    clauses = [_ORDER_DATE_WHERE.format(start=filters["date_start"], end=filters["date_end"]).replace(
        "order_date", f"{p}order_date"
    )]
    if filters["cities"]:
        clauses.append(f"{p}city in ({sql_quote_list(filters['cities'])})")
    if filters["outcome"] == "Delivered":
        clauses.append(f"{p}is_delivered = true")
    return " and ".join(clauses)


def _cuisine_where(filters: dict) -> str:
    """Cuisine filter operates on the split tag, applied after LATERAL SPLIT_TO_TABLE."""
    if not filters["cuisines"]:
        return ""
    return f" and trim(t.value::string) in ({sql_quote_list(filters['cuisines'])})"


@st.cache_data(ttl=3600, show_spinner=False)
def top_cities(n: int = 20) -> list:
    df = query_snowflake(
        f"""
        select city, count(*) as orders
        from ZOMATO.MARTS.FCT_ORDER_SALES
        group by city
        order by orders desc
        limit {n}
        """
    )
    return df["CITY"].tolist()


@st.cache_data(ttl=3600, show_spinner=False)
def top_cuisine_tags(n: int = 30) -> list:
    df = query_snowflake(
        f"""
        select trim(t.value::string) as cuisine_tag, count(*) as orders
        from ZOMATO.MARTS.FCT_ORDER_SALES f, lateral split_to_table(f.cuisine, ',') t
        group by 1
        order by orders desc
        limit {n}
        """
    )
    return df["CUISINE_TAG"].tolist()


@st.cache_data(ttl=3600, show_spinner=False)
def platform_kpis(filters: dict) -> dict:
    """Trailing-6-months-vs-prior-6-months deltas, computed on the unfiltered dataset
    timeline (fixed comparison windows, per spec K1.1-K1.5), plus the filtered-scope
    headline aggregates themselves.

    GMV/AOV source from MART_EXECUTIVE_SUMMARY whenever no city/cuisine filter is active
    (spec §11.1: the mart is the single source of truth for GMV — computing it directly
    from FCT_ORDER_SALES instead gives a figure ~0.035% off due to rounding order). City/
    cuisine filtering needs order-grain, so it falls back to FCT_ORDER_SALES only then.
    """
    no_city_cuisine_filter = not filters["cities"] and not filters["cuisines"]

    if no_city_cuisine_filter:
        headline = query_snowflake(
            f"""
            select
                sum(gmv_cad) as gmv_cad,
                sum(delivered_orders) as delivered_orders,
                sum(total_orders) as total_orders,
                sum(cancelled_orders + refunded_orders) as failed_orders,
                sum(gmv_cad) / nullif(sum(delivered_orders), 0) as aov_cad
            from ZOMATO.MARTS.MART_EXECUTIVE_SUMMARY
            where order_date between '{filters['date_start']}' and '{filters['date_end']}'
            """
        ).iloc[0]
        orders_in_scope = headline["DELIVERED_ORDERS"] if filters["outcome"] == "Delivered" else headline["TOTAL_ORDERS"]
    else:
        where = _where(filters)
        headline = query_snowflake(
            f"""
            select
                sum(iff(is_delivered, sales_amount_cad, 0)) as gmv_cad,
                count_if(is_delivered) as delivered_orders,
                count(*) as total_orders,
                count_if(is_cancelled or is_refunded) as failed_orders,
                sum(iff(is_delivered, sales_amount_cad, 0)) / nullif(count_if(is_delivered), 0) as aov_cad
            from ZOMATO.MARTS.FCT_ORDER_SALES
            where {where}
            """
        ).iloc[0]
        orders_in_scope = headline["DELIVERED_ORDERS"] if filters["outcome"] == "Delivered" else headline["TOTAL_ORDERS"]

    bounds = query_snowflake("select max(order_date) as max_date from ZOMATO.MARTS.MART_EXECUTIVE_SUMMARY").iloc[0]
    max_date = bounds["MAX_DATE"]
    cur_start = (max_date.replace(day=1) - dt.timedelta(days=1)).replace(day=1)
    for _ in range(4):
        cur_start = (cur_start - dt.timedelta(days=1)).replace(day=1)
    prior_end = cur_start - dt.timedelta(days=1)
    prior_start = prior_end.replace(day=1)
    for _ in range(5):
        prior_start = (prior_start - dt.timedelta(days=1)).replace(day=1)

    windows = query_snowflake(
        f"""
        select
            sum(iff(order_date >= '{cur_start}', gmv_cad, 0)) as gmv_current,
            sum(iff(order_date < '{cur_start}' and order_date >= '{prior_start}', gmv_cad, 0)) as gmv_prior,
            sum(iff(order_date >= '{cur_start}', delivered_orders, 0)) as delivered_current,
            sum(iff(order_date < '{cur_start}' and order_date >= '{prior_start}', delivered_orders, 0)) as delivered_prior,
            sum(iff(order_date >= '{cur_start}', cancelled_orders + refunded_orders, 0))
                / nullif(sum(iff(order_date >= '{cur_start}', total_orders, 0)), 0) as failure_rate_current,
            sum(iff(order_date < '{cur_start}' and order_date >= '{prior_start}', cancelled_orders + refunded_orders, 0))
                / nullif(sum(iff(order_date < '{cur_start}' and order_date >= '{prior_start}', total_orders, 0)), 0) as failure_rate_prior,
            avg(iff(order_date >= '{cur_start}', aov_cad, null)) as aov_current,
            avg(iff(order_date < '{cur_start}' and order_date >= '{prior_start}', aov_cad, null)) as aov_prior
        from ZOMATO.MARTS.MART_EXECUTIVE_SUMMARY
        """
    ).iloc[0]

    mau = query_snowflake(
        """
        select date_trunc('month', order_date) as month, max(monthly_active_users) as mau
        from ZOMATO.MARTS.MART_EXECUTIVE_SUMMARY
        group by 1 order by 1
        """
    )
    latest_mau = mau.iloc[-1]["MAU"]
    mau_6mo_ago = mau.iloc[-7]["MAU"] if len(mau) > 6 else mau.iloc[0]["MAU"]

    def pct_delta(cur, prior):
        return None if not prior else (cur - prior) / prior * 100

    # GMV/AOV are defined on delivered orders only. Outcome="All" re-scopes the orders
    # count but must not silently attach a delivered-only revenue figure to it — spec §5.1.
    delivered_scope = filters["outcome"] == "Delivered"
    return {
        "gmv_cad": (headline["GMV_CAD"] or 0) if delivered_scope else None,
        "delivered_orders": int(orders_in_scope or 0),
        "aov_cad": (headline["AOV_CAD"] or 0) if delivered_scope else None,
        "failure_rate": (headline["FAILED_ORDERS"] or 0) / headline["TOTAL_ORDERS"] if headline["TOTAL_ORDERS"] else 0,
        "mau_latest": int(latest_mau),
        "gmv_delta_pct": pct_delta(windows["GMV_CURRENT"], windows["GMV_PRIOR"]),
        "orders_delta_pct": pct_delta(windows["DELIVERED_CURRENT"], windows["DELIVERED_PRIOR"]),
        "failure_delta_pp": (
            None if windows["FAILURE_RATE_PRIOR"] is None
            else (windows["FAILURE_RATE_CURRENT"] - windows["FAILURE_RATE_PRIOR"]) * 100
        ),
        "aov_delta_pct": pct_delta(windows["AOV_CURRENT"], windows["AOV_PRIOR"]),
        "mau_delta_pct": pct_delta(latest_mau, mau_6mo_ago),
    }


@st.cache_data(ttl=3600, show_spinner=False)
def gmv_orders_monthly(filters: dict) -> pd.DataFrame:
    """V1.1/V1.2 hero. Sources from MART_EXECUTIVE_SUMMARY (spec §11.1 single source of
    truth for GMV) unless a city/cuisine filter forces order-grain aggregation."""
    orders_col = "delivered_orders" if filters["outcome"] == "Delivered" else "total_orders"
    if not filters["cities"] and not filters["cuisines"]:
        return query_snowflake(
            f"""
            select
                date_trunc('month', order_date) as month,
                sum(gmv_cad) as gmv_cad,
                sum({orders_col}) as orders
            from ZOMATO.MARTS.MART_EXECUTIVE_SUMMARY
            where order_date between '{filters['date_start']}' and '{filters['date_end']}'
            group by 1
            order by 1
            """
        )
    where = _where(filters)
    orders_expr = "count_if(is_delivered)" if filters["outcome"] == "Delivered" else "count(*)"
    return query_snowflake(
        f"""
        select
            date_trunc('month', order_date) as month,
            sum(iff(is_delivered, sales_amount_cad, 0)) as gmv_cad,
            {orders_expr} as orders
        from ZOMATO.MARTS.FCT_ORDER_SALES
        where {where}
        group by 1
        order by 1
        """
    )


@st.cache_data(ttl=3600, show_spinner=False)
def mau_monthly(filters: dict) -> pd.DataFrame:
    return query_snowflake(
        f"""
        select date_trunc('month', order_date) as month, max(monthly_active_users) as monthly_active_users
        from ZOMATO.MARTS.MART_EXECUTIVE_SUMMARY
        where order_date between '{filters['date_start']}' and '{filters['date_end']}'
        group by 1
        order by 1
        """
    )


@st.cache_data(ttl=3600, show_spinner=False)
def retention_monthly(filters: dict) -> pd.DataFrame:
    return query_snowflake(
        f"""
        select date_trunc('month', order_date) as month, max(monthly_retention_rate) as monthly_retention_rate
        from ZOMATO.MARTS.MART_EXECUTIVE_SUMMARY
        where order_date between '{filters['date_start']}' and '{filters['date_end']}'
            and monthly_retention_rate is not null
        group by 1
        order by 1
        """
    )


@st.cache_data(ttl=3600, show_spinner=False)
def delivery_time_distribution(filters: dict) -> pd.DataFrame:
    where = _where(filters)
    return query_snowflake(
        f"""
        select delivery_time_min, count(*) as orders
        from ZOMATO.MARTS.FCT_ORDER_SALES
        where {where} and is_delivered = true
        group by 1
        order by 1
        """
    )


@st.cache_data(ttl=3600, show_spinner=False)
def outcome_mix_monthly(filters: dict) -> pd.DataFrame:
    return query_snowflake(
        f"""
        select
            month,
            delivered_orders::float / total_orders as delivered_share,
            cancelled_orders::float / total_orders as cancelled_share,
            refunded_orders::float / total_orders as refunded_share
        from (
            select
                date_trunc('month', order_date) as month,
                sum(total_orders) as total_orders,
                sum(delivered_orders) as delivered_orders,
                sum(cancelled_orders) as cancelled_orders,
                sum(refunded_orders) as refunded_orders
            from ZOMATO.MARTS.MART_EXECUTIVE_SUMMARY
            where order_date between '{filters['date_start']}' and '{filters['date_end']}'
            group by 1
        )
        order by 1
        """
    )


@st.cache_data(ttl=3600, show_spinner=False)
def cuisine_gmv_top(filters: dict, n: int = 12) -> pd.DataFrame:
    where = _where(filters, table_alias="f")
    cuisine_extra = _cuisine_where(filters)
    return query_snowflake(
        f"""
        select trim(t.value::string) as cuisine_tag,
            sum(iff(f.is_delivered, f.sales_amount_cad, 0)) as gmv_cad,
            count(*) as tagged_orders
        from ZOMATO.MARTS.FCT_ORDER_SALES f, lateral split_to_table(f.cuisine, ',') t
        where {where}{cuisine_extra}
        group by 1
        order by gmv_cad desc
        limit {n}
        """
    )


@st.cache_data(ttl=3600, show_spinner=False)
def city_matrix(filters: dict, n: int = 20) -> pd.DataFrame:
    where = _where(filters, table_alias="f")
    return query_snowflake(
        f"""
        select
            city,
            count(*) as orders,
            sum(iff(is_delivered, sales_amount_cad, 0)) as gmv_cad,
            sum(iff(is_delivered, sales_amount_cad, 0)) / nullif(count_if(is_delivered), 0) as aov_cad,
            avg(iff(customer_rating is not null and is_delivered, customer_rating, null)) as avg_rating,
            median(iff(is_delivered, delivery_time_min, null)) as median_delivery_min,
            count_if(is_delivered and is_late_delivery_proxy)::float
                / nullif(count_if(is_delivered), 0) as over_30_share
        from ZOMATO.MARTS.FCT_ORDER_SALES f
        where {where}
        group by city
        order by orders desc
        limit {n}
        """
    ).sort_values("GMV_CAD", ascending=False)


@st.cache_data(ttl=3600, show_spinner=False)
def restaurant_lookup(min_orders: int = 100, limit: int = 200) -> pd.DataFrame:
    return query_snowflake(
        f"""
        select
            r.name as restaurant_name,
            f.city,
            count(*) as orders,
            sum(iff(f.is_delivered, f.sales_amount_cad, 0)) as gmv_cad,
            sum(iff(f.is_delivered, f.sales_amount_cad, 0)) / nullif(count_if(f.is_delivered), 0) as aov_cad,
            avg(iff(f.is_delivered, f.customer_rating, null)) as avg_rating,
            median(iff(f.is_delivered, f.delivery_time_min, null)) as median_delivery_min
        from ZOMATO.MARTS.FCT_ORDER_SALES f
        join ZOMATO.STAGING.STG_RESTAURANTS r on f.restaurant_id = r.id
        group by r.name, f.city
        having count(*) >= {min_orders}
        order by gmv_cad desc
        limit {limit}
        """
    )
