# SageMaker Migration Advisor - Quick Start Guide

Get up and running in 5 minutes!

## 🚀 Quick Setup

### 1. Setup Cognito (2 minutes)

```bash
cd migration/SageMakerMigrationAdvisor/deploy
./setup-cognito.sh
```

This creates:
- ✅ Cognito User Pool
- ✅ User Pool Client
- ✅ Admin and Users groups
- ✅ `.env` configuration file

### 2. Create a Test User (30 seconds)

```bash
./create-user.sh admin@example.com "Admin User" "SecurePass123!" "Admins"
```

### 3. Test Locally (1 minute)

```bash
cd ..
source venv/bin/activate
source .env
streamlit run app.py
```

Open browser: http://localhost:8501

Login with:
- **Email:** admin@example.com
- **Password:** SecurePass123!

### 4. Choose Your Mode

Select either:
- **🎯 Lite Mode** - Quick assessment (5-10 min)
- **🔬 Regular Mode** - Comprehensive analysis (15-30 min)

---

## 🌐 Deploy to AWS App Runner

### Option 1: Automated (Recommended)

```bash
cd deploy
./deploy.sh
```

Wait 5-10 minutes for deployment to complete.

### Option 2: Using Terraform

```bash
cd deploy/terraform

# Copy example variables
cp terraform.tfvars.example terraform.tfvars

# Edit variables (optional)
nano terraform.tfvars

# Deploy
terraform init
terraform apply
```

### Get Your Application URL

```bash
cd deploy/terraform
terraform output apprunner_service_url
```

Access at: `https://<service-id>.us-east-1.awsapprunner.com`

---

## 📝 User Management

### Create Users

```bash
cd deploy

# Create admin
./create-user.sh admin@company.com "Admin Name" "Pass123!" "Admins"

# Create regular user
./create-user.sh user@company.com "User Name" "Pass123!" "Users"
```

### List Users

```bash
./list-users.sh
```

### Reset Password

```bash
./reset-password.sh user@company.com "NewPass123!"
```

### Delete User

```bash
./delete-user.sh user@company.com
```

---

## 🎯 Using the Application

### 1. Login
- Enter your Cognito email and password
- Click "Login"

### 2. Select Mode
- **Lite**: Quick assessment, basic TCO, faster execution
- **Regular**: Full analysis, Q&A, diagrams, detailed TCO

### 3. Provide Architecture Info
- **Option A**: Upload architecture diagram (PNG/JPG)
- **Option B**: Describe your architecture in text

### 4. Follow the Workflow
- Answer clarifying questions (Regular mode only)
- Review SageMaker design recommendations
- View TCO analysis
- Download PDF report

---

## 🔧 Configuration

### Environment Variables

Edit `.env` file:

```bash
# AWS Configuration
AWS_REGION=us-east-1

# Cognito
COGNITO_USER_POOL_ID=us-east-1_XXXXXXXXX
COGNITO_CLIENT_ID=xxxxxxxxxxxxxxxxxxxx
COGNITO_CLIENT_SECRET=xxxxxxxxxxxxxxxxxxxxxxxx

# S3 (optional)
S3_BUCKET=your-bucket-name

# Bedrock (optional)
BEDROCK_MODEL_ID=us.anthropic.claude-sonnet-4-5-20250929-v1:0
```

### App Runner Configuration

Edit `deploy/terraform/terraform.tfvars`:

```hcl
aws_region = "us-east-1"
app_name   = "sagemaker-migration-advisor"

# Instance size
apprunner_cpu    = "2048"  # 2 vCPU
apprunner_memory = "4096"  # 4 GB

# Tags
tags = {
  Environment = "Production"
  Owner       = "ML-Team"
}
```

---

## 🐛 Troubleshooting

### Can't Login?

```bash
# Check user exists
cd deploy
source ../.env
aws cognito-idp admin-get-user \
  --user-pool-id $COGNITO_USER_POOL_ID \
  --username your-email@example.com \
  --region $AWS_REGION

# Reset password
./reset-password.sh your-email@example.com "NewPass123!"
```

### App Won't Start Locally?

```bash
# Check dependencies
pip install -r requirements.txt

# Check environment
source .env
echo $COGNITO_USER_POOL_ID

# Run in dev mode (no Cognito)
unset COGNITO_USER_POOL_ID
streamlit run app.py
```

### Deployment Failed?

```bash
# Check Terraform state
cd deploy/terraform
terraform show

# View logs
terraform apply -refresh-only

# Destroy and retry
terraform destroy
terraform apply
```

---

## 📊 Architecture Overview

```
┌─────────────────────────────────────────────┐
│           User Browser                       │
└─────────────────┬───────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────┐
│      AWS App Runner (Streamlit App)          │
│  ┌─────────────────────────────────────┐    │
│  │  Unified Frontend (app.py)          │    │
│  │  ├─ Login Page (Cognito Auth)       │    │
│  │  ├─ Mode Selection                  │    │
│  │  ├─ Lite Mode (advisor_lite.py)     │    │
│  │  └─ Regular Mode (advisor.py)       │    │
│  └─────────────────────────────────────┘    │
└─────────────────┬───────────────────────────┘
                  │
        ┌─────────┴─────────┐
        │                   │
        ▼                   ▼
┌──────────────┐    ┌──────────────┐
│   Cognito    │    │   Bedrock    │
│  User Pool   │    │   (Claude)   │
└──────────────┘    └──────────────┘
        │                   │
        ▼                   ▼
┌──────────────┐    ┌──────────────┐
│      S3      │    │     ECR      │
│  (Artifacts) │    │   (Images)   │
└──────────────┘    └──────────────┘
```

---

## 💰 Cost Estimate

### Monthly Costs (Typical Usage)

| Service | Usage | Cost |
|---------|-------|------|
| App Runner (2 vCPU, 4GB) | 24/7 | ~$100 |
| Cognito | 100 users | Free |
| Bedrock (Claude) | 1M tokens | ~$15 |
| S3 Storage | 10 GB | ~$0.23 |
| ECR | 1 image | ~$0.10 |
| **Total** | | **~$115/month** |

### Cost Optimization

- Use smaller App Runner instance for testing
- Enable auto-scaling to scale to zero
- Monitor Bedrock token usage
- Clean up old S3 artifacts

---

## 📚 Next Steps

1. ✅ **Read Full Documentation**: See `DEPLOYMENT_GUIDE.md`
2. ✅ **Configure Custom Domain**: Add your own domain to App Runner
3. ✅ **Enable Monitoring**: Set up CloudWatch alarms
4. ✅ **Train Users**: Share login credentials and user guide
5. ✅ **Customize**: Modify prompts and workflows as needed

---

## 🆘 Need Help?

- **Documentation**: `DEPLOYMENT_GUIDE.md`
- **Troubleshooting**: See troubleshooting section above
- **AWS Support**: Contact your AWS account team
- **Logs**: Check CloudWatch logs for errors

---

## 🎉 You're Ready!

Your SageMaker Migration Advisor is now configured and ready to use!

**Local URL**: http://localhost:8501  
**Production URL**: https://<your-service>.awsapprunner.com

Happy migrating! 🚀
