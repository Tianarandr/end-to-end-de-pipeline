terraform {
  required_version = ">= 1.7"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    snowflake = {
      source  = "Snowflake-Labs/snowflake"
      version = "~> 0.94"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

provider "snowflake" {
  # Credentials read from SNOWFLAKE_* environment variables (SNOWFLAKE_ACCOUNT,
  # SNOWFLAKE_USER, SNOWFLAKE_PASSWORD or SNOWFLAKE_PRIVATE_KEY), never from
  # this file or a checked-in tfvars. See ../../.env.example.
  role = "ACCOUNTADMIN" # one-time infra provisioning only, not a runtime role
}
