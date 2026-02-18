# CloudFront HTTPS Guide

## Overview

Get HTTPS without a custom domain using CloudFront's default SSL certificate.

**Benefits:**
- ✅ Free HTTPS certificate included
- ✅ No domain purchase or DNS setup required
- ✅ Global CDN performance
- ✅ DDoS protection (AWS Shield Standard)
- ✅ Works immediately (5-10 min deployment)

## Quick Start

```bash
cd migration/SageMakerMigrationAdvisor/deploy/terraform

# Add to terraform.tfvars
echo 'enable_cloudfront = true' >> terraform.tfvars

# Deploy
terraform apply

# Get your HTTPS URL
terraform output cloudfront_url
# Output: https://d1234567890abc.cloudfront.net
```

## Architecture

```
User Browser (HTTPS)
    ↓
CloudFront Distribution
    ↓
Application Load Balancer (HTTP)
    ↓
ECS Fargate Tasks
```

## Configuration

### Enable CloudFront

```hcl
# terraform.tfvars
enable_cloudfront = true
```

### With IP Whitelisting (Recommended)

```hcl
# terraform.tfvars
enable_cloudfront = true
my_ip_address     = "203.0.113.0/32"
```

This configuration:
- CloudFront: Open HTTPS access for all users
- Direct ALB: IP-whitelisted (your IP only)

### Disable CloudFront

```hcl
# terraform.tfvars
enable_cloudfront = false
```

## Cost

**CloudFront Costs:**
- Data Transfer: $0.085/GB (first 10 TB)
- HTTPS Requests: $0.010 per 10,000 requests
- Free Tier: 1 TB + 10M requests/month (first 12 months)

**Example:** 100 GB transfer + 1M requests = ~$8.50/month
**Total with ECS:** ~$55/month

## Troubleshooting

### 502/504 Errors

Check ECS service and ALB health:
```bash
aws ecs describe-services \
  --cluster sagemaker-migration-advisor-cluster \
  --services sagemaker-migration-advisor

aws elbv2 describe-target-health \
  --target-group-arn $(terraform output -raw alb_target_group_arn)
```

### Distribution Stuck "In Progress"

Normal - CloudFront deployment takes 5-15 minutes. Check status:
```bash
aws cloudfront get-distribution \
  --id $(terraform output -raw cloudfront_distribution_id) \
  --query 'Distribution.Status'
```

### Application Not Loading

Invalidate CloudFront cache:
```bash
aws cloudfront create-invalidation \
  --distribution-id $(terraform output -raw cloudfront_distribution_id) \
  --paths "/*"
```

## Management Commands

```bash
# Get CloudFront URL
terraform output cloudfront_url

# Check distribution status
aws cloudfront get-distribution \
  --id $(terraform output -raw cloudfront_distribution_id)

# Invalidate cache
aws cloudfront create-invalidation \
  --distribution-id $(terraform output -raw cloudfront_distribution_id) \
  --paths "/*"

# Disable CloudFront
# Edit terraform.tfvars: enable_cloudfront = false
terraform apply
```

## CloudFront vs Custom Domain

| Feature | CloudFront | Custom Domain + ACM |
|---------|-----------|---------------------|
| Setup Time | 5-10 minutes | Hours (DNS validation) |
| Domain Required | No | Yes |
| HTTPS Certificate | Free (included) | Free (ACM) |
| Cost | ~$8/month | Domain registration cost |
| Branding | CloudFront domain | Your domain |

## Next Steps

1. Set `enable_cloudfront = true` in terraform.tfvars
2. Run `terraform apply`
3. Wait 5-10 minutes for deployment
4. Get URL: `terraform output cloudfront_url`
5. Access your application via HTTPS

## Resources

- [CloudFront Documentation](https://docs.aws.amazon.com/cloudfront/)
- [CloudFront Pricing](https://aws.amazon.com/cloudfront/pricing/)
- [Best Practices](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/best-practices.html)
