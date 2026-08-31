# Infrastructure as Code

Terraform for the infrastructure that actually benefits from being
reproducible and code-reviewed: the S3 landing bucket + least-privilege IAM
(`aws.tf`), and the Snowflake warehouse/database/schemas/roles (`snowflake.tf`).

**What's not Terraformed**: object-level grants on individual dbt-created
tables/views (`snowflake/01_roles_and_grants.sql`), and the RAW table DDL /
control tables (`snowflake/02_bronze_tables.sql`,
`snowflake/03_control_tables.sql`). These change in lockstep with dbt models
and are naturally SQL-managed, run by CI/the pipeline's own setup step
rather than a separate Terraform apply loop. Terraforming *everything*
Snowflake-side would mean two competing tools (Terraform and dbt) both
trying to own table schemas; see the top-level README's "why not Terraform
everything" note.

## Usage

```bash
cd infrastructure/terraform
cp terraform.tfvars.example terraform.tfvars   # fill in real values, gitignored
terraform init
terraform plan  -var-file=terraform.tfvars
terraform apply -var-file=terraform.tfvars
```

Credentials: `AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY` (or an assumed role)
for the AWS provider; `SNOWFLAKE_ACCOUNT`/`SNOWFLAKE_USER`/
`SNOWFLAKE_PASSWORD` (or key-pair auth) for the Snowflake provider. Both come
from environment variables, never from `terraform.tfvars`.

## The two-step apply

Snowflake's `STORAGE INTEGRATION` and AWS's IAM trust policy for it are
mutually dependent (Snowflake needs the S3 bucket ARN; AWS needs Snowflake's
generated IAM user ARN + external ID). This repo resolves that with two
applies, documented in `outputs.tf`'s `next_step` output. It's a one-time
per-environment bootstrap step, not part of routine operation.

## Per environment

Run with a different `-var-file` (or a `dev.tfvars` / `staging.tfvars` /
`prod.tfvars`) per environment, and a separate Terraform state per
environment (e.g. an S3 backend keyed by `environment`). Not configured here,
to keep the reference minimal; see comments in `versions.tf`.
