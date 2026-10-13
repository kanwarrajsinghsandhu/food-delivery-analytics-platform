import sys

# Read certificate
with open('.streamlit/rsa_cert.crt', 'r') as f:
    cert = f.read().strip()

# Print the SQL statement
print("Copy this entire line and paste into Snowflake:")
print(f"ALTER USER your_username SET RSA_PUBLIC_KEY='{cert}';")
