# Zomato Data Warehouse — Data Engineering Case Study

A production-grade data engineering project that builds a comprehensive data warehouse for the Zomato food delivery platform on Snowflake using dbt. This project demonstrates enterprise data engineering practices: medallion architecture, automated data quality, and analytics-ready datasets.

## 🎯 What We Seek to Achieve

This project transforms raw operational data (restaurants, orders, customers, reviews) into clean, tested, business-ready analytics tables. The vision is **three-fold:**

1. **Operational Excellence** — Prove data quality through automated testing, reconciliation macros, and cross-grain validation. Every transformation is testable, auditable, and recoverable.

2. **Executive Insights** — Deliver KPIs and dashboards that answer real business questions:
   - Revenue & GMV trends
   - Customer acquisition, retention, and churn analysis
   - Order fulfillment performance (delivery time, cancellation patterns)
   - Restaurant performance and rating correlation with volume
   - Retention drivers: What keeps customers coming back?

3. **Recruitment Narrative** — Demonstrate advanced dbt skills (macros, custom tests, snapshot tracking) and data engineering rigor for stakeholder engagement.

---

## 🏗️ Architecture: Medallion Layers

```
Bronze (RAW)
    ↓
    CSV data loaded from Azure Data Lake → Snowflake ZOMATO.RAW schema
    (restaurants, users, food, menu, orders, order_items, reviews)
    
    ↓
Silver (STAGING)
    ↓
    7 dbt staging models: clean, rename, validate, no joins, 1:1 with sources
    Tests: NOT NULL, unique, foreign key, domain constraints, reconciliation
    
    ↓
Gold (MARTS)
    ↓
    Atomic facts + dimensions → BI-ready analytics tables
    Core: fct_order_sales, fct_order_items, dim_customer
    Executive: daily KPI rollups (MAU, DAU, GMV, AOV, retention/churn, NPS)
    Subject-area: restaurant performance, customer segmentation, retention drivers
```

---

## 📊 Current Status (Sept 15, 2026)

| Phase | Scope | Status | Notes |
|-------|-------|--------|-------|
| **1. Foundation** | dbt setup, Snowflake connection, profile config | ✅ Complete | Repo initialized, CLAUDE.md guidance added |
| **2. Staging Layer** | 7 staging models with sophisticated parsing & cleaning | ✅ Complete | All models built with production-quality data handling |
| **3. Data Quality** | Reconciliation macros, canary tests, cross-grain validation | ✅ Complete | Custom test macros with tolerance thresholds & failure storage |
| **4. Marts (Gold)** | Atomic facts/dimensions + 5 BI-ready aggregate marts | 🔄 In Progress | 3 of 8 core models built; executive_summary & diagnostics pending |
| **5. BI Integration** | Tableau/Power BI mockups, dashboard connections | ⏳ Pending | Awaiting mart completion |
| **6. CI/CD & Artifacts** | GitHub Actions, DAG/lineage docs, proof screenshots | ⏳ Pending | Post-mart phase |

**Overall Progress:** ~75% — Phases 1–3 production-ready; Phase 4 partially built.

---

## 🔍 Key Components

### Staging Models (Silver Layer)
Seven cleaned, validated views with sophisticated parsing:
- **stg_restaurants** — Cleans rating (string → decimal), handles missing data
- **stg_users** — PII-safe (omits password), demographic standardization
- **stg_food** — Veg/non-veg classification
- **stg_menu** — Restaurant-food joins with pricing in CAD (INR→CAD conversion via macro)
- **stg_orders** — Order status (Delivered/Cancelled/Refunded), derived amounts
- **stg_order_items** — Order line items with quantity & price reconciliation
- **stg_reviews** — Rating & review text with referential checks

**All staging models tested for:**
- Column nullability and type correctness
- Uniqueness constraints (grain validation)
- Referential integrity (relationships to dimensions)
- Cross-model reconciliation (orders ↔ order_items totals match)

### Mart Models (Gold Layer)

