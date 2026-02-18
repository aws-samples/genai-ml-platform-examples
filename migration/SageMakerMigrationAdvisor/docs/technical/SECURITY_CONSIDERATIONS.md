# Security Considerations

## Current Security Posture

### How Credentials Are Stored
AWS credentials are stored as **environment variables** in the Lightsail container configuration for Bedrock and S3 access.

**Note:** This approach is acceptable for development/testing but not recommended for production use.

## Key Security Risks

### High Priority
- **AWS Console Access**: Users with Lightsail permissions can view deployment configurations containing credentials
- **IAM User Compromise**: Stolen access keys could lead to unauthorized Bedrock/S3 access and cost overruns
- **Container Runtime**: Application vulnerabilities could expose environment variables

### Medium Priority
- **Application Logs**: Credentials might be accidentally logged
- **Terraform State**: Contains Cognito secrets (keep out of Git, use S3 backend with encryption)
- **Snapshots**: Lightsail snapshots include environment variables

### Current Mitigations
- ✅ Credentials not in Git repository (`.env` in `.gitignore`)
- ✅ IAM user has minimal permissions (Bedrock, S3 only)
- ✅ HTTPS-only communication

## Recommended Actions

### Immediate (Do Now)

1. **Enable CloudTrail** for audit logging
2. **Restrict IAM permissions** - Review who has Lightsail access
3. **Never log credentials** - Sanitize all log output
4. **Keep `.env` out of Git** - Already configured in `.gitignore`

### Short-term (1-2 weeks)

1. **Implement credential rotation** (every 90 days)
2. **Use Terraform S3 backend** with encryption for state files
3. **Add security scanning** for Docker images (AWS Inspector or Trivy)
4. **Set up CloudWatch alarms** for unusual Bedrock/S3 usage

### Production Deployment (Recommended)

**Migrate to ECS Fargate with IAM Task Roles** ⭐

Benefits:
- No credentials in environment variables
- Temporary credentials via IAM roles
- Automatic credential rotation
- Better security posture
- Similar cost (~$40-50/month)

Alternative: Use AWS Secrets Manager to fetch credentials at runtime

## Incident Response

### If Credentials Are Compromised

1. **Immediately disable the access key:**
```bash
aws iam update-access-key \
  --access-key-id <KEY_ID> \
  --status Inactive \
  --user-name sagemaker-migration-advisor-app-user
```

2. **Investigate via CloudTrail:**
```bash
aws cloudtrail lookup-events \
  --lookup-attributes AttributeKey=AccessKeyId,AttributeValue=<KEY_ID>
```

3. **Delete and recreate credentials:**
```bash
aws iam delete-access-key --access-key-id <KEY_ID> --user-name sagemaker-migration-advisor-app-user
bash deploy/add-credentials-to-lightsail.sh
```

4. **Review Bedrock and S3 usage** for unauthorized activity

---

## Compliance Notes

For production use requiring compliance (PCI DSS, HIPAA, SOC 2, GDPR):
- Environment variable storage may not meet requirements
- Use AWS Secrets Manager or ECS Fargate with IAM roles
- Enable comprehensive logging and monitoring
- Conduct regular security audits

---

## Summary

**Current Risk Level:** Medium-High (Development/Testing)

✅ **Acceptable for:** Development, testing, proof-of-concept  
⚠️ **Not recommended for:** Production deployments  
❌ **Not compliant with:** Most security standards

**For Production:** Migrate to ECS Fargate with IAM task roles to eliminate credential storage entirely.
