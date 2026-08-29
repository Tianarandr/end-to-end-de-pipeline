output "landing_bucket_name" {
  value       = aws_s3_bucket.landing.bucket
  description = "S3 landing bucket name, set as S3_LANDING_BUCKET in .env."
}

output "ingestion_writer_role_arn" {
  value       = aws_iam_role.ingestion_writer.arn
  description = "IAM role the ingestion runner assumes to write to the landing zone."
}

output "snowflake_warehouse_name" {
  value = snowflake_warehouse.delivery_wh.name
}

output "snowflake_database_name" {
  value = snowflake_database.delivery.name
}

output "next_step" {
  value = <<-EOT
    1. Run `snowflake/00_setup.sql` to create the STORAGE INTEGRATION, then
       `DESC STORAGE INTEGRATION delivery_s3_int` to get STORAGE_AWS_IAM_USER_ARN
       and STORAGE_AWS_EXTERNAL_ID.
    2. Re-apply Terraform with -var snowflake_storage_aws_iam_user_arn=... and
       -var snowflake_storage_aws_external_id=... to create the scoped S3
       reader role for that integration (chicken-and-egg dependency between
       the two cloud providers, see infrastructure/terraform/README.md).
    3. Run snowflake/01_roles_and_grants.sql for object-level grants.
  EOT
}
