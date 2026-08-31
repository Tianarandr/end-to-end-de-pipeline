# 05: Security Model

## Principles

- No secrets in Git. `.env` is gitignored; `dbt/delivery_pipeline/profiles/profiles.yml`
  is gitignored (a `.example` is committed); CI never sees production credentials.
- Least privilege: **one Snowflake role per pipeline stage**, not one
  `DBT_ROLE` that can do everything (the original design's single
  `GRANT ALL ON DATABASE ... TO ROLE DBT_ROLE`).
- The AI layer never has write access outside its own schema, and never has
  access to `RAW` at all.
- `ACCOUNTADMIN` is used only in the one-time, human-run setup scripts
  (`snowflake/00_*`, `infrastructure/terraform`), never by an application,
  DAG, or service account at runtime.

## Snowflake roles

| Role | Used by | Grants |
|---|---|---|
| `LOADER_ROLE` | `ingestion/` | `USAGE` on warehouse; `INSERT`/`SELECT` on `RAW.*` and `INGESTION_RUNS`; `USAGE` on the S3 storage integration. **No access to `STAGING`/`MARTS`/`SEMANTIC`/`AI`.** |
| `TRANSFORM_ROLE` | dbt (staging/marts/semantic builds) | `SELECT` on `RAW`; full DML/DDL on `STAGING`, `MARTS`, `SEMANTIC`, `SNAPSHOTS`. **No access to `AI`** except `SELECT` where a semantic/AI-tagged model explicitly joins it. |
| `AI_ENRICH_ROLE` | `ai/enrichment/` | `SELECT` on `STAGING.STG_REVIEWS`; `INSERT`/`SELECT` on `AI.REVIEW_ENRICHED` and `AI.ENRICHMENT_LOG` only. **No `RAW` access, no write access outside `AI`.** |
| `AI_READONLY_ROLE` | `ai/rag/`, `ai/text_to_sql/` | `SELECT` on `SEMANTIC.*` only. **No `RAW`, `STAGING`, `MARTS`, or `AI` access, no write privileges anywhere.** This is the role the LLM's generated SQL ultimately executes under. The real guardrail is the grant, not just the SQL string check. |
| `ACCOUNTADMIN` | Human operators, one-time setup only | Full control. Never assumed by a service account. |

Defined in [snowflake/01_roles_and_grants.sql](../../snowflake/01_roles_and_grants.sql)
and mirrored in Terraform (`infrastructure/terraform/snowflake.tf`) for
environments where Snowflake infra is provisioned via IaC.

## Why a read-only role matters more than the SQL blocklist

A string-based "block DROP/DELETE/UPDATE" check (the original
`text_to_sql.py`) is necessary but not sufficient: it's trivially bypassed
by comments, encoding tricks, or a keyword the list didn't anticipate.
**The grant is the actual guardrail**: even a generated statement that
somehow passed validation cannot execute a mutation, because
`AI_READONLY_ROLE` has no `INSERT`/`UPDATE`/`DELETE`/`DDL` privileges on
anything, and no `SELECT` outside `SEMANTIC`. Guardrails here are defense in
depth: validate first (fast, clear error messages), then enforce at the
database (the layer that actually matters).

## Secrets and environments

- Local dev: `.env`, read via `python-dotenv` / `pydantic-settings`, never
  committed.
- CI: no real credentials. `dbt parse`/`dbt compile` run against a
  dummy profile (see [.github/workflows/ci.yml](../../.github/workflows/ci.yml));
  Python unit tests mock the Snowflake/OpenAI clients (`moto` for AWS).
- Staging/Prod: credentials injected by the orchestrator's secret backend
  (e.g. Airflow Connections backed by a secrets manager, or environment
  injection from the CI/CD deploy step), never written to disk in the
  image or repo.

## AWS / S3

- `S3_LANDING_BUCKET`: versioned, private, no public access; the only
  writer is the ingestion process's IAM role/user.
- Snowflake reads it via a `STORAGE INTEGRATION` (IAM role trust
  relationship, see `infrastructure/terraform/aws.tf`), not long-lived
  access keys embedded anywhere.
- Bucket policy and IAM role are least-privilege: `s3:GetObject` /
  `s3:ListBucket` scoped to the `raw/` prefix for Snowflake's role;
  `s3:PutObject` scoped to the same prefix for the ingestion role. Neither
  has delete rights on the immutable landing prefix in prod.
