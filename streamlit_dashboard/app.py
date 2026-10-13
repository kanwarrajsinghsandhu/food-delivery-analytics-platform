import streamlit as st

from queries import marketplace as q_marketplace
from utils.filters import render_global_filters

st.set_page_config(
    page_title="Zomato Analytics",
    page_icon="🍽️",
    layout="wide",
    initial_sidebar_state="expanded",
)

nav = st.navigation(
    {
        "Overview": [st.Page("views/marketplace_health.py", title="Marketplace Health", icon=":material/insights:")],
        "Customers": [st.Page("views/customer_value.py", title="Customer Value", icon=":material/group:")],
        "Retention": [st.Page("views/retention.py", title="Retention & Activation", icon=":material/replay:")],
        "Reference": [st.Page("views/method.py", title="Method & Data Quality", icon=":material/rule:")],
    }
)

try:
    top_cities = q_marketplace.top_cities()
    top_cuisines = q_marketplace.top_cuisine_tags()
except Exception:
    top_cities, top_cuisines = [], []

render_global_filters(top_cities, top_cuisines)

nav.run()
