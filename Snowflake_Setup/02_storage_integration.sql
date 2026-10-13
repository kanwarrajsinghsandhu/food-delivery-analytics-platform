USE ROLE ACCOUNTADMIN;

CREATE OR REPLACE STORAGE INTEGRATION ZOMATO_BLOB_INT
  TYPE = EXTERNAL_STAGE
  STORAGE_PROVIDER = 'AZURE'
  ENABLED          = TRUE
  AZURE_TENANT_ID = '3d61d24e-39f9-483e-b2b6-31e6318b387d'
  STORAGE_ALLOWED_LOCATIONS =('azure://stfooddeliverystatsprod.blob.core.windows.net/raw-telemetry');


GRANT USAGE ON INTEGRATION ZOMATO_BLOB_INT TO ROLE DBT_ROLE;

DESC STORAGE INTEGRATION ZOMATO_BLOB_INT;

-- Look for two properties in the output table:

-- AZURE_CONSENT_URL: A URL link to grant Snowflake permissions in your tenant.

-- AZURE_MULTI_TENANT_APP_NAME: Snowflake's Azure Enterprise App name (formatted like snowflake_app_123456...).
--