# SageMaker Migration Advisor - Deployment Success

## ✅ Deployment Status: ACTIVE

Your SageMaker Migration Advisor is successfully deployed to AWS Lightsail Container Service.

**Application URL:** https://sagemaker-migration-advisor.nxpnv0fwethe0.us-east-1.cs.amazonlightsail.com/

**Test Credentials:**
- Username: `admin@example.com`
- Password: `SecurePass123!`

---

## 📊 Deployment Configuration

| Component | Details |
|-----------|---------|
| **Service** | sagemaker-migration-advisor |
| **Region** | us-east-1 |
| **Instance** | medium (1 GB RAM, 0.5 vCPU) |
| **Deployed** | 2026-02-04 21:48:33 UTC |
| **Cost** | ~$40-45/month |

### Infrastructure IDs
- **Cognito User Pool:** us-east-1_6BJtLHa5V
- **Cognito Client:** 2k4tgb96fpo8rkhv5o33u4n8ed
- **ECR Repository:** YOUR_AWS_ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com/sagemaker-migration-advisor
- **S3 Bucket:** sagemaker-migration-advisor-artifacts-YOUR_AWS_ACCOUNT_ID
- **CodeBuild Project:** sagemaker-migration-advisor-lightsail-pusher

---

## 🔄 Update Deployment

```bash
cd migration/SageMakerMigrationAdvisor

# Build and push to ECR
bash deploy/codebuild-deploy.sh

# Deploy to Lightsail
bash deploy/codebuild-lightsail.sh
```

---

## 🔍 Monitoring

**View logs:**
```bash
aws lightsail get-container-log \
  --service-name sagemaker-migration-advisor \
  --container-name app \
  --region us-east-1
```

**Check status:**
```bash
aws lightsail get-container-services \
  --service-name sagemaker-migration-advisor \
  --region us-east-1
```

---

## 🛠️ Troubleshooting

**Application not loading:**
- Check logs with command above
- Verify health endpoint: `/_stcore/health` returns 200

**Authentication issues:**
- Verify `.env` file has correct Cognito credentials
- Reset password: `bash deploy/reset-password.sh admin@example.com`

**WebSocket errors:**
- Lightsail supports WebSockets (unlike App Runner)
- Ensure URL uses `https://`

---

## 👥 User Management

```bash
cd deploy

# Create user
./create-user.sh user@example.com "Name" "Pass123!" "Users"

# List users
./list-users.sh

# Reset password
./reset-password.sh user@example.com "NewPass123!"
```

---

## 🗑️ Cleanup

```bash
# Delete Lightsail service
aws lightsail delete-container-service \
  --service-name sagemaker-migration-advisor \
  --region us-east-1

# Delete CodeBuild project
aws codebuild delete-project \
  --name sagemaker-migration-advisor-lightsail-pusher \
  --region us-east-1

# Delete Terraform resources (ECR, Cognito, S3)
cd deploy/terraform
terraform destroy
```

---

## 📚 Documentation

- **Quick Start:** See `QUICKSTART.md`
- **Full Guide:** See `DEPLOYMENT_GUIDE.md`
- **User Management:** See `deploy/create-user.sh`
