-- Observability backbone. See docs/architecture/06-observability.md.
-- INGESTION_RUNS (ingestion), AI.ENRICHMENT_LOG (AI attempts), PUBLIC.PIPELINE_RUNS
-- (whole-DAG-run summary, written by the Airflow `publish` task).
--
-- Usage: snowsql -f 03_control_tables.sql -D env=DEV

USE ROLE ACCOUNTADMIN;
SET db_name = 'DELIVERY_' || '&env';
USE DATABASE IDENTIFIER($db_name);

CREATE TABLE IF NOT EXISTS PUBLIC.INGESTION_RUNS (
    run_id             STRING NOT NULL,      -- UUID, one per DAG run
    source             STRING NOT NULL,      -- e.g. 'restaurants', 'orders'
    file_name          STRING,               -- S3 object key, null if the whole source had zero new files
    ingestion_timestamp TIMESTAMP_LTZ NOT NULL,
    row_count          NUMBER,
    status             STRING NOT NULL,      -- 'SUCCEEDED' | 'FAILED' | 'SKIPPED_ALREADY_LOADED'
    error_message      STRING,
    PRIMARY KEY (run_id, source, file_name)
)
COMMENT = 'One row per (run, source, file) ingestion attempt. See docs/architecture/02-data-flow.md and docs/data_contracts/.';

CREATE TABLE IF NOT EXISTS AI.ENRICHMENT_LOG (
    batch_id       STRING NOT NULL,      -- ingestion-style run_id for the enrichment DAG run
    review_id      STRING NOT NULL,
    attempt_number NUMBER NOT NULL,
    status         STRING NOT NULL,      -- 'SUCCEEDED' | 'FAILED'
    error_message  STRING,
    model_name     STRING,
    model_version  STRING,
    prompt_version STRING,
    processed_at   TIMESTAMP_LTZ NOT NULL,
    PRIMARY KEY (batch_id, review_id, attempt_number)
)
COMMENT = 'Every AI enrichment attempt, success or failure, so a batch can be safely retried without redoing completed work. See docs/architecture/04-ai-architecture.md#a-batch-ai-enrichment-aienrichment.';

CREATE TABLE IF NOT EXISTS AI.REVIEW_ENRICHED (
    review_id       STRING NOT NULL,
    sentiment_label STRING NOT NULL,
    sentiment_score FLOAT NOT NULL,
    topic           STRING NOT NULL,
    key_issue       STRING,
    model_name      STRING NOT NULL,
    model_version   STRING NOT NULL,
    prompt_version  STRING NOT NULL,
    batch_id        STRING NOT NULL,
    processed_at    TIMESTAMP_LTZ NOT NULL,
    PRIMARY KEY (review_id)
)
COMMENT = 'Success-only enrichment output. See docs/data_contracts/review_enriched.yml.';

CREATE TABLE IF NOT EXISTS PUBLIC.PIPELINE_RUNS (
    run_id            STRING NOT NULL,
    dag_run_id        STRING NOT NULL,
    started_at        TIMESTAMP_LTZ NOT NULL,
    finished_at       TIMESTAMP_LTZ,
    status            STRING,        -- 'SUCCESS' | 'FAILED' | 'PARTIAL'
    rows_ingested     NUMBER,
    dq_status         STRING,        -- 'passed' | 'warned' | 'failed'
    ai_success_count  NUMBER,
    ai_fail_count     NUMBER,
    PRIMARY KEY (run_id)
)
COMMENT = 'One row per Airflow DAG run: the top-level observability record. See docs/data_contracts/pipeline_runs.yml.';

SELECT 'control_tables_complete' AS status;
