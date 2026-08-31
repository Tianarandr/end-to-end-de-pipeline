# Snowflake setup scripts

One-time, human-run bootstrap SQL. Run once per environment (dev/staging/prod)
by whoever holds `ACCOUNTADMIN` in that Snowflake account. **Never run by
Airflow, CI, or any application at runtime.** See
[docs/architecture/05-security.md](../docs/architecture/05-security.md#snowflake-roles).

Run in order:

```bash
snowsql -f snowflake/00_setup.sql -D env=DEV
# → DESC STORAGE INTEGRATION DELIVERY_S3_INT;  copy STORAGE_AWS_IAM_USER_ARN / STORAGE_AWS_EXTERNAL_ID
#   into infrastructure/terraform's second apply (see infrastructure/terraform/README.md)
snowsql -f snowflake/01_roles_and_grants.sql -D env=DEV
snowsql -f snowflake/02_bronze_tables.sql -D env=DEV
snowsql -f snowflake/03_control_tables.sql -D env=DEV
```

| File | Purpose |
|---|---|
| `00_setup.sql` | Warehouse, database, schemas, storage integration, stage, file format. |
| `01_roles_and_grants.sql` | The four least-privilege roles from `docs/architecture/05-security.md` and their grants, including `FUTURE` grants so new dbt models pick up the right access without a manual grant per model. |
| `02_bronze_tables.sql` | `RAW` table DDL, with the four technical metadata columns every Bronze table carries. |
| `03_control_tables.sql` | `INGESTION_RUNS`, `AI.ENRICHMENT_LOG`, `PUBLIC.PIPELINE_RUNS`: the observability backbone (`docs/architecture/06-observability.md`). |

Everything past this point (`STAGING`, `MARTS`, `SEMANTIC`, `AI.REVIEW_ENRICHED`)
comes from `dbt build` and the AI enrichment job, not hand-written DDL. See
[ADR-002](../docs/decisions/ADR-002-dbt.md).
