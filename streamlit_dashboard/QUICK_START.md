# Streamlit Dashboard — Quick Start Guide

## ⚡ 5-Minute Setup

### 1. Generate Keys (One-time)
```bash
cd .streamlit
openssl genrsa 2048 | openssl pkcs8 -topk8 -inform PEM -out rsa_key.p8 -nocrypt
openssl req -new -x509 -key rsa_key.p8 -out rsa_cert.crt -days 365
```

### 2. Register Public Key in Snowflake
```bash
cat rsa_cert.crt
```
Copy output. In Snowflake SQL Editor:
```sql
ALTER USER your_username SET RSA_PUBLIC_KEY='<paste cert>';
```

### 3. Configure Secrets
```bash
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
# Edit .streamlit/secrets.toml with your details
```

**Example secrets.toml:**
```toml
[snowflake]
user = "your_username"
private_key_path = "rsa_key.p8"
private_key_passphrase = ""
account = "xy12345.us-east-1"
warehouse = "ZOMATO_WH"
database = "ZOMATO"
schema = "MARTS"
```

### 4. Install & Run
```bash
pip install -r requirements.txt
streamlit run app.py
```

**Done!** Dashboard opens at `http://localhost:8501`

---

## 📊 Dashboard Pages

| Page | Question | Data Source |
|------|----------|-------------|
| 📈 Business Health | How is platform performance & retention trending? | `mart_executive_summary` |
| 👥 Customer Value | Which segments drive the most customer value? | `mart_customer_rfm` |
| 🔄 Retention & Activation | What drives repeat customers? | `mart_cohort_retention`, `mart_activation`, `mart_retention_diagnostic`, `mart_basket_discount` |

---

## 🔐 Security Checklist

- ✅ `.streamlit/secrets.toml` → `.gitignore` (never committed)
- ✅ `.streamlit/rsa_key.p8` → `.gitignore` (never committed)
- ✅ `.streamlit/rsa_cert.crt` → Can be committed (it's public)
- ✅ No passwords in code
- ✅ Safe for Streamlit Cloud deployment

---

## 🆘 Common Issues

| Problem | Solution |
|---------|----------|
| "Private key not found" | Check `rsa_key.p8` exists in `.streamlit/` |
| "Authentication failed" | Verify public key registered in Snowflake (`DESCRIBE USER`) |
| "No data from marts" | Run `dbt build` in `zomato/` directory first |
| "Failed to connect" | Check account identifier format & warehouse is active |

**Detailed help:** See `.streamlit/KEYPAIR_SETUP.md` or `README.md`

---

## 🚀 Next Steps

1. ✅ Set up keys & secrets (above)
2. ✅ Run `streamlit run app.py`
3. 📊 Explore the 3-page dashboard
4. 💬 Create LinkedIn content (see README.md for strategy)
5. 📈 Share findings with stakeholders
6. 🎨 Iterate on Power BI polish (Phase 2)

---

## 📚 Full Documentation

- **Setup details:** See `README.md`
- **Key pair walkthrough:** See `.streamlit/KEYPAIR_SETUP.md`
- **LinkedIn strategy:** See `README.md` (LinkedIn Content Strategy section)
- **Architecture & marts:** See `project_Plan.md` in repo root

---

**Ready?** Run step 1 above and let's go! 🚀
