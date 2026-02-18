variable "aws_region" {
  description = "AWS region for deployment"
  type        = string
  default     = "us-east-1"
}

variable "app_name" {
  description = "Application name"
  type        = string
  default     = "sagemaker-migration-advisor"
}

variable "tags" {
  description = "Tags to apply to all resources"
  type        = map(string)
  default = {
    Application = "SageMaker Migration Advisor"
    ManagedBy   = "Terraform"
    Deployment  = "Lightsail"
  }
}
