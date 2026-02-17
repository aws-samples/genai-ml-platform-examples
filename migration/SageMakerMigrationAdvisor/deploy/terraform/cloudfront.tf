# CloudFront Distribution for HTTPS access without custom domain
# This provides HTTPS via CloudFront's default certificate

# CloudFront Distribution
resource "aws_cloudfront_distribution" "migration_advisor" {
  count               = var.enable_cloudfront ? 1 : 0
  enabled             = true
  is_ipv6_enabled     = true
  comment             = "SageMaker Migration Advisor - HTTPS via CloudFront"
  default_root_object = ""
  price_class         = "PriceClass_100"  # Use only North America and Europe

  origin {
    domain_name = aws_lb.migration_advisor.dns_name
    origin_id   = "alb-origin"

    custom_origin_config {
      http_port              = 80
      https_port             = 443
      origin_protocol_policy = "http-only"  # ALB uses HTTP
      origin_ssl_protocols   = ["TLSv1.2"]
    }

    custom_header {
      name  = "X-Custom-Header"
      value = random_password.cloudfront_secret[0].result
    }
  }

  default_cache_behavior {
    allowed_methods  = ["DELETE", "GET", "HEAD", "OPTIONS", "PATCH", "POST", "PUT"]
    cached_methods   = ["GET", "HEAD", "OPTIONS"]
    target_origin_id = "alb-origin"

    forwarded_values {
      query_string = true
      headers      = ["*"]

      cookies {
        forward = "all"
      }
    }

    viewer_protocol_policy = "redirect-to-https"
    min_ttl                = 0
    default_ttl            = 0
    max_ttl                = 0
    compress               = true
  }

  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }

  viewer_certificate {
    cloudfront_default_certificate = true
    minimum_protocol_version       = "TLSv1.2_2021"
  }

  tags = merge(var.tags, {
    Deployment = "ECS-Fargate-CloudFront"
  })
}

# Random secret for CloudFront to ALB communication
resource "random_password" "cloudfront_secret" {
  count   = var.enable_cloudfront ? 1 : 0
  length  = 32
  special = true
}

# Data source for CloudFront managed prefix list
data "aws_ec2_managed_prefix_list" "cloudfront" {
  count = var.enable_cloudfront ? 1 : 0
  name  = "com.amazonaws.global.cloudfront.origin-facing"
}

# Allow CloudFront to access ALB (when CloudFront is enabled)
resource "aws_security_group_rule" "alb_from_cloudfront" {
  count             = var.enable_cloudfront ? 1 : 0
  type              = "ingress"
  from_port         = 80
  to_port           = 80
  protocol          = "tcp"
  prefix_list_ids   = [data.aws_ec2_managed_prefix_list.cloudfront[0].id]
  security_group_id = aws_security_group.alb.id
  description       = "Allow HTTP from CloudFront managed prefix list"
}

# Outputs
output "cloudfront_domain_name" {
  description = "CloudFront distribution domain name (if enabled)"
  value       = var.enable_cloudfront ? aws_cloudfront_distribution.migration_advisor[0].domain_name : "CloudFront not enabled"
}

output "cloudfront_url" {
  description = "Full HTTPS URL via CloudFront (if enabled)"
  value       = var.enable_cloudfront ? "https://${aws_cloudfront_distribution.migration_advisor[0].domain_name}" : "CloudFront not enabled - set enable_cloudfront=true"
}

output "cloudfront_distribution_id" {
  description = "CloudFront distribution ID (if enabled)"
  value       = var.enable_cloudfront ? aws_cloudfront_distribution.migration_advisor[0].id : "CloudFront not enabled"
}
