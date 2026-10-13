USE ROLE ACCOUNTADMIN;
USE DATABASE ZOMATO;
USE SCHEMA RAW;

CREATE OR REPLACE FILE FORMAT ZOMATO.RAW.CSV_FMT
   TYPE = 'CSV'
   COMPRESSION = 'AUTO'
   FIELD_DELIMITER = ','
   FIELD_OPTIONALLY_ENCLOSED_BY = '"'
   SKIP_HEADER = 1
   EMPTY_FIELD_AS_NULL = TRUE
   NULL_IF = (' ', '\\N', 'NULL')
   TRIM_SPACE = FALSE
   ERROR_ON_COLUMN_COUNT_MISMATCH = FALSE;

CREATE OR REPLACE STAGE ZOMATO.RAW.ZOMATO_RAW_STAGE
  URL = 'azure://stfooddeliverystatsprod.blob.core.windows.net/raw-telemetry/'
  STORAGE_INTEGRATION = ZOMATO_BLOB_INT
  FILE_FORMAT = ZOMATO.RAW.CSV_FMT;

-- Confirm Snowflake can see your files (should list the seven table folders).
-- This will list ONLY the 7 CSV files across all directories
LIST @ZOMATO.RAW.ZOMATO_RAW_STAGE PATTERN = '.*\.csv$';
