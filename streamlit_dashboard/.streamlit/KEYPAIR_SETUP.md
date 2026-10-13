# Snowflake Key Pair Authentication Setup

This guide walks through setting up Snowflake key pair authentication for secure, password-free connections.

## Why Key Pair Auth?

✅ **More secure:** No passwords stored anywhere  
✅ **Rotatable:** Generate new keys without changing passwords  
✅ **Best practice:** Snowflake and Streamlit Cloud both recommend it  
✅ **No plain text:** Private keys stay private, even in config files  

---

## Step 1: Generate a Private Key (One-time Setup)

Run this command on your Mac:

```bash
cd streamlit_dashboard/.streamlit
openssl genrsa 2048 | openssl pkcs8 -topk8 -inform PEM -out rsa_key.p8 -nocrypt
```

This creates `rsa_key.p8` in the `.streamlit/` directory. **Keep this file secure and never commit it to git** (it's already in `.gitignore`).

**Output:**
```
rsa_key.p8   ← Your private key (keep secret)
```

---

## Step 2: Generate a Public Key Certificate

Still in the same directory:

```bash
openssl req -new -x509 -key rsa_key.p8 -out rsa_cert.crt -days 365
```

This prompts you for certificate details (you can press Enter to skip most fields, just provide Country at minimum):

```
-----
Country Name (2 letter code) [AU]:US
State or Province Name (full name) [Some-State]:
Locality Name (eg, city) []:
Organization Name (eg, company) [Internet Widgits Pty Ltd]:
Organizational Unit Name (eg, section) []:
Common Name (e.g. server FQDN or YOUR name) []:
Email Address []:
-----
```

**Output:**
```
rsa_cert.crt  ← Your public certificate (safe to share with Snowflake)
```

**Files created:**
```
.streamlit/
├── rsa_key.p8        ← PRIVATE (never share, in .gitignore)
└── rsa_cert.crt      ← PUBLIC (safe to commit or share)
```

---

## Step 3: Register the Public Key in Snowflake

Read your certificate:

```bash
cat rsa_cert.crt
```

Copy the entire output (including `-----BEGIN CERTIFICATE-----` and `-----END CERTIFICATE-----` lines).

In **Snowflake**, run this SQL as a user with `ACCOUNTADMIN` role:

```sql
ALTER USER <your_username> SET RSA_PUBLIC_KEY='<paste entire certificate here>';
```

**Example:**
```sql
ALTER USER kanwarraj SET RSA_PUBLIC_KEY='-----BEGIN CERTIFICATE-----
MIIDXTCCAkWgAwIBAgIJAJC1/iNAZwqDMA0GCSqGSIb3DQEBCwUAMEUxCzAJBgNV
...
-----END CERTIFICATE-----';
```

**To verify it worked:**
```sql
DESCRIBE USER <your_username>;
```

Look for `RSA_PUBLIC_KEY_FP` — if it's not empty, the key was registered successfully.

---

## Step 4: Configure `secrets.toml`

Copy the example and fill it in:

```bash
cp secrets.toml.example secrets.toml
```

Edit `.streamlit/secrets.toml`:

```toml
[snowflake]
user = "kanwarraj"
private_key_path = "rsa_key.p8"      # Points to the file you created
private_key_passphrase = ""           # Leave empty (we created it without a passphrase)
account = "xy12345.us-east-1"         # Your Snowflake account identifier
warehouse = "ZOMATO_WH"
database = "ZOMATO"
schema = "MARTS"
```

**Find your account identifier:**
- In Snowflake web UI, click your profile (top-right) → Accounts
- Or look at your login URL: `https://xy12345.us-east-1.snowflakecomputing.com`
- The account identifier is: `xy12345.us-east-1`

---

## Step 5: Test the Connection

Run the Streamlit app:

```bash
cd streamlit_dashboard
streamlit run app.py
```

If successful, you'll see the dashboard. If there's an error, check the terminal output.

**Common errors:**
- `FileNotFoundError: Private key not found` → Check `rsa_key.p8` exists in `.streamlit/`
- `Failed to connect to Snowflake` → Double-check your account identifier and warehouse name
- `Authentication failed` → Verify the public key was registered in Snowflake (run `DESCRIBE USER`)

---

## File Security Checklist

- ✅ `.streamlit/secrets.toml` is in `.gitignore` (never committed)
- ✅ `.streamlit/rsa_key.p8` is in `.gitignore` (never committed)
- ✅ `.streamlit/rsa_cert.crt` can be committed (it's public, not sensitive)
- ✅ Only you have read access to `rsa_key.p8` (check file permissions: `ls -la rsa_key.p8`)

---

## Rotating Keys (When Needed)

If you want to rotate your keys later:

1. Generate new `rsa_key.p8` and `rsa_cert.crt` (follow Steps 1-2)
2. Register the new public key in Snowflake (Step 3)
3. Optionally, unregister the old key: `ALTER USER <your_username> UNSET RSA_PUBLIC_KEY;`
4. Update `secrets.toml` if the file path changed

---

## Deploying to Streamlit Cloud

When you deploy to Streamlit Cloud:

1. **Do NOT** commit `secrets.toml` or `rsa_key.p8` to GitHub
2. In the Streamlit Cloud dashboard, go to **Settings** → **Secrets**
3. Paste the contents of your **local** `.streamlit/secrets.toml` (Streamlit Cloud encrypts it)
4. Your app will read secrets from Streamlit's secure vault, not from committed files

---

## References

- [Snowflake Key Pair Auth Docs](https://docs.snowflake.com/en/user-guide/key-pair-auth)
- [Streamlit Secrets Management](https://docs.streamlit.io/library/advanced-features/secrets-management)
- [OpenSSL Commands](https://www.openssl.org/docs/man1.1.1/man1/openssl.html)

---

**Questions?** Check the `README.md` troubleshooting section.
