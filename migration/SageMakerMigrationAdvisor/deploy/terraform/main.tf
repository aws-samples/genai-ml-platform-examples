terraform {
  required_version = ">= 1.0"
  
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

# Cognito User Pool
resource "aws_cognito_user_pool" "migration_advisor" {
  name = "${var.app_name}-user-pool"

  password_policy {
    minimum_length    = 8
    require_lowercase = true
    require_numbers   = true
    require_symbols   = true
    require_uppercase = true
  }

  auto_verified_attributes = ["email"]

  schema {
    name                = "email"
    attribute_data_type = "String"
    required            = true
    mutable             = true
  }

  tags = var.tags
}

# Cognito User Pool Client
resource "aws_cognito_user_pool_client" "migration_advisor" {
  name         = "${var.app_name}-client"
  user_pool_id = aws_cognito_user_pool.migration_advisor.id

  generate_secret = true

  explicit_auth_flows = [
    "ALLOW_USER_PASSWORD_AUTH",
    "ALLOW_REFRESH_TOKEN_AUTH"
  ]

  prevent_user_existence_errors = "ENABLED"
}

# ECR Repository for Docker images
resource "aws_ecr_repository" "migration_advisor" {
  name                 = var.app_name
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }

  tags = var.tags
}

# S3 Bucket for artifacts
resource "aws_s3_bucket" "migration_advisor" {
  bucket = "${var.app_name}-artifacts-${data.aws_caller_identity.current.account_id}"

  tags = var.tags
}

# S3 Bucket versioning
resource "aws_s3_bucket_versioning" "migration_advisor" {
  bucket = aws_s3_bucket.migration_advisor.id

  versioning_configuration {
    status = "Enabled"
  }
}

# S3 Bucket encryption
resource "aws_s3_bucket_server_side_encryption_configuration" "migration_advisor" {
  bucket = aws_s3_bucket.migration_advisor.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

# Data source for current AWS account
data "aws_caller_identity" "current" {}

# Outputs
output "cognito_user_pool_id" {
  description = "Cognito User Pool ID"
  value       = aws_cognito_user_pool.migration_advisor.id
}

output "cognito_client_id" {
  description = "Cognito Client ID"
  value       = aws_cognito_user_pool_client.migration_advisor.id
}

output "cognito_client_secret" {
  description = "Cognito Client Secret"
  value       = aws_cognito_user_pool_client.migration_advisor.client_secret
  sensitive   = true
}

output "ecr_repository_url" {
  description = "ECR Repository URL"
  value       = aws_ecr_repository.migration_advisor.repository_url
}

output "s3_bucket_name" {
  description = "S3 Bucket Name"
  value       = aws_s3_bucket.migration_advisor.id
}
