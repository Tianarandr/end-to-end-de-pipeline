-- One-time bootstrap: warehouse, database, medallion + semantic + AI schemas,
-- S3 storage integration, stage, file format.
-- Run once per environment by an ACCOUNTADMIN. See snowflake/README.md.
--
-- Usage: snowsql -f 00_setup.sql -D env=DEV -D bucket=delivery-pipeline-landing-dev

USE ROLE ACCOUNTADMIN;

SET db_name = 'DELIVERY_' || '&env';

CREATE WAREHOUSE IF NOT EXISTS DELIVERY_WH
    WAREHOUSE_SIZE = 'XSMALL'
    AUTO_SUSPEND = 60
    AUTO_RESUME = TRUE
    INITIALLY_SUSPENDED = TRUE
    COMMENT = 'Shared warehouse for delivery-data-pipeline. Auto-suspends after 60s idle.';

CREATE DATABASE IF NOT EXISTS IDENTIFIER($db_name)
    COMMENT = 'delivery-data-pipeline (see docs/architecture/03-data-model.md)';

USE DATABASE IDENTIFIER($db_name);

-- Medallion + semantic + AI schemas (docs/architecture/03-data-model.md)
CREATE SCHEMA IF NOT EXISTS RAW       COMMENT = 'Bronze: verbatim source copy plus ingestion metadata. No business logic.';
CREATE SCHEMA IF NOT EXISTS STAGING   COMMENT = 'Silver: typed, deduplicated, standardized. dbt views.';
CREATE SCHEMA IF NOT EXISTS MARTS     COMMENT = 'Gold: star schema plus business marts. dbt tables.';
CREATE SCHEMA IF NOT EXISTS SEMANTIC  COMMENT = 'Semantic layer: curated, documented views plus metrics.yml (ADR-005). Only schema AI_READONLY_ROLE can read.';
CREATE SCHEMA IF NOT EXISTS AI        COMMENT = 'AI-written outputs (review enrichment). Written only by AI_ENRICH_ROLE.';
CREATE SCHEMA IF NOT EXISTS SNAPSHOTS COMMENT = 'dbt snapshots (SCD tracking), if/when introduced.';
CREATE SCHEMA IF NOT EXISTS PUBLIC    COMMENT = 'Cross-layer observability: PIPELINE_RUNS.';

-- --------------------------------------------------------------------------
-- S3 storage integration (ADR-004). STORAGE_ALLOWED_LOCATIONS is scoped to
-- exactly the landing bucket's raw/ prefix that infrastructure/terraform/aws.tf
-- provisions. Never a bare bucket root, and never '*'.
-- --------------------------------------------------------------------------

CREATE STORAGE INTEGRATION IF NOT EXISTS DELIVERY_S3_INT
    TYPE = EXTERNAL_STAGE
    STORAGE_PROVIDER = 'S3'
    ENABLED = TRUE
    STORAGE_AWS_ROLE_ARN = '&snowflake_reader_role_arn'  -- from infrastructure/terraform outputs, second apply
    STORAGE_ALLOWED_LOCATIONS = ('s3://&bucket/raw/');

-- After running this, capture the generated trust-policy values:
--   DESC STORAGE INTEGRATION DELIVERY_S3_INT;
-- copy STORAGE_AWS_IAM_USER_ARN and STORAGE_AWS_EXTERNAL_ID into the second
-- `terraform apply` (infrastructure/terraform/README.md) before files can
-- actually be read from S3.

CREATE FILE FORMAT IF NOT EXISTS RAW.CSV_FMT
    TYPE = 'CSV'
    COMPRESSION = 'AUTO'
    FIELD_DELIMITER = ','
    FIELD_OPTIONALLY_ENCLOSED_BY = '"'
    SKIP_HEADER = 1
    EMPTY_FIELD_AS_NULL = TRUE
    NULL_IF = (' ', '\\N', 'NULL')
    TRIM_SPACE = FALSE
    ERROR_ON_COLUMN_COUNT_MISMATCH = FALSE;

CREATE STAGE IF NOT EXISTS RAW.LANDING_STAGE
    STORAGE_INTEGRATION = DELIVERY_S3_INT
    URL = 's3://&bucket/raw/'
    FILE_FORMAT = RAW.CSV_FMT
    COMMENT = 'Immutable landing zone stage (see ADR-004).';

SELECT 'setup_complete' AS status, $db_name AS database_created;
