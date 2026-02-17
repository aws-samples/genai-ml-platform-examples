# HTTPS Enablement Checklist

Use this checklist to enable HTTPS for your SageMaker Migration Advisor deployment.

## Prerequisites

- [ ] AWS account with appropriate permissions
- [ ] Domain name (optional but recommended)
- [ ] Access to domain DNS settings (if using custom domain)
- [ ] Existing ECS deployment or ready to deploy

## Step 1: Request ACM Certificate

### Option A: Custom Domain (Recommended)

- [ ] Go to AWS Certificate Manager in your region
- [ ] Click "Request a certificate"
- [ ] Select "Request a public certificate"
- [ ] Enter your domain name (e.g., `advisor.yourdomain.com`)
- [ ] Select "DNS validation" method
- [ ] Click "Request"
- [ ] Copy the CNAME record details
- [ ] Add CNAME record to your DNS provider
- [ ] Wait for certificate status to show "Issued" (usually 5-30 minutes)
- [ ] Copy the Certificate ARN
- [ ] Save ARN: `_________________________________`

### Option B: Wildcard Certificate for ALB

- [ ] Request certificate for `*.region.elb.amazonaws.com`
- [ ] Follow DNS validation steps
- [ ] Copy the Certificate ARN
- [ ] Save ARN: `_________________________________`

## Step 2: Prepare Route53 (If Using Custom Domain)

- [ ] Verify Route53 hosted zone exists for your domain
- [ ] Note the hosted zone ID
- [ ] Ensure nameservers are configured correctly
- [ ] Domain name to use: `_________________________________`

## Step 3: Configure Deployment

### Option A: Using Deployment Script (Recommended)

- [ ] Navigate to deploy directory: `cd migration/SageMakerMigrationAdvisor/deploy`
- [ ] Run deployment script: `./deploy-ecs.sh`
- [ ] When prompted "Enable HTTPS?", enter: `yes`
- [ ] Enter your Certificate ARN
- [ ] Enter your domain name (or leave empty for ALB DNS)
- [ ] Confirm deployment

### Option B: Manual Configuration

- [ ] Create or edit `terraform.tfvars` in `deploy/terraform/`
- [ ] Add your certificate ARN:
  ```hcl
  certificate_arn = "arn:aws:acm:region:account:certificate/id"
  ```
- [ ] (Optional) Add your domain name:
  ```hcl
  domain_name = "advisor.yourdomain.com"
  ```
- [ ] Save the file
- [ ] Run: `cd deploy/terraform && terraform apply`

## Step 4: Verify Deployment

- [ ] Wait for Terraform to complete (5-10 minutes)
- [ ] Note the output URLs
- [ ] ALB URL: `_________________________________`
- [ ] HTTPS URL: `_________________________________`

## Step 5: Test HTTPS Access

- [ ] Open browser to HTTPS URL
- [ ] Verify certificate is valid (no browser warnings)
- [ ] Verify application loads correctly
- [ ] Test HTTP URL - should redirect to HTTPS
- [ ] Test login functionality
- [ ] Test file upload/download

## Step 6: DNS Propagation (If Using Custom Domain)

- [ ] Wait for DNS propagation (up to 48 hours, usually faster)
- [ ] Test domain resolution: `nslookup advisor.yourdomain.com`
- [ ] Verify domain points to ALB
- [ ] Test access via custom domain

## Step 7: Update Documentation

- [ ] Update internal documentation with HTTPS URL
- [ ] Update any bookmarks or saved links
- [ ] Notify team members of new URL
- [ ] Update any API clients or integrations

## Step 8: Security Verification

- [ ] Verify IP whitelisting still works
- [ ] Test from allowed IP - should work
- [ ] Test from different IP - should be blocked
- [ ] Verify HTTP redirects to HTTPS
- [ ] Check SSL Labs rating: https://www.ssllabs.com/ssltest/

## Troubleshooting Checklist

If something doesn't work:

- [ ] Certificate status is "Issued" in ACM
- [ ] Certificate is in the same region as deployment
- [ ] Certificate domain matches the URL you're accessing
- [ ] Security group allows your IP on port 443
- [ ] DNS records are correct (if using custom domain)
- [ ] ALB is healthy: `aws elbv2 describe-target-health`
- [ ] ECS tasks are running: `aws ecs describe-services`
- [ ] Check CloudWatch logs for errors

## Rollback Plan (If Needed)

If you need to revert to HTTP only:

- [ ] Edit `terraform.tfvars`
- [ ] Remove or comment out `certificate_arn` line
- [ ] Remove or comment out `domain_name` line
- [ ] Run: `terraform apply`
- [ ] Verify HTTP access works

## Post-Deployment Tasks

- [ ] Set up certificate renewal monitoring (ACM auto-renews)
- [ ] Configure CloudWatch alarms for ALB
- [ ] Update backup/disaster recovery procedures
- [ ] Document the HTTPS configuration
- [ ] Schedule periodic security reviews

## Cost Tracking

- [ ] Verify ACM certificate shows as FREE
- [ ] Monitor ALB costs (no change expected)
- [ ] Monitor Route53 costs (if using custom domain)
- [ ] Set up billing alerts if needed

## Maintenance Schedule

- [ ] Monthly: Review certificate expiration (ACM auto-renews)
- [ ] Quarterly: Review SSL/TLS policy for updates
- [ ] Annually: Review security group rules
- [ ] As needed: Update IP whitelist

## Notes

Use this space for deployment-specific notes:

```
Date deployed: _______________
Certificate ARN: _______________
Domain name: _______________
Deployed by: _______________
Issues encountered: _______________
_______________
_______________
```

## Success Criteria

Your HTTPS deployment is successful when:

- [x] Certificate shows as "Issued" in ACM
- [x] HTTPS URL loads without browser warnings
- [x] HTTP automatically redirects to HTTPS
- [x] Application functions correctly over HTTPS
- [x] IP whitelisting still works
- [x] Custom domain resolves correctly (if configured)
- [x] SSL Labs rating is A or higher

## Support Resources

- **Setup Guide**: `HTTPS_SETUP_GUIDE.md`
- **Quick Reference**: `HTTPS_QUICK_REFERENCE.md`
- **Examples**: `terraform.tfvars.example`
- **AWS ACM Docs**: https://docs.aws.amazon.com/acm/
- **AWS ALB Docs**: https://docs.aws.amazon.com/elasticloadbalancing/

---

**Checklist Version**: 1.0  
**Last Updated**: 2026-02-05  
**Maintained By**: DevOps Team
