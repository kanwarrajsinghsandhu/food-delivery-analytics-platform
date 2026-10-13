"""Global sidebar filter bar (spec Part 5) — session_state-backed, shared across pages.

Only four global filters exist, deliberately: date range, city, cuisine tag, order outcome.
Each answers a question a reviewer actually asks. A filter that doesn't apply on a given
page (RFM's lifetime measures, cohort membership) is visually disabled there with an
explanation rather than silently ignored — see DISABLED_FILTER_NOTE below and spec §5.3.
"""

import datetime as dt

import streamlit as st

DATASET_START = dt.date(2024, 1, 1)
DATASET_END = dt.date(2026, 6, 30)

DATE_PRESETS = {
    "Full history": None,
    "Last 12 months": 365,
    "Last 6 months": 182,
    "Last 90 days": 90,
}

_DEFAULTS = {
    "flt_date_preset": "Full history",
    "flt_date_range": (DATASET_START, DATASET_END),
    "flt_cities": [],
    "flt_cuisines": [],
    "flt_outcome": "Delivered",
}


def _init_state() -> None:
    for key, value in _DEFAULTS.items():
        st.session_state.setdefault(key, value)


def _is_off_default() -> bool:
    return any(st.session_state.get(k) != v for k, v in _DEFAULTS.items())


def reset_filters() -> None:
    for key, value in _DEFAULTS.items():
        st.session_state[key] = value


def render_global_filters(top_cities: list, top_cuisines: list) -> None:
    """Sidebar filter bar. Call once, below st.navigation, on every run of app.py."""
    _init_state()

    st.sidebar.markdown("### Filters")

    preset = st.sidebar.selectbox(
        "Date range", list(DATE_PRESETS.keys()), key="flt_date_preset"
    )
    if preset == "Full history":
        st.session_state["flt_date_range"] = (DATASET_START, DATASET_END)
    else:
        days = DATE_PRESETS[preset]
        start = max(DATASET_START, DATASET_END - dt.timedelta(days=days))
        st.session_state["flt_date_range"] = (start, DATASET_END)

    st.sidebar.multiselect(
        "City",
        options=top_cities,
        key="flt_cities",
        help="Top 20 cities by order volume (70% of orders). Empty = all 547 cities.",
    )
    st.sidebar.multiselect(
        "Cuisine tag",
        options=top_cuisines,
        key="flt_cuisines",
        help="Operates on split tags, not raw comma-delimited strings. Empty = all.",
    )
    st.sidebar.segmented_control(
        "Order outcome",
        options=["Delivered", "All"],
        key="flt_outcome",
        help="GMV/AOV are defined on delivered orders. 'All' re-scopes counts; GMV shows '—'.",
    )

    st.sidebar.markdown("&nbsp;", unsafe_allow_html=True)
    if _is_off_default():
        if st.sidebar.button("Reset all filters", use_container_width=True):
            reset_filters()
            st.rerun()


def get_filters() -> dict:
    """Current filter state as a plain dict for query functions to consume."""
    _init_state()
    date_start, date_end = st.session_state["flt_date_range"]
    return {
        "date_start": date_start,
        "date_end": date_end,
        "cities": list(st.session_state["flt_cities"]),
        "cuisines": list(st.session_state["flt_cuisines"]),
        "outcome": st.session_state["flt_outcome"],
    }


def chip_text(filters: dict, extra: str = "") -> str:
    date_start, date_end = filters["date_start"], filters["date_end"]
    period = f"{date_start:%b %Y} – {date_end:%b %Y}"
    city = f"{len(filters['cities'])} selected" if filters["cities"] else "All (552)"
    cuisine = f"{len(filters['cuisines'])} selected" if filters["cuisines"] else "All"
    base = f"Period: {period} · City: {city} · Cuisine: {cuisine} · {filters['outcome']}"
    return f"{base} · {extra}" if extra else base


def disabled_filter_note(text: str) -> None:
    st.sidebar.markdown(f'<div class="disabled-filter-note">ⓘ {text}</div>', unsafe_allow_html=True)


def sql_quote_list(values: list) -> str:
    """Safe SQL IN-list literal for a list of strings (defensive quote-doubling)."""
    escaped = [str(v).replace("'", "''") for v in values]
    return ", ".join(f"'{v}'" for v in escaped)
