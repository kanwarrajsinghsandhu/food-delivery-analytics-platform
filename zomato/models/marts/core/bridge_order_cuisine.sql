-- models/marts/core/bridge_order_cuisine.sql
-- Purpose: Gold bridge -- splits fct_order_sales.cuisine (a comma-separated multi-tag string, e.g.
--   "North Indian, Chinese") into one row per tag, so the BI layer can filter orders by a single cuisine
--   without string matching. Same split logic the Streamlit dashboard applies at query time.
-- Grain: order_id x cuisine_tag
-- FK: order_id -> fct_order_sales
-- Caveat: an order with N tags appears N times. Order measures summed through this table without a
--   distinct on order_id will be inflated -- in Power BI, filter fct_order_sales *through* this bridge,
--   don't aggregate from it. Lifecycle marts (customer-month status, growth accounting) are deliberately
--   not cuisine-filterable: a customer's new/retained/resurrected status is platform-level, not per-cuisine.

{{ config(schema='MARTS') }}

with orders as (
    select order_id, cuisine
    from {{ ref('fct_order_sales') }}
    where cuisine is not null
)

select distinct
    o.order_id,
    trim(t.value::string) as cuisine_tag
from orders o,
    lateral split_to_table(o.cuisine, ',') t
where trim(t.value::string) != ''
