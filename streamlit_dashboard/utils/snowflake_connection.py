import streamlit as st
import pandas as pd
from snowflake.connector import connect
from snowflake.connector.errors import DatabaseError
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.backends import default_backend
import os


@st.cache_resource
def get_snowflake_connection():
    """Create and cache a Snowflake connection using key pair authentication."""
    try:
        snowflake_config = st.secrets["snowflake"]

        # Load private key
        private_key_path = snowflake_config.get("private_key_path")
        if not private_key_path:
            raise ValueError("private_key_path not found in secrets")

        # Resolve path relative to .streamlit directory
        if not os.path.isabs(private_key_path):
            streamlit_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            private_key_path = os.path.join(streamlit_dir, ".streamlit", os.path.basename(private_key_path))

        if not os.path.exists(private_key_path):
            raise FileNotFoundError(f"Private key not found at {private_key_path}")

        # Read and parse the private key
        with open(private_key_path, "rb") as key_file:
            private_key = serialization.load_pem_private_key(
                key_file.read(),
                password=snowflake_config.get("private_key_passphrase", "").encode() or None,
                backend=default_backend(),
            )

        # Create connection with key pair auth
        conn = connect(
            user=snowflake_config["user"],
            private_key=private_key,
            account=snowflake_config["account"],
            warehouse=snowflake_config["warehouse"],
            database=snowflake_config["database"],
            schema=snowflake_config["schema"],
            role=snowflake_config.get("role"),
        )
        return conn
    except FileNotFoundError as e:
        st.error(f"Private key file not found: {e}")
        st.stop()
    except KeyError as e:
        st.error(
            f"Missing Snowflake credentials in secrets: {e}. "
            "Ensure private_key_path, user, account, warehouse, database, and schema are set in `.streamlit/secrets.toml`"
        )
        st.stop()
    except DatabaseError as e:
        st.error(f"Failed to connect to Snowflake: {e}")
        st.stop()
    except Exception as e:
        st.error(f"Snowflake connection error: {e}")
        st.stop()


@st.cache_data(ttl=3600)
def query_snowflake(sql_query: str) -> pd.DataFrame:
    """Execute a SQL query against Snowflake and cache results for 1 hour."""
    try:
        conn = get_snowflake_connection()
        df = pd.read_sql(sql_query, conn)
        return df
    except Exception as e:
        st.error(f"Query failed: {e}")
        st.stop()


def get_mart_data(mart_name: str) -> pd.DataFrame:
    """Fetch data from a specific mart in ZOMATO.MARTS schema."""
    query = f"SELECT * FROM ZOMATO.MARTS.{mart_name}"
    return query_snowflake(query)
