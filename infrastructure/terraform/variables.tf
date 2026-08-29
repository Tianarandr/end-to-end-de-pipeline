variable "environment" {
  description = "Deployment environment: dev | staging | prod"
  type        = string
  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "environment must be one of: dev, staging, prod."
  }
}

variable "aws_region" {
  description = "AWS region for the S3 landing bucket."
  type        = string
  default     = "ap-southeast-2"
}

variable "landing_bucket_name" {
  description = "Name of the S3 bucket used as the immutable ingestion landing zone (ADR-004)."
  type        = string
}

variable "snowflake_account_locator" {
  description = "Snowflake account identifier, used to scope the storage integration trust policy."
  type        = string
}

variable "snowflake_warehouse_name" {
  description = "Name of the Snowflake warehouse used by this pipeline."
  type        = string
  default     = "DELIVERY_WH"
}

variable "snowflake_database_name" {
  description = "Name of the Snowflake database for this environment, e.g. DELIVERY_DEV."
  type        = string
}

variable "landing_prefix_raw_retention_days" {
  description = "Days before objects under the raw/ landing prefix transition to cheaper storage. Landing objects are never deleted automatically (immutable landing principle, ADR-004)."
  type        = number
  default     = 90
}
