# S3 landing zone (ADR-004) + least-privilege IAM for the ingestion writer
# and the Snowflake storage integration reader. Kept small: one bucket, one
# prefix convention, two IAM principals. No cross-account complexity beyond
# what Snowflake's storage integration itself requires.

resource "aws_s3_bucket" "landing" {
  bucket = var.landing_bucket_name

  tags = {
    Project     = "delivery-data-pipeline"
    Environment = var.environment
    Purpose     = "immutable-ingestion-landing-zone"
  }
}

resource "aws_s3_bucket_versioning" "landing" {
  bucket = aws_s3_bucket.landing.id
  versioning_configuration {
    status = "Enabled" # replayability, see ADR-004
  }
}

resource "aws_s3_bucket_public_access_block" "landing" {
  bucket                  = aws_s3_bucket.landing.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_server_side_encryption_configuration" "landing" {
  bucket = aws_s3_bucket.landing.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "landing" {
  bucket = aws_s3_bucket.landing.id

  rule {
    id     = "raw-landing-transition"
    status = "Enabled"
    filter {
      prefix = "raw/"
    }
    # Immutable landing objects are never expired automatically, only moved
    # to cheaper storage. Deleting landing history is a human decision, not
    # a lifecycle default.
    transition {
      days          = var.landing_prefix_raw_retention_days
      storage_class = "GLACIER_IR"
    }
    noncurrent_version_transition {
      noncurrent_days = 30
      storage_class   = "GLACIER_IR"
    }
  }
}

# --- Ingestion writer identity ------------------------------------------------
# Assumed by the ingestion runner: local dev via `aws configure`, CI via
# OIDC, prod via an EC2 instance profile or task role. This role is what any
# of those actually assume, never long-lived static keys.

data "aws_iam_policy_document" "ingestion_writer_assume" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]
    principals {
      type        = "AWS"
      identifiers = ["arn:aws:iam::${data.aws_caller_identity.current.account_id}:root"]
    }
  }
}

data "aws_caller_identity" "current" {}

resource "aws_iam_role" "ingestion_writer" {
  name               = "delivery-pipeline-ingestion-writer-${var.environment}"
  assume_role_policy = data.aws_iam_policy_document.ingestion_writer_assume.json
}

data "aws_iam_policy_document" "ingestion_writer_permissions" {
  statement {
    sid     = "WriteLandingPrefixOnly"
    effect  = "Allow"
    actions = ["s3:PutObject"]
    resources = [
      "${aws_s3_bucket.landing.arn}/raw/*",
    ]
  }
  statement {
    sid       = "ListBucketForWriter"
    effect    = "Allow"
    actions   = ["s3:ListBucket"]
    resources = [aws_s3_bucket.landing.arn]
    condition {
      test     = "StringLike"
      variable = "s3:prefix"
      values   = ["raw/*"]
    }
  }
  # No s3:DeleteObject in prod: the landing zone is immutable (ADR-004).
  # Non-prod environments may extend this for cleanup convenience.
}

resource "aws_iam_role_policy" "ingestion_writer" {
  name   = "ingestion-writer-least-privilege"
  role   = aws_iam_role.ingestion_writer.id
  policy = data.aws_iam_policy_document.ingestion_writer_permissions.json
}

# --- Snowflake storage integration reader identity ----------------------------
# Trust policy uses Snowflake's own external-ID pattern; STORAGE_AWS_IAM_USER_ARN
# and STORAGE_AWS_EXTERNAL_ID come from `DESC INTEGRATION` after the integration
# is created (see snowflake/00_setup.sql). Terraform-managed here via a
# two-step apply (see infrastructure/terraform/README.md).

variable "snowflake_storage_aws_iam_user_arn" {
  description = "STORAGE_AWS_IAM_USER_ARN from `DESC STORAGE INTEGRATION delivery_s3_int`, set after the first apply that creates the Snowflake integration."
  type        = string
  default     = ""
}

variable "snowflake_storage_aws_external_id" {
  description = "STORAGE_AWS_EXTERNAL_ID from `DESC STORAGE INTEGRATION delivery_s3_int`."
  type        = string
  default     = ""
}

data "aws_iam_policy_document" "snowflake_reader_assume" {
  count = var.snowflake_storage_aws_iam_user_arn == "" ? 0 : 1
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]
    principals {
      type        = "AWS"
      identifiers = [var.snowflake_storage_aws_iam_user_arn]
    }
    condition {
      test     = "StringEquals"
      variable = "sts:ExternalId"
      values   = [var.snowflake_storage_aws_external_id]
    }
  }
}

resource "aws_iam_role" "snowflake_reader" {
  count              = var.snowflake_storage_aws_iam_user_arn == "" ? 0 : 1
  name               = "delivery-pipeline-snowflake-reader-${var.environment}"
  assume_role_policy = data.aws_iam_policy_document.snowflake_reader_assume[0].json
}

data "aws_iam_policy_document" "snowflake_reader_permissions" {
  statement {
    sid       = "ReadLandingPrefixOnly"
    effect    = "Allow"
    actions   = ["s3:GetObject"]
    resources = ["${aws_s3_bucket.landing.arn}/raw/*"]
  }
  statement {
    sid       = "ListBucketForReader"
    effect    = "Allow"
    actions   = ["s3:ListBucket"]
    resources = [aws_s3_bucket.landing.arn]
    condition {
      test     = "StringLike"
      variable = "s3:prefix"
      values   = ["raw/*"]
    }
  }
}

resource "aws_iam_role_policy" "snowflake_reader" {
  count  = var.snowflake_storage_aws_iam_user_arn == "" ? 0 : 1
  name   = "snowflake-reader-least-privilege"
  role   = aws_iam_role.snowflake_reader[0].id
  policy = data.aws_iam_policy_document.snowflake_reader_permissions.json
}
