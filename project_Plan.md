# Zomato dbt Project — Plan

Last verified against disk: 2026-08-19. This reflects what's actually in `zomato/` right now, not what was discussed earlier in the build — the project was reset/cleaned since then.

## Current state (verified on disk)

**Working:**
- Not a git repo yet (`/Users/kanwarraj/Documents/Zomata_Data_Engineering` has no `.git`)
- `zomato/dbt_project.yml` — name/profile set to `zomato`, connects to Snowflake, `dbt debug` passes
- `zomato/models/staging/_sources.yml` — declares source `raw` (database `ZOMATO`, schema `RAW`), 7 tables: `restaurants`, `users`, `food`, `menu`, `orders`, `order_items`, `reviews` (lowercase, no descriptions beyond a generic one-liner each)
- `zomato/packages.yml` — `dbt-labs/dbt_utils >=1.3.0` already declared
- `zomato_er_diagram.png` (repo root) — real, accurate schema with every column, PK/FK, and cardinality for all 7 tables. This is the source of truth for column names below.

**Not yet built:**
- Zero staging models (`models/staging/` has only `_sources.yml`, no `.sql` files)
- Zero macros (`macros/` is empty)
- Zero marts/gold models (`models/marts/` is empty)
- Zero tests (no `tests/` directory)
- No CI/CD, no GitHub repo
- `README.md` is still the default Jaffle Shop boilerplate

**Known issues to fix, not just build around:**
- `dbt_project.yml` has a leftover `seeds: jaffle_shop:` block — dead config, no seeds are used, remove it
- `dbt_project.yml` marts config has a typo: `+ schema: staging` (space after `+`, and it points marts at the `staging` schema instead of its own) — fix both
- `dbt_project.yml` declares a `snapshot:` materialization config but no `snapshot-paths` and no `snapshots/` folder exists — either wire it up when you actually add a snapshot, or remove it for now to avoid dead config

## Real schema reference (from `zomato_er_diagram.png`)

| Table | Key columns | Notes |
|---|---|---|
| `RESTAURANTS` | `id` (PK) | name, city, rating, rating_count, cost, cuisine, lic_no, link, address, menu |
| `USERS` | `user_id` (PK) | name, email, password, age, gender, marital_status, occupation, monthly_income, education, family_size |
| `FOOD` | `f_id` (PK) | item, veg_or_non_veg |
| `MENU` | `menu_id` (PK), `r_id`/`f_id` (FK) | cuisine, price |
| `ORDERS` | `order_id` (PK), `user_id`/`r_id` (FK) | order_timestamp, order_date, restaurant_city, cuisine, items_count, sales_qty, **subtotal, discount, delivery_fee, gst, sales_amount**, currency, payment_method, order_status, customer_rating, delivery_time_min |
| `ORDER_ITEMS` | `order_item_id` (PK), `order_id`/`r_id`/`f_id` (FK) | price, quantity, line_amount |
| `REVIEWS` | `review_id` (PK), `order_id`/`user_id`/`restaurant_id` (FK) | rating (1–5), comment, review_date |

The bold `ORDERS` columns matter most — they're what the reconciliation macro (Phase 3) validates: `sales_amount == subtotal - discount + delivery_fee + gst`.

## Phase 1 — Fix the foundation (do this first, ~15 min)

1. Remove the dead `seeds: jaffle_shop:` block from `dbt_project.yml`
2. Fix the marts materialization config: `+schema: marts` (own schema, not `staging`; no stray space)
3. Either remove the unused `snapshot:` block or leave a `# TODO` if you plan to snapshot something (e.g. `RESTAURANTS.rating` over time) later
4. Rewrite `README.md` to describe the actual project, not Jaffle Shop
5. `git init`, first commit, push to a new GitHub repo — everything from Phase 5 (CI/CD) depends on this existing

## Phase 2 — Staging layer (Bronze → Silver)

Build one `stg_<table>.sql` per source table, in `models/staging/`:
- `stg_restaurants.sql`, `stg_users.sql`, `stg_food.sql`, `stg_menu.sql`, `stg_orders.sql`, `stg_order_items.sql`, `stg_reviews.sql`

Each: `select * from {{ source('raw', '<table>') }}`, rename/cast columns to consistent snake_case, no business logic yet — that belongs in marts or macros, not staging.

Add a `models/staging/staging.yml` (or per-model `.yml`) with column-level docs and baseline tests using real columns:
- `not_null` + `unique` on every PK (`id`, `user_id`, `f_id`, `menu_id`, `order_id`, `order_item_id`, `review_id`)
- `relationships` tests on every FK (e.g. `ORDER_ITEMS.order_id` → `ORDERS.order_id`, `ORDERS.r_id` → `RESTAURANTS.id`, `REVIEWS.order_id` → `ORDERS.order_id`)
- `accepted_values` on `order_status` and `veg_or_non_veg` (confirm the actual value sets from Snowflake first — don't guess)
- `dbt_utils.accepted_range` on `REVIEWS.rating` (1–5) and on `ORDERS.delivery_time_min` (>0)

## Phase 3 — The macro (this is the centerpiece for the post)

Build a **custom generic test macro** in `macros/tests/test_order_total_reconciles.sql`:

```sql
{% test order_total_reconciles(model) %}
select order_id
from {{ model }}
where sales_amount != (subtotal - discount + delivery_fee + gst)
{% endtest %}
```

Apply it to `stg_orders.sales_amount` (or wherever `sales_amount` lives after staging) in the model's schema `.yml`. Run it against real data — if it fails on real rows, that's not a bug in the macro, that's a genuine data quality finding worth a line in the post ("X% of orders don't reconcile — here's why").

Also add source freshness to `_sources.yml` once you confirm which column represents load time (`order_timestamp` is the candidate on `orders`):
```yaml
tables:
  - name: orders
    loaded_at_field: order_timestamp
    freshness:
      warn_after: {count: 24, period: hour}
      error_after: {count: 48, period: hour}
```

## Phase 4 — Marts / Gold layer (the insights)

Build in `models/marts/`, one model per business question:
- `revenue_by_restaurant.sql` — revenue and order count by restaurant and city
- `customer_retention.sql` — repeat-order rate / RFM-style segmentation by `user_id`
- `rating_vs_volume.sql` — join `RESTAURANTS.rating` against order volume per restaurant; this is the model that produces the finding the LinkedIn draft leans on, so run it for real and see what the actual number says before writing the post around it

## Phase 5 — CI/CD

- GitHub Actions workflow (`.github/workflows/dbt-ci.yml`) that runs `dbt build` (or `dbt compile` + `dbt test`) against Snowflake on every PR, using `DBT_SNOWFLAKE_PASSWORD` as a repo secret
- Confirm it actually blocks a PR when a test fails (test this once deliberately — break something on purpose, open a PR, confirm red X)

## Phase 6 — Proof artifacts (needed before the post, not needed for the pipeline to work)

- `dbt docs generate` + `dbt docs serve`, screenshot the real DAG
- Screenshot of a passing (and, once, a failing) GitHub Actions run
- Screenshot of the actual macro file and the actual `schema.yml` test config — not a mockup
- Write down the real numbers from Phase 4's `rating_vs_volume` model — don't reuse the illustrative "they don't always" line unless the real data backs it up

## Sequencing note

Don't reorder Phase 3 before Phase 2, and don't build Phase 6 screenshots before Phases 1–5 are real — every gap in the earlier review ("no real code/screenshots," "diagrams look generic") comes from the carousel being built ahead of the actual implementation. Phase 6 exists specifically to close that gap once, not to be improvised per-post.
