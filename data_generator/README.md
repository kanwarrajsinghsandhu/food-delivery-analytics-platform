# Order data generator

The tutorial dataset this project started from had real restaurant listings (scraped from Swiggy, with menus) and a synthetic 100K-user panel. Its **orders were synthetic too, and their behaviour wasn't realistic**:

- About 85% of all users ordered every month.
- New customers dried up: 16K in Feb 2024, 3 in Jun 2026.
- Order frequency climbed steadily for 2.5 years.
- AOV, ratings and cancellation rate were flat to two decimals.
- Rating had no relationship to delivery time.
- Review dates ran up to 900 days *before* their order.

Retention, cohort and growth-accounting analysis is meaningless on that data, so this generator replaces **ORDERS, ORDER_ITEMS and REVIEWS** with calibrated synthetic behaviour. The real dimensions (RESTAURANTS, MENU, FOOD, USERS) are untouched.

> **The order data is simulated, not real Zomato performance.** Parameters are calibrated to public disclosures where they exist and are documented as assumptions where they don't. Treat trends in the marts as properties of the simulation, not business findings.

## What it models
Every value lives in [`params.yml`](params.yml), tagged `[source]`, `[observed]` or `[assumption]`.

- **Acquisition:**
  - 55% of users are an existing base, with prior tenure, whose first observed order falls in a Jul–Dec 2023 burn-in.
  - The rest arrive Jan 2024–Jun 2026 at ~25%/yr growth, with festive bumps.
  - The burn-in exists so growth accounting doesn't label the whole existing base as "new" in Jan 2024.
- **Lifecycle:**
  - Each customer has their own order rate (Gamma-distributed, heavy tail).
  - Monthly lapse risk is steep in months 1–2 and low after a year.
  - Lapsed customers come back with a small monthly probability, higher Oct–Dec.
- **Calendar:** festive Oct–Dec peak, monsoon Jul–Sep dip (slower deliveries, more cancellations), weekend uplift, lunch and dinner hour peaks.
- **Restaurants:**
  - Popularity is weighted by Swiggy rating-count tier.
  - Customers have 3 favourites, and ~40% of orders go to them. ~5% of orders are outside the home city.
  - Only 12K of the 148K listings have a scraped menu; the rest use a same-cuisine donor restaurant's menu.
- **Basket and price:** items and prices come from real menus, with +5.5%/yr price drift. GST is 5%. Delivery fee, payment mix and item counts follow the original data.
- **Discounts:** ~70% of first orders, ~60% of comeback orders, ~30% of all others.
- **Rating:** falls with delivery time, plus noise (correlation about −0.37).

## The one deliberate deviation: a heavy-user panel
The project keeps ~10M orders in the Jan 2024–Jun 2026 window with a fixed 100K users. That works out to **~6–7 orders per active customer per month**, against Swiggy's 4.07 in FY26. The 100K should be read as a heavy-user panel, like a loyalty-programme slice. Month-over-month retention (~88%) is high for the same reason.

## Planted effects (pipeline validation, not findings)
- A first delivery slower than 40 min raises month-1 lapse risk (×1.8) and halves early ordering.
- A first-order rating below 3 raises month-1 lapse risk (×1.5).
- Discount-acquired new customers lapse faster at every tenure (×1.3).

The generator recomputes the 30-day reorder outcome per first-order bucket straight from the orders it writes, using `mart_retention_diagnostic`'s exact rules. It writes the result to `zomato/seeds/generator_ground_truth.csv`. `zomato/tests/generator/assert_planted_effects_recovered.sql` then requires the mart to match exactly, which proves the raw → staging → core → mart pipeline doesn't distort the data.

## Run it
From the repo root. Needs `zomato_engineering_raw_data/` locally, and `snowflake-connector-python` in `.venv` for loading.

```bash
.venv/bin/python -I data_generator/generate.py --calibrate     # lifecycle + volume report, ~10s
.venv/bin/python -I data_generator/generate.py                 # full run, ~3 min, writes output/ + ground-truth seed
.venv/bin/python -I data_generator/load_to_snowflake.py        # ZOMATO.RAW_V2: clones dims, loads facts, checks counts
cd zomato && dbt build --exclude tag:canary                    # dbt sources default to RAW_V2
```

`dbt build --vars '{raw_schema: RAW}'` rebuilds on the original tutorial data for comparison. The generator test is disabled there.

## Output (seed 20260612)
| | |
|---|---|
| Orders | 11.44M total, 10.03M in Jan 2024–Jun 2026 |
| Order items / reviews | 25.5M / 369K |
| MAU | 44.7K (Jan 2024) → 60.5K (Jun 2026), ~20% YoY by 2026 |
| New customers / month | ~1.1K–1.9K |
| AOV (delivered, INR) | 552 (2024) → 581 (2025) → 604 (2026) |
| Cancel / refund rate | 5.4% / 2.4%, varying by city and season |

## Sources
- Swiggy FY26: 4.07 orders per transacting user per month (4.43 in FY25, 4.48 in FY24); MTU +33% YoY — [Inc42](https://inc42.com/buzz/over-35-of-swiggy-users-try-multiple-services-but-order-frequency-slips/)
- Zomato Dec-2025 quarter: average MTU +21% YoY to 24.9M — [Outlook Business](https://www.outlookbusiness.com/corporate/swiggy-magicpin-zomato-see-food-delivery-regain-growth-momentum-in-dec-qtr)

## Known caveats
- 136K restaurants use a donor menu, so their item lists are realistic for the cuisine but not their own.
- Users have no city in the source, so each customer's home city is drawn from the restaurant distribution.
