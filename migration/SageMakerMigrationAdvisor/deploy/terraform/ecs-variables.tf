# Variables specific to ECS Fargate deployment

variable "my_ip_address" {
  description = "Your IP address in CIDR notation (e.g., 203.0.113.0/32) for ALB access restriction"
  type        = string
  default     = "0.0.0.0/0"  # Change this to your IP for security
}

variable "ecs_task_cpu" {
  description = "CPU units for ECS task (256, 512, 1024, 2048, 4096)"
  type        = string
  default     = "1024"  # 1 vCPU
}

variable "ecs_task_memory" {
  description = "Memory for ECS task in MB (512, 1024, 2048, 3072, 4096, 5120, 6144, 7168, 8192)"
  type        = string
  default     = "2048"  # 2 GB
}

variable "ecs_desired_count" {
  description = "Desired number of ECS tasks"
  type        = number
  default     = 1
}

variable "enable_cloudfront" {
  description = "Enable CloudFront distribution for HTTPS (no custom domain needed)"
  type        = bool
  default     = false
}

variable "cloudfront_only_access" {
  description = "When CloudFront is enabled, restrict ALB to CloudFront traffic only (recommended for security)"
  type        = bool
  default     = true
}

variable "certificate_arn" {
  description = "ARN of the SSL certificate from ACM for HTTPS (leave empty to use HTTP only)"
  type        = string
  default     = ""
}

variable "domain_name" {
  description = "Domain name for the application (optional, for Route53 DNS record)"
  type        = string
  default     = ""
}
