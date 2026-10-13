"""Load generator output into Snowflake schema ZOMATO.RAW_V2.

- Dimension tables (RESTAURANTS, USERS, FOOD, MENU) are zero-copy CLONEs of ZOMATO.RAW, so dbt can
  point its whole `raw` source at RAW_V2 with one var.
- ORDERS, ORDER_ITEMS, REVIEWS are created with the same columns as RAW (CREATE TABLE ... LIKE),
  then loaded from data_generator/output/ via PUT to an internal stage + COPY INTO (strict).
- Connection details are read from the `zomato` profile in ~/.dbt/profiles.yml (key-pair auth).

Usage (from the repo root):
    .venv/bin/python -I data_generator/load_to_snowflake.py
"""

import json
from pathlib import Path

import snowflake.connector
import yaml
from cryptography.hazmat.primitives import serialization

HERE = Path(__file__).resolve().parent
OUT_DIR = HERE / "output"
TARGET = "RAW_V2"
DIMENSIONS = ["RESTAURANTS", "USERS", "FOOD", "MENU"]
FACTS = ["ORDERS", "ORDER_ITEMS", "REVIEWS"]


def connect():
    prof = yaml.safe_load((Path.home() / ".dbt" / "profiles.yml").read_text())["zomato"]
    cfg = prof["outputs"][prof["target"]]
    key = serialization.load_pem_private_key(Path(cfg["private_key_path"]).read_bytes(), password=None)
    der = key.private_bytes(
        serialization.Encoding.DER, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
    )
    return snowflake.connector.connect(
        account=cfg["account"], user=cfg["user"], private_key=der,
        role=cfg["role"], warehouse=cfg["warehouse"], database=cfg["database"],
    )


def run(cur, sql):
    print(f"> {sql.splitlines()[0][:110]}")
    cur.execute(sql)
    return cur.fetchall()


def main():
    summary = json.loads((OUT_DIR / "summary.json").read_text())
    expected = {"ORDERS": summary["orders_total"], "ORDER_ITEMS": summary["order_items"], "REVIEWS": summary["reviews"]}

    con = connect()
    cur = con.cursor()
    run(cur, f"create schema if not exists {TARGET}")
    run(cur, f"use schema {TARGET}")

    for t in DIMENSIONS:
        run(cur, f"create or replace table {TARGET}.{t} clone RAW.{t}")
    for t in FACTS:
        run(cur, f"create or replace table {TARGET}.{t} like RAW.{t}")

    run(cur, f"""create or replace file format {TARGET}.CSV_GZ
        type = csv compression = gzip field_delimiter = ',' field_optionally_enclosed_by = '"'
        skip_header = 1 empty_field_as_null = true null_if = ('') """)
    run(cur, f"create or replace stage {TARGET}.LOAD_STAGE file_format = {TARGET}.CSV_GZ")

    for t in FACTS:
        folder = OUT_DIR / t.lower()
        for f in sorted(folder.glob("*.csv.gz")):
            run(cur, f"put 'file://{f}' @{TARGET}.LOAD_STAGE/{t.lower()}/ parallel=8 auto_compress=false overwrite=true")
        run(cur, f"copy into {TARGET}.{t} from @{TARGET}.LOAD_STAGE/{t.lower()}/ on_error = 'abort_statement' purge = true")

    print("\nrow counts:")
    ok = True
    for t in FACTS:
        (n,), = run(cur, f"select count(*) from {TARGET}.{t}")
        match = n == expected[t]
        ok &= match
        print(f"  {t:12s} loaded={n:>12,}  expected={expected[t]:>12,}  {'OK' if match else 'MISMATCH'}")
    con.close()
    if not ok:
        raise SystemExit("row-count mismatch")


if __name__ == "__main__":
    main()