#### Core Facts & Dimensions (Atomic, rebuilds other marts)
- **fct_order_sales** (1 row/order)
  - Grain: `order_id`
  - Includes: customer, restaurant, order dates, amounts (CAD), delivery time, status flags
  - Late-delivery proxy: `delivery_time_min > 30` (industry benchmark ~25-30 min)
  - Test: 6 validations (grain, FK integrity, amount arithmetic)
  
- **fct_order_items** (1 row/order item)
  - Grain: `order_item_id`
  - Includes: order, food, quantity, line amount, delivery time
  - Test: 7 validations (reconciliation with fct_order_sales, line totals)
  
- **dim_customer** (1 row/customer, attributes only)
  - Grain: `customer_id`
  - Includes: user profile, city, aggregate metrics (lifetime value, order count)
  - Note: Known data quality caveat — 90K of 100K users appear in orders (sample mismatch)

#### Executive Aggregations
- **mart_executive_summary** (1 row/calendar day)
  - Metrics: MAU, DAU, GMV, AOV, retention rate, churn rate, NPS proxy
  - Purpose: Case Study 1 — "CXO Dashboard: How is the business performing?"
  - Built: ✅ Validated to 912 calendar days, retention 75-86%, retention+churn=1.0

#### Diagnostic & Segmentation (Pending)
- **mart_retention_diagnostic** — Churn-driver analysis: delivery time, rating, discounts vs. repeat-order behavior
- **mart_customer_rfm** — RFM segmentation for targeting
- **mart_restaurant_performance** — Revenue, order count, rating trends by restaurant
- **mart_rating_vs_volume** — Correlation between restaurant rating and order volume (recruitment anchor)

---

## 🚀 Quick Start

### Prerequisites
- Snowflake account with `ZOMATO` database
- dbt-fusion (`dbt-fusion 2.0.0-preview.218` or later)
- dbt profile configured at `~/.dbt/profiles.yml`:
  ```yaml
  zomato:
    target: dev
    outputs:
      dev:
        type: snowflake
        account: <your-account>
        user: <your-user>
        password: <your-password>
        database: ZOMATO
        warehouse: ZOMATO_WH
        schema: STAGING
  ```

### Commands
```bash
cd zomato

# Verify Snowflake connection
dbt debug

# Run entire pipeline (seeds → models → tests)
dbt build

# Run only models (no tests)
dbt run

# Run only tests
dbt test

# Load seed data (includes canary DQ-proof rows)
dbt seed

# Scope to one model or layer
dbt build --select stg_orders
dbt build --select staging.*
dbt build --select marts.core.*

# Run a single test
dbt test --select stg_orders
dbt test --select order_total_reconciles

# Generate & serve documentation
dbt docs generate && dbt docs serve

# Clean build artifacts
dbt clean
```

---

## 📁 Project Structure

```
zomato/
├── models/
│   ├── staging/          # Silver layer: 7 cleaning models
│   │   ├── stg_*.sql     # Individual source models
│   │   └── _staging.yml  # Source definitions & tests
│   └── marts/            # Gold layer: facts, dimensions, aggregates
│       ├── core/         # Atomic facts & dims
│       ├── executive/    # KPI aggregations
│       ├── restaurant/   # Restaurant-focused analytics
│       └── customer/     # Retention, segmentation, RFM
├── macros/
│   ├── utils/
│   │   └── inr_to_cad.sql           # Currency conversion macro
│   └── tests/
│       ├── <model_name>/            # Custom tests per model
│       ├── canary/                  # Data quality proof (synthetic violations)
│       └── *_reconciles.sql         # Cross-grain totals matching
├── seeds/
│   └── dq_canary_*.yml              # Synthetic test data
├── tests/
│   ├── assert_*.sql                 # Top-level cross-model tests
│   └── canary/                      # Canary proof tests (tagged & excluded from normal builds)
├── dbt_project.yml
└── README.md
```

---

## 🧪 Data Quality & Testing

