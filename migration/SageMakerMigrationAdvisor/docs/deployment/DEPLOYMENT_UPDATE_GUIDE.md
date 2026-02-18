# ECS/Fargate Deployment Update Guide

Quick guide for updating your ECS/Fargate deployment with the latest code changes.

## 🚀 Quick Update (Recommended)

```bash
cd migration/SageMakerMigrationAdvisor/deploy
./update-ecs-deployment.sh
```

**Time:** 5-10 minutes

The script automatically:
1. Builds new Docker image
2. Pushes to ECR
3. Updates ECS service
4. Monitors deployment
5. Verifies success

---

## 📋 Prerequisites

- AWS CLI configured
- Docker running
- Existing ECS deployment
- ECR, ECS, CloudWatch permissions

---

## 🔍 Verification

After deployment completes, verify:

```bash
# Check service status
aws ecs describe-services \
  --cluster sagemaker-migration-advisor-cluster \
  --services sagemaker-migration-advisor \
  --region us-east-1 \
  --query 'services[0].{Status:status,Running:runningCount,Desired:desiredCount}'

# View logs
aws logs tail /ecs/sagemaker-migration-advisor --follow --region us-east-1

# Get application URL
cd deploy/terraform && terraform output alb_url
```

**Test the application:**
- ✅ Application loads
- ✅ Can upload diagrams
- ✅ Can generate reports
- ✅ PDF downloads work

---

## 🐛 Troubleshooting

### Docker Build Fails

```bash
# Start Docker
# Mac/Windows: Start Docker Desktop
# Linux: sudo systemctl start docker
```

### ECR Login Expired

```bash
aws ecr get-login-password --region us-east-1 | \
  docker login --username AWS --password-stdin \
  $(aws sts get-caller-identity --query Account --output text).dkr.ecr.us-east-1.amazonaws.com
```

### Service Not Updating

```bash
# Check service events
aws ecs describe-services \
  --cluster sagemaker-migration-advisor-cluster \
  --services sagemaker-migration-advisor \
  --region us-east-1 \
  --query 'services[0].events[0:5]'

# Force stop old tasks if stuck
aws ecs list-tasks \
  --cluster sagemaker-migration-advisor-cluster \
  --service-name sagemaker-migration-advisor \
  --region us-east-1

aws ecs stop-task \
  --cluster sagemaker-migration-advisor-cluster \
  --task <TASK_ID> \
  --region us-east-1
```

### Tasks Failing

```bash
# Check logs for errors
aws logs tail /ecs/sagemaker-migration-advisor --region us-east-1

# Common issues:
# - Missing environment variables
# - IAM permissions
# - Health check failures
```

---

## 🔄 Rollback

If the deployment has issues:

### Via CLI

```bash
# List previous task definitions
aws ecs list-task-definitions \
  --family-prefix sagemaker-migration-advisor \
  --region us-east-1

# Update to previous revision
aws ecs update-service \
  --cluster sagemaker-migration-advisor-cluster \
  --service sagemaker-migration-advisor \
  --task-definition sagemaker-migration-advisor:<PREVIOUS_REVISION> \
  --region us-east-1
```

### Via Console

1. Go to ECS Console → Clusters → sagemaker-migration-advisor-cluster
2. Select service → Update
3. Choose previous task definition revision
4. Update

---

## 📚 Related Documentation

- **ECS Deployment:** `ECS_DEPLOYMENT_SUMMARY.md`
- **Troubleshooting:** `TROUBLESHOOTING.md`
- **Quick Reference:** `ECS_DEPLOYMENT_TEST_RESULTS.md`

---

**Ready to update?**

```bash
cd migration/SageMakerMigrationAdvisor/deploy
./update-ecs-deployment.sh
```
