# HTTPS Setup Guide

Enable HTTPS for your SageMaker Migration Advisor deployment with AWS Certificate Manager (ACM).

## Prerequisites

- AWS account with ACM access
- Domain name (optional but recommended)
- DNS access for domain validation

## Request ACM Certificate

### AWS Console

1. Open AWS Certificate Manager in your deployment region
2. Click "Request a certificate" → "Request a public certificate"
3. Enter domain name: `advisor.yourdomain.com` (or `*.yourdomain.com` for wildcard)
4. Select "DNS validation" (recommended)
5. Add the CNAME record to your DNS provider
6. Wait for status "Issued" (typically 5-30 minutes)
7. Copy the Certificate ARN

### AWS CLI

```bash
aws acm request-certificate \
  --domain-name advisor.yourdomain.com \
  --validation-method DNS \
  --region us-east-1
```

**Note**: Certificate must be in the same region as your deployment.

## Deploy with HTTPS

### Using Deployment Script (Recommended)

```bash
cd migration/SageMakerMigrationAdvisor/deploy
./deploy-ecs.sh
```

When prompted:
- **Enable HTTPS?** → `yes`
- **Certificate ARN** → `<YOUR_ACM_CERTIFICATE_ARN>`
- **Domain Name** → `advisor.yourdomain.com` (or leave empty for ALB DNS)

### Manual Configuration

Create or edit `terraform.tfvars`:

```hcl
aws_region      = "us-east-1"
my_ip_address   = "YOUR.IP.ADDRESS/32"
certificate_arn = "<YOUR_ACM_CERTIFICATE_ARN>"
domain_name     = "advisor.yourdomain.com"  # Optional
```

Then deploy:

```bash
cd migration/SageMakerMigrationAdvisor/deploy/terraform
terraform init
terraform apply
```

## Configuration Options

### HTTP Only (Default)
No certificate needed. Application accessible via HTTP on port 80.

### HTTPS with ALB DNS
```hcl
certificate_arn = "<YOUR_ACM_CERTIFICATE_ARN>"
```
- HTTP redirects to HTTPS (301)
- Access via: `https://your-alb-name.us-east-1.elb.amazonaws.com`

### HTTPS with Custom Domain
```hcl
certificate_arn = "<YOUR_ACM_CERTIFICATE_ARN>"
domain_name     = "advisor.yourdomain.com"
```
- HTTP redirects to HTTPS (301)
- Route53 A record created automatically
- Access via: `https://advisor.yourdomain.com`
- Requires existing Route53 hosted zone

## Security

- **TLS**: 1.2 and 1.3 with strong cipher suites
- **Policy**: ELBSecurityPolicy-TLS13-1-2-2021-06
- **Redirect**: HTTP automatically redirects to HTTPS (301)
- **Certificate**: Managed by ACM with auto-renewal
- **IP Whitelisting**: Works on both HTTP and HTTPS ports

## Troubleshooting

### Certificate Not Found
**Issue**: Terraform can't find the certificate ARN  
**Solution**: Ensure certificate is in the same region as your deployment

### DNS Validation Pending
**Issue**: Certificate stuck in "Pending Validation"  
**Solution**: Add the CNAME record from ACM to your DNS provider

### Browser Certificate Warning
**Issue**: Browser shows certificate error  
**Solution**: 
- Verify certificate domain matches the URL you're accessing
- For ALB DNS: use wildcard certificate (`*.region.elb.amazonaws.com`)
- For custom domain: ensure certificate matches your domain

### HTTP Still Accessible
**Issue**: Can still access via HTTP after enabling HTTPS  
**Solution**: This is expected - HTTP automatically redirects to HTTPS (301)

## Cost

- **ACM Certificates**: FREE
- **ALB HTTPS**: No additional cost
- **Route53**: ~$0.50/month per hosted zone (if using custom domain)

## Additional Resources

- **Quick Reference**: `HTTPS_QUICK_REFERENCE.md`
- **Checklist**: `HTTPS_CHECKLIST.md`
- **AWS ACM Docs**: https://docs.aws.amazon.com/acm/
- **AWS ALB HTTPS**: https://docs.aws.amazon.com/elasticloadbalancing/latest/application/create-https-listener.html