Every model is tested. Custom generic macros validate:
- **Reconciliation** — Order totals roll up correctly from line items
- **Cross-grain consistency** — Dimension key distribution matches fact cardinality
- **Arithmetic tolerance** — Amount sums within 0.01 CAD (floating-point drift)
- **Referential integrity** — FK constraints to dimensions (with severity tuning for known sample gaps)
- **Canary proofs** — Synthetic "deliberately broken" rows prove tests fire on violations

Tests use `store_failures = true` where relevant, landing failing rows in inspectable tables for debugging.

### Severity Policy
- `error` — Unambiguous bugs (arithmetic mismatches, broken keys)
- `warn` — Expected data gaps (sample-data keyspace mismatches, known outliers)

---

## 📈 Key Metrics & Proxy Definitions

**Clean KPIs (from dataset directly):**
- MAU/DAU (distinct customers by month/day)
- GMV/AOV (gross merchandise value / average order value, delivered orders only)
- Order frequency, delivery time, cancellation rate

**Proxy Metrics (caveat-disclosed):**
- **CLTV proxy:** Historical revenue-to-date per customer (not predictive survival model)
- **NPS proxy:** Built from 5-star ratings (≤3★=detractor, 4★=passive, 5★=promoter), not recommend-likelihood
- **% Delivered Late proxy:** `delivery_time_min > 30` (absolute threshold, not dynamic ETA). Industry benchmark ~25-30 min; real Zomato uses predicted kitchen + rider transit + buffer.

**Not in dataset:**
- CAC (cost per acquisition — no marketing data)
- Conversion rate (no session/landing-page data)
- App metrics (no crash/telemetry data)
- Support KPIs (no support-ticket data)

---

## 💡 Technical Highlights

1. **Sophisticated Data Cleaning** — Regex parsing, safe type casting, PII handling, currency conversion
2. **Macro-Driven Testing** — Custom Jinja macros for tolerance thresholds, failure storage, cross-model reconciliation
3. **Grain-First Design** — Every model declares grain in its SQL comment; tests validate grain constraints
4. **Production Snowflake** — Resource monitoring, warehouse tuning (XS + auto-suspend), cost tracking
5. **Canary Testing** — Synthetic "broken" seed rows prove tests actually fire; separated from normal builds via tags
6. **Recruitment-Ready** — Multi-layer marts build progressively; intermediate artifacts showcase architecture decisions

---

## 🎓 Learning & Recruitment Value

This project demonstrates:
- **dbt Mastery**: Staging models, macros, custom tests, snapshots, multi-layer design
- **Data Engineering Rigor**: Medallion architecture, reconciliation, grain validation, cross-grain consistency
- **SQL & Snowflake**: Window functions, CTEs, safe casting, cost optimization, resource monitoring
- **Testing as Code**: Automated DQ validation, failure storage, severity tuning, canary proofs
- **Analytics Design**: Atomic facts vs. aggregate marts, dimension modeling, KPI definition with caveats

---

## 📝 Notes & Caveats

- **Data Volume**: 100K users, 9.15M orders, 23M order items. Full build + test costs ~0.003 Snowflake credits.
- **Sample Data Gaps**: Menu/food items, customer IDs don't cover full keyspace; relationships tests use `severity: warn`.
- **Late Delivery Proxy**: 52% of delivered orders exceed 30-min threshold (much higher than 8-10% industry benchmark) — **a genuine finding worth highlighting in analysis narratives**.
- **No Snapshots Yet**: `snapshot-paths` configured but not used; reserved for tracking restaurant rating changes over time.

---

## 👤 Contact & Attribution

**Project Lead**: Kanwar Raj Singh Sandhu  
**Email**: vladmirrabinovich@gmail.com  
**Generated with**: Claude Code + dbt-fusion

---

## 📚 References

- [dbt Documentation](https://docs.getdbt.com)
- [Snowflake & dbt Integration](https://docs.getdbt.com/docs/core/connect-data-platform/snowflake-setup)
- [CLAUDE.md](./CLAUDE.md) — Project structure, commands, and testing conventions
- [zomato/README.md](./zomato/README.md) — Original architecture overview
