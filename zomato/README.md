# Zomato Data Warehouse — dbt + Snowflake

A data engineering project that builds a medallion-architecture data warehouse on Snowflake using dbt, starting from raw operational data (restaurants, orders, users, reviews) and delivering clean, tested, business-logic-ready tables for analytics.

## Architecture

**Bronze/Raw** — CSV data loaded from Azure Data Lake into `ZOMATO.RAW` via Snowflake `COPY INTO`

**Silver/Staging** — dbt staging models (`stg_*.sql`) that clean, rename, and validate columns; enforce referential integrity and domain constraints via tests

**Gold/Marts** — dbt mart models that answer business questions: revenue by restaurant, customer retention patterns, rating vs. order volume

## Source Tables

- `restaurants` — restaurant metadata (name, city, rating, cuisine)
- `users` — customer profiles (name, email, demographics)
- `food` — food item catalog (item name, veg/non-veg)
- `menu` — restaurant menus (restaurant × food × price)
- `orders` — transactions (order ID, user, restaurant, amounts, status)
- `order_items` — order line items (order × food × quantity × price)
- `reviews` — customer feedback (order × rating × comment)

## Quick Start

1. Verify Snowflake connection: `dbt debug`
2. Run the pipeline: `dbt build` (compiles models, runs tests, materializes tables)
3. Explore docs: `dbt docs generate && dbt docs serve`

## Project Structure

```
models/
  staging/       # Bronze → Silver; 1:1 with source tables, cleaned/tested
  marts/         # Silver → Gold; business logic, aggregations, joins
macros/
  tests/         # Custom generic tests (e.g., reconciliation logic)
```

For details on phases, tests, and macro design, see `project_Plan.md`.