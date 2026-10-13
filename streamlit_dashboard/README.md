# Zomato Analytics Dashboard

An interactive BI layer for the Zomato dbt project, built on the gold-layer `MARTS` schema.
Four pages — Marketplace Health, Customer Value, Retention & Activation, and a Method &
Data Quality reference page — implementing the redesign in `DASHBOARD_REDESIGN_SPEC.md`.
Every rate on this dashboard is a ratio-of-aggregates computed in SQL (never `AVG(rate)`
over cohorts of unequal size), and null results (first-order experience has no measurable
association with reordering) are reported explicitly rather than dressed up as findings.

---

## Quick Start

### 1. Prerequisites
- Python 3.9+ (ideally from the repo's `.venv`)
- Access to Snowflake with `ZOMATO.MARTS` schema populated (run `dbt build` in `zomato/` first)

### 2. Install Dependencies

```bash
cd streamlit_dashboard
pip install -r requirements.txt
```

### 3. Configure Snowflake Credentials (Key Pair Auth)

This dashboard uses **key pair authentication** (more secure than passwords).

#### Quick Start (5 minutes)

1. **Generate keys:**
   ```bash
   cd .streamlit
   openssl genrsa 2048 | openssl pkcs8 -topk8 -inform PEM -out rsa_key.p8 -nocrypt
   openssl req -new -x509 -key rsa_key.p8 -out rsa_cert.crt -days 365
   ```

2. **Register public key in Snowflake:**
   - Read your cert: `cat rsa_cert.crt`
   - In Snowflake, run:
     ```sql
     ALTER USER your_username SET RSA_PUBLIC_KEY='<paste cert contents>';
     ```

3. **Configure secrets:**
   ```bash
   cp secrets.toml.example secrets.toml
   ```
   Edit `.streamlit/secrets.toml`:
   ```toml
   [snowflake]
   user = "your_username"
   private_key_path = "rsa_key.p8"
   private_key_passphrase = ""
   account = "xy12345.us-east-1"  # your account identifier
   warehouse = "ZOMATO_WH"
   database = "ZOMATO"
   schema = "MARTS"
   ```

**For detailed walkthrough:** See [`.streamlit/KEYPAIR_SETUP.md`](.streamlit/KEYPAIR_SETUP.md)

**Security notes:**
- ✅ No passwords in code
- ✅ `secrets.toml` and `rsa_key.p8` are in `.gitignore` (never committed)
- ✅ Private key stays on your machine
- ✅ Safe to deploy to Streamlit Cloud (uses their secrets vault)

### 4. Run the Dashboard

```bash
streamlit run app.py
```

The app will open at `http://localhost:8501` in your browser.

---

## Dashboard Structure

### 📈 Page 1: Marketplace Health
- **Question:** What is happening across the marketplace, and is it healthy?
- **Sources:** `MART_EXECUTIVE_SUMMARY` (grain: order_date), `FCT_ORDER_SALES` (city/cuisine slices)
- **Visuals:** 5 KPI tiles (GMV, delivered orders, AOV, MAU, order failure rate) · GMV hero
  with an order-volume companion panel · monthly active customers · monthly retention rate ·
  delivery-time distribution with the 30-min proxy threshold drawn on it · order outcome mix
  over time (fixed status colors) · top cuisine tags by GMV · city performance table ·
  restaurant lookup (expander, framed as operational lookup, not a leaderboard)
- **Filters:** Date range, City, Cuisine tag, Order outcome (the only page using all four)

### 👥 Page 2: Customer Value
- **Question:** Where is customer value concentrated, and what drives it?
- **Source:** `MART_CUSTOMER_RFM` (grain: customer_id), `DIM_CUSTOMER` (demographics only)
- **Visuals:** 5 KPI tiles · value-concentration hero (paired share-of-customers vs
  share-of-value bars by segment) · Recency × Frequency density heatmap (SQL-binned) ·
  value-by-decile chart · RFM segment detail table · demographics expander (demoted —
  age/income/family size show ~zero correlation with value)
- **Filter:** RFM segment multiselect. Date/City are visually disabled here — RFM is a
  lifetime measure anchored to a fixed recency date, not a rolling window.

### 🔄 Page 3: Retention & Activation — the central storyline
- **Question:** Where do customers drop off, and what is — and isn't — associated with coming back?
- **Sources:** `MART_COHORT_RETENTION`, `MART_RETENTION_DIAGNOSTIC`, `MART_BASKET_DISCOUNT`
- **Visuals:** 5 activation KPIs (customer-weighted, never `AVG(pct)` over cohorts) · cohort
  retention heatmap (hero, defaults to cohorts with n≥100, suppresses smaller ones instead of
  showing sampling noise as signal) · selected-cohort curve vs platform-weighted benchmark ·
  activation windows (nested cumulative shares, explicitly not a funnel) · first-order
  experience diagnostics on a **fixed 0–100% axis** with a pooled-rate reference line — the
  differences are all well under a percentage point, and the page says so directly instead of
  letting an auto-scaled axis dramatize noise · discount-dependency table with `avg orders`
  exposed alongside value, so the reader sees the order-count confound instead of a misleading
  "discounted customers are less valuable" takeaway
- **Filters:** Minimum cohort size, cohort selector. City/cuisine are disabled — cohort
  membership is defined by a customer's *first* order, so filtering by city would retroactively
  redefine cohort sizes.
- **Caveat:** The experience-diagnostics and discount-dependency panels are observational, not
  causal, and are documented null results — see the Method page's "Null results log".

### 📋 Page 4: Method & Data Quality (reference)
- Four tabs: metric dictionary (every formula's numerator/denominator), proxies & limitations,
  the null-results log, and data lineage/freshness. No filters — this page exists so the three
  analytical pages don't need inline caveat blocks.

---

## Architecture

```
streamlit_dashboard/
├── app.py                          # st.navigation entry point + global filter bar
├── views/
│   ├── marketplace_health.py       # Page 1
│   ├── customer_value.py           # Page 2
│   ├── retention.py                # Page 3
│   └── method.py                   # Page 4
├── queries/                        # One module per page; all aggregation happens in SQL
│   ├── marketplace.py
│   ├── customers.py
│   └── retention.py
├── utils/
│   ├── snowflake_connection.py      # Connection + query caching
│   ├── theme.py                     # Design-system color tokens
│   ├── style.py                     # Injected CSS (8px spacing scale) + header helpers
│   ├── filters.py                   # Global sidebar filter bar + session_state
│   └── charts.py                    # Plotly figure factories (one per visual spec)
├── .streamlit/
│   └── secrets.toml.example        # Credential template (copy to secrets.toml)
├── requirements.txt                # Python dependencies
└── README.md                       # This file
```

### Key Utilities: `utils/snowflake_connection.py`

- **`get_snowflake_connection()`** — Creates and caches a Snowflake connection (via `@st.cache_resource`)
- **`query_snowflake(sql_query)`** — Executes SQL and caches results for 1 hour (via `@st.cache_data`)

Every query in `queries/*.py` pushes its `GROUP BY`/aggregation into Snowflake and returns
only presentation-grain rows — no `SELECT *` + pandas `groupby` pulls.

---

## Deployment

### Local
```bash
streamlit run app.py
```

### Streamlit Cloud (Free Hosting)

1. Push this `streamlit_dashboard/` directory to GitHub (ensure `.streamlit/secrets.toml` is in `.gitignore`)
2. Go to https://streamlit.io/cloud and click "Deploy an app"
3. Connect your GitHub repo and select this directory as the app root
4. Add Snowflake credentials in the Streamlit Cloud dashboard's "Secrets" section (same format as `.toml`)
5. App deploys automatically and updates on every push

**Cost:** Free tier available for non-commercial projects.

---

## LinkedIn Content Strategy

This MVP is a **strong case study** for LinkedIn engagement. Here's how to frame it:

### Narrative Arc
1. **Problem:** Building BI dashboards is slow. Power BI requires weeks of setup and learning; waiting blocks stakeholder insights.
2. **Insight:** The analytical work is already done in dbt (marts are built, tested, documented). BI is just visualization.
3. **Solution:** Streamlit + Python + Snowflake = MVP in days, not weeks.
4. **Result:** Working dashboard deployed and shareable within 48 hours; stakeholders get early insights; team validates analytical direction before investing in Power BI polish.

### Post Ideas

#### Post 1: The MVP Story (Carousel or Long-Form)
**Headline:** "How we shipped a retention dashboard in 2 days instead of 2 months"

**Sections:**
1. The problem: blocked stakeholder insights waiting on Power BI setup
2. The insight: data work ≠ BI work; marts were done, visualization was the blocker
3. The approach: Python + Streamlit + Snowflake, iterating live with stakeholders
4. The result: working 3-page dashboard deployed and shareable
5. The trade-off: Streamlit MVP vs. Power BI polish (and why the MVP won first)
6. What's next: using early feedback to drive Power BI polish

**Hashtags:** #DataEngineering #dbt #Streamlit #BI #Analytics #DataStack

#### Post 2: Technical Deep Dive (Twitter/Short-form)
**Headline:** "Building a BI layer on dbt marts with Streamlit: the architecture"

**Content:**
- dbt medallion layer (bronze/silver/gold) → mart schema (`ZOMATO.MARTS`)
- Streamlit multi-page app querying marts live
- Caching strategy: 1-hour TTL on query results
- 3 pages answering the cohesive question: "What drives repeat customers?"
- Code: https://github.com/[your-repo]/tree/main/streamlit_dashboard

#### Post 3: Lessons Learned (LinkedIn)
**Headline:** "What we learned building an MVP BI layer"

**Key points:**
- Speed > polish when validating analytical direction
- dbt's data quality tests + well-documented marts make BI *easy*
- Python/Streamlit iteration speed rivals hand-coded dashboards
- Observational analysis (this MVP) → hypothesis generation → causal testing (Phase B)
- The real blocker was never SQL; it was getting feedback fast

#### Post 4: Before/After Comparison
A side-by-side (or carousel slide) showing:
- **Before:** Waiting weeks for BI setup while stakeholders have questions
- **After:** Questions answered interactively in days; early feedback shapes Power BI roadmap

---

## Data Quality Notes

### Page 2 (Customer Value)
RFM is scored on `dim_customer`'s ~90,428 customers. Pages 1 & 3 use the full order-side population (~99,963 customers). This is intentional per the mart design; no live Power BI relationship bridges them.

### Page 3 (Retention & Activation)
- **Observational, not causal:** First-order metrics (delivery speed, rating) correlate with reorder rate, but confounders are not controlled for in this MVP.
- **Discount usage:** Is a customer choice, not a randomized treatment. Causal inference (Phase B) addresses this.
- Cohort retention heatmaps can have sparse cells (especially recent cohorts with few weeks of history). This is expected.

---

## Troubleshooting

### Key Pair Authentication Issues

**"Private key not found at ..."**
- Ensure `rsa_key.p8` exists in `.streamlit/` directory
- Check the path in `secrets.toml` matches the file location
- Verify file permissions: `ls -la .streamlit/rsa_key.p8`

**"Authentication failed" or "Permission denied"**
- Verify the public key was registered: `DESCRIBE USER your_username;` (look for `RSA_PUBLIC_KEY_FP`)
- Re-register if needed: `ALTER USER your_username SET RSA_PUBLIC_KEY='<cert contents>';`
- Ensure you're using the correct Snowflake username in `secrets.toml`

**"Missing Snowflake credentials in secrets"**
- Check `.streamlit/secrets.toml` exists (not just `.example`)
- Verify all required fields: `user`, `private_key_path`, `account`, `warehouse`, `database`, `schema`

### Connection Issues

**"Failed to connect to Snowflake"**
- Verify `ZOMATO_WH` warehouse exists and is active
- Check account identifier: `xy12345.us-east-1` (from your Snowflake URL)
- Test connection manually:
  ```bash
  python -c "from utils.snowflake_connection import get_snowflake_connection; get_snowflake_connection()"
  ```

**"No data available from MART_*"**
- Ensure `dbt build --exclude tag:canary` completed successfully in `zomato/` directory
- Verify marts exist: `SELECT * FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA = 'MARTS'`
- Check that your Snowflake user has `SELECT` permissions on `ZOMATO.MARTS` schema

**"Query failed" errors**
- Check Snowflake query history for the actual error message
- Verify column names match the marts exactly (case-sensitive in Snowflake)
- Check resource monitor quotas: `SHOW RESOURCE MONITORS;` → adjust if `CREDIT_LIMIT` exceeded

### For More Help

- See [`.streamlit/KEYPAIR_SETUP.md`](.streamlit/KEYPAIR_SETUP.md) for detailed key pair setup walkthrough
- Check the project's [CLAUDE.md](../CLAUDE.md) for dbt pipeline context

---

## Next Steps

### Short-term (Streamlit)
- Validate analytical direction with stakeholders using this MVP
- Gather feedback on what matters most (retention driver focus, new metrics, etc.)
- Iterate on visuals and filters based on usage

### Medium-term (Power BI)
- Use this MVP as a specification for the Power BI dashboard
- Design Power BI visuals with stakeholder feedback baked in
- Maintain both (Streamlit for analytical tinkering, Power BI for org-wide dashboarding)

### Long-term (Phase B)
- Multivariate analysis of reorder drivers (confounders controlled)
- Churn prediction model
- LTV prediction and optimization
- See `churn_ltv_prediction.py` and `project_Plan.md` for full Phase B roadmap

---

## Files & Documentation

- **`project_Plan.md`** (repo root) — Full project roadmap and architecture
- **`project_status_2026_09_27.md`** — Status snapshot (schema fix + BI work ahead)
- **`bi_dashboard_plan_phase_a.md`** — BI brief this dashboard implements
- **`models/marts/**`** — dbt gold-layer marts feeding this dashboard

---

## Author & Attribution

Built with [Claude Code](https://claude.com/claude-code) as a rapid MVP.

Data pipeline: dbt on Snowflake  
Visualization: Streamlit + Plotly

---

**Questions?** Check the troubleshooting section above, or review the project's `CLAUDE.md` for context on the dbt pipeline.
