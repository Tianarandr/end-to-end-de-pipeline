# Snowflake infra: warehouse, database/schemas, and the least-privilege roles
# documented in docs/architecture/05-security.md. Grants on future
# tables/views are handled by snowflake/01_roles_and_grants.sql (run once per
# environment after `dbt build` creates the first objects). Terraform owns
# the roles and warehouse; dbt/SQL owns object-level grants that change as
# models are added, which is a poor fit for a Terraform apply loop.

resource "snowflake_warehouse" "delivery_wh" {
  name           = var.snowflake_warehouse_name
  warehouse_size = var.environment == "prod" ? "SMALL" : "XSMALL"
  auto_suspend   = 60
  auto_resume    = true
  initially_suspended = true
}

resource "snowflake_database" "delivery" {
  name    = var.snowflake_database_name
  comment = "delivery-data-pipeline (${var.environment}); see docs/architecture/03-data-model.md"
}

resource "snowflake_schema" "raw" {
  database = snowflake_database.delivery.name
  name     = "RAW"
  comment  = "Bronze: verbatim source copy plus ingestion metadata. No business logic. See docs/architecture/03-data-model.md#bronze-raw-schema."
}

resource "snowflake_schema" "staging" {
  database = snowflake_database.delivery.name
  name     = "STAGING"
  comment  = "Silver: typed, deduplicated, standardized. dbt views."
}

resource "snowflake_schema" "marts" {
  database = snowflake_database.delivery.name
  name     = "MARTS"
  comment  = "Gold: star schema plus business marts. dbt tables."
}

resource "snowflake_schema" "semantic" {
  database = snowflake_database.delivery.name
  name     = "SEMANTIC"
  comment  = "Semantic layer: curated, documented views plus metrics.yml. The only schema AI_READONLY_ROLE can read. See ADR-005."
}

resource "snowflake_schema" "ai" {
  database = snowflake_database.delivery.name
  name     = "AI"
  comment  = "AI-written outputs (review enrichment). Written only by AI_ENRICH_ROLE."
}

resource "snowflake_schema" "snapshots" {
  database = snowflake_database.delivery.name
  name     = "SNAPSHOTS"
}

# --- Roles (docs/architecture/05-security.md) ---------------------------------

resource "snowflake_role" "loader" {
  name    = "LOADER_ROLE"
  comment = "Ingestion writer. RAW + INGESTION_RUNS only. See ADR-004, 05-security.md."
}

resource "snowflake_role" "transform" {
  name    = "TRANSFORM_ROLE"
  comment = "dbt. Reads RAW, writes STAGING/MARTS/SEMANTIC/SNAPSHOTS."
}

resource "snowflake_role" "ai_enrich" {
  name    = "AI_ENRICH_ROLE"
  comment = "Batch AI enrichment writer. Reads STAGING.STG_REVIEWS, writes AI schema only."
}

resource "snowflake_role" "ai_readonly" {
  name    = "AI_READONLY_ROLE"
  comment = "RAG + text-to-SQL. SELECT on SEMANTIC only. See ADR-006."
}

resource "snowflake_warehouse_grant" "loader_wh" {
  warehouse_name = snowflake_warehouse.delivery_wh.name
  privilege      = "USAGE"
  roles          = [snowflake_role.loader.name]
}

resource "snowflake_warehouse_grant" "transform_wh" {
  warehouse_name = snowflake_warehouse.delivery_wh.name
  privilege      = "USAGE"
  roles          = [snowflake_role.transform.name]
}

resource "snowflake_warehouse_grant" "ai_enrich_wh" {
  warehouse_name = snowflake_warehouse.delivery_wh.name
  privilege      = "USAGE"
  roles          = [snowflake_role.ai_enrich.name]
}

resource "snowflake_warehouse_grant" "ai_readonly_wh" {
  warehouse_name = snowflake_warehouse.delivery_wh.name
  privilege      = "USAGE"
  roles          = [snowflake_role.ai_readonly.name]
}
