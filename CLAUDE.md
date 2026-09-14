# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository scope

The only tracked project is `zomato/`, a dbt project. Everything else at the repo root is gitignored and not part of the codebase proper:
- `zomato_engineering_raw_data/` — raw source CSVs (loaded into Snowflake `ZOMATO.RAW` outside of dbt, e.g. via `Miscelleneaous Items/Upload_To_Blob.py` → Azure Data Lake → Snowflake `COPY INTO`)
- `jaffle_shop/` — the stock dbt-fusion sandbox/tutorial project, unrelated to Zomato
- `Markdowns for Instructions/`, `Miscelleneaous Items/`, `linkedin_carousel/` — personal planning notes and LinkedIn content, not project documentation
- `.venv/` — a Python venv (used for the `Upload_To_Blob.py` script), not for dbt itself

All dbt commands below assume `cd zomato` first.

## Commands

dbt CLI here is **dbt-fusion** (`dbt-fusion 2.0.0-preview.218`, installed globally at `~/.local/bin/dbt`, not from `.venv`), targeting Snowflake via the `zomato` profile in `~/.dbt/profiles.yml` (gitignored).

```bash
cd zomato

dbt debug                  # verify Snowflake connection
dbt build                  # run seeds + models + tests end-to-end (primary command)
dbt run                    # models only, no tests
dbt test                   # tests only
dbt seed                   # load seeds/ (includes the dq_canary_* synthetic data)

# Scope to one model/layer
dbt build --select stg_orders
dbt build --select staging.*
dbt build --select marts.core.*
dbt build --select fct_order_sales+          # model and everything downstream
dbt build --select +fct_order_sales          # model and everything upstream

# Run a single test
dbt test --select stg_orders,test_type:singular
dbt test --select order_total_reconciles     # by custom generic test name
dbt build --select tag:canary                # canary DQ-proof tests (excluded from normal builds)

dbt docs generate && dbt docs serve
dbt clean                                    # wipe target/ and dbt_packages/
```

There is no separate lint/format step or CI config in this repo — correctness is enforced entirely through dbt's built-in and custom schema/data tests.

## Architecture: medallion layers

Bronze (`ZOMATO.RAW`, outside dbt) → Silver (`models/staging/`) → Gold (`models/marts/`), per `zomato/README.md`.

- **staging**: materialized as `view`s, 1:1 with each raw source table (`RESTAURANTS`, `USERS`, `FOOD`, `MENU`, `ORDERS`, `ORDER_ITEMS`, `REVIEWS` in `models/staging/_sources.yml`). Each `stg_*.sql` casts types, renames raw columns to conformed names, and does minimal parsing (e.g. regex-extracting numeric cost/rating out of messy raw strings) — but staging models must stay faithful to source grain and must **not** join across sources or pre-aggregate (see the note in `stg_reviews.sql` about a removed join, and `dim_customer.sql`'s note that order-derived metrics don't belong in a dimension model). Currency conversion (INR → CAD, fixed rate 0.015) is applied via the shared macro `{{ inr_to_cad(column) }}` (`macros/utils/inr_to_cad.sql`) wherever a monetary column is exposed.
- **marts**: materialized as `table`s in the `MARTS` schema, organized by subject area (`models/marts/core/`, `models/marts/executive/`). `core` holds the atomic Gold facts/dimension (`fct_order_sales` grain=order_id, `fct_order_items` grain=order_item_id, `dim_customer` grain=customer_id) that everything else builds from; subject-area marts (e.g. `mart_executive_summary`, grain=order_date) `ref()` the core facts rather than staging models directly. `models/marts/` is new/uncommitted work — check `git status` before assuming it matches what's on `main`.

Each model file's leading SQL comment states its **grain**, **FKs**, and any known data-quality caveats or proxy-metric definitions — read that comment before modifying a model, since the caveats (e.g. sample-data keyspace mismatches between dimensions and facts, `is_late_delivery_proxy` being a fixed 30-minute threshold rather than a real SLA breach, `line_amount` arithmetic tolerance) are load-bearing for how the accompanying tests are tuned.

## Data-quality testing pattern

Tests are split per-model under `macros/tests/<model_name>/` as custom generic (`{% test %}`) macros, referenced from the corresponding model's YAML (staging: `models/staging/_staging.yml`; marts: `models/marts/**/_*.yml`). Conventions to follow when adding tests:

- Every custom test sets `config(severity=...)` explicitly and explains the choice in a comment: `error` for things that are unambiguous bugs (arithmetic mismatches, cross-grain inconsistencies), `warn` for known/expected data issues (documented sample-data mismatches between staging models, an existing outlier value) that shouldn't block `dbt build`.
- Cross-grain/reconciliation tests (`order_total_reconciles`, `order_items_rollup_consistency`, the top-level `tests/assert_order_items_roll_up_to_orders.sql`) use `store_failures = true` and an explicit `alias` so failing rows land in a stable, inspectable table.
- `relationships` tests to dimensions with known sample-data gaps (`stg_menu` → `stg_restaurants`/`stg_food`, `stg_reviews` → `stg_users`, `fct_order_sales` → `dim_customer`) are intentionally `severity: warn`, not `error` — don't "fix" these by deleting the test or silently flipping severity without understanding the keyspace-mismatch note in that model's YAML/SQL comment first.
- `seeds/dq_canary_*` are synthetic, deliberately-broken rows (not real data) that exist purely to prove a given reconciliation test actually fires on a genuine violation; they're tagged `canary` and excluded from normal `dbt build` runs — see `tests/canary/test_dq_canary_grain_mismatch.sql` and `seeds/dq_canary.yml` for the pattern to follow if adding a new canary proof.
