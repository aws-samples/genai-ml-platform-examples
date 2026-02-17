# HTTPS Quick Reference Card

## 🚀 Quick Start

### 1. Request ACM Certificate (One-time)

```bash
# Via AWS Console
1. Go to AWS Certificate Manager
2. Request public certificate
3. Enter domain: advisor.yourdomain.com
4. Choose DNS validation
5. Add CNAME record to DNS
6. Wait for "Issued" status
7. Copy Certificate ARN

# Via AWS CLI
aws acm request-certificate \
  --domain-name advisor.yourdomain.com \
  --validation-method DNS \
  --region us-east-1
```

### 2. Deploy with HTTPS

```bash
cd migration/SageMakerMigrationAdvisor/deploy
./deploy-ecs.sh

# When prompted:
# Enable HTTPS? yes
# Certificate ARN: <YOUR_ACM_CERTIFICATE_ARN>
# Domain Name: advisor.yourdomain.com (or leave empty)
```

### 3. Access Your Application

```bash
# With custom domain
https://advisor.yourdomain.com

# With ALB DNS
https://your-alb-name.us-east-1.elb.amazonaws.com
```

## 📋 Configuration Options

### HTTP Only (Default)
```hcl
# terraform.tfvars
aws_region    = "us-east-1"
my_ip_address = "203.0.113.0/32"
# Don't set certificate_arn
```

### HTTPS with ALB DNS
```hcl
# terraform.tfvars
aws_region      = "us-east-1"
my_ip_address   = "203.0.113.0/32"
certificate_arn = "<YOUR_ACM_CERTIFICATE_ARN>"
```

### HTTPS with Custom Domain
```hcl
# terraform.tfvars
aws_region      = "us-east-1"
my_ip_address   = "203.0.113.0/32"
certificate_arn = "<YOUR_ACM_CERTIFICATE_ARN>"
domain_name     = "advisor.yourdomain.com"
```

## 🔧 Common Commands

### Check Certificate Status
```bash
aws acm describe-certificate \
  --certificate-arn <YOUR_ACM_CERTIFICATE_ARN> \
  --region us-east-1
```

### List Certificates
```bash
aws acm list-certificates --region us-east-1
```

### Test HTTPS
```bash
curl -I https://advisor.yourdomain.com
```

### Update Existing Deployment
```bash
cd deploy/terraform
# Edit terraform.tfvars to add certificate_arn
terraform apply
```

## 🛡️ Security

- **TLS Version**: 1.2 and 1.3
- **Policy**: ELBSecurityPolicy-TLS13-1-2-2021-06
- **Redirect**: HTTP → HTTPS (301)
- **IP Whitelist**: Still active on both ports

## 💰 Cost

- ACM Certificate: **FREE**
- ALB HTTPS: **No extra cost**
- Route53: **~$0.50/month** (if using custom domain)

## ❓ Troubleshooting

| Issue | Solution |
|-------|----------|
| Certificate not found | Ensure certificate is in same region |
| DNS validation pending | Add CNAME record to DNS |
| Browser warning | Check certificate domain matches URL |
| Can't access HTTPS | Check security group allows your IP |

## 📚 Full Documentation

- **Setup Guide**: `HTTPS_SETUP_GUIDE.md`
- **Examples**: `terraform.tfvars.example`
- **Summary**: `../../HTTPS_IMPLEMENTATION_SUMMARY.md`

## 🎯 Variables Reference

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `certificate_arn` | No | `""` | ACM certificate ARN for HTTPS |
| `domain_name` | No | `""` | Custom domain for Route53 |
| `my_ip_address` | Yes | `0.0.0.0/0` | Your IP for access control |
| `aws_region` | Yes | `us-east-1` | AWS region |

## 🔄 Outputs

After deployment:
```bash
terraform output alb_url          # Primary URL (HTTP or HTTPS)
terraform output alb_https_url    # HTTPS URL (if configured)
terraform output alb_dns_name     # ALB DNS name
terraform output route53_record   # DNS record status
```
