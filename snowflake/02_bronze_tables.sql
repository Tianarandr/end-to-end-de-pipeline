-- Bronze (RAW) table DDL. Column shape mirrors the source CSVs exactly
-- (docs/architecture/03-data-model.md#bronze-raw-schema) plus four technical
-- metadata columns stamped by ingestion/ at load time, never by hand.
--
-- Usage: snowsql -f 02_bronze_tables.sql -D env=DEV

USE ROLE ACCOUNTADMIN;
SET db_name = 'DELIVERY_' || '&env';
USE DATABASE IDENTIFIER($db_name);
USE SCHEMA RAW;

-- Every RAW table gets these four columns, spelled out by hand rather than
-- via a template, so each table's DDL is self-contained and greppable.
--   _ingested_at   TIMESTAMP_LTZ  -- when the loader wrote this row
--   _source_file   STRING         -- METADATA$FILENAME from the stage
--   _batch_id      STRING         -- ingestion run_id (UUID), joins INGESTION_RUNS
--   _record_hash   STRING         -- MD5 of the raw column values

CREATE TABLE IF NOT EXISTS RAW.restaurants (
    _idx STRING,
    id STRING,
    name STRING,
    city STRING,
    rating STRING,
    rating_count STRING,
    cost STRING,
    cuisine STRING,
    lic_no STRING,
    link STRING,
    address STRING,
    menu STRING,
    _ingested_at TIMESTAMP_LTZ,
    _source_file STRING,
    _batch_id STRING,
    _record_hash STRING
);

CREATE TABLE IF NOT EXISTS RAW.users (
    _idx STRING,
    user_id STRING,
    name STRING,
    email STRING,
    password STRING,
    age STRING,
    gender STRING,
    marital_status STRING,
    occupation STRING,
    monthly_income STRING,
    education STRING,
    family_size STRING,
    _ingested_at TIMESTAMP_LTZ,
    _source_file STRING,
    _batch_id STRING,
    _record_hash STRING
);

CREATE TABLE IF NOT EXISTS RAW.food (
    _idx STRING,
    f_id STRING,
    item STRING,
    veg_or_non_veg STRING,
    _ingested_at TIMESTAMP_LTZ,
    _source_file STRING,
    _batch_id STRING,
    _record_hash STRING
);

CREATE TABLE IF NOT EXISTS RAW.menu (
    _idx STRING,
    menu_id STRING,
    r_id STRING,
    f_id STRING,
    cuisine STRING,
    price STRING,
    _ingested_at TIMESTAMP_LTZ,
    _source_file STRING,
    _batch_id STRING,
    _record_hash STRING
);

CREATE TABLE IF NOT EXISTS RAW.orders (
    order_id STRING,
    order_timestamp STRING,
    order_date STRING,
    user_id STRING,
    r_id STRING,
    restaurant_city STRING,
    cuisine STRING,
    items_count STRING,
    sales_qty STRING,
    subtotal STRING,
    discount STRING,
    delivery_fee STRING,
    gst STRING,
    sales_amount STRING,
    currency STRING,
    payment_method STRING,
    order_status STRING,
    customer_rating STRING,
    delivery_time_min STRING,
    _ingested_at TIMESTAMP_LTZ,
    _source_file STRING,
    _batch_id STRING,
    _record_hash STRING
);

CREATE TABLE IF NOT EXISTS RAW.order_items (
    order_item_id STRING,
    order_id STRING,
    r_id STRING,
    f_id STRING,
    price STRING,
    quantity STRING,
    line_amount STRING,
    _ingested_at TIMESTAMP_LTZ,
    _source_file STRING,
    _batch_id STRING,
    _record_hash STRING
);

CREATE TABLE IF NOT EXISTS RAW.reviews (
    review_id STRING,
    order_id STRING,
    user_id STRING,
    restaurant_id STRING,
    rating STRING,
    comment STRING,
    review_date STRING,
    _ingested_at TIMESTAMP_LTZ,
    _source_file STRING,
    _batch_id STRING,
    _record_hash STRING
);

-- Bronze stores every column as STRING even where the source "looks" numeric
-- (order_id, price, ...). Type casting is Silver's job (dbt staging), not
-- Bronze's. Keeping it untyped also means we can reload Bronze without a
-- schema migration if a source column that used to be clean numeric text
-- starts arriving with stray characters.

SELECT 'bronze_tables_complete' AS status;
