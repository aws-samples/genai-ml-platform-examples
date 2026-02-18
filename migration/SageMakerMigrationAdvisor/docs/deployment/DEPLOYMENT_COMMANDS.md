# Quick Deployment Commands Reference

## 🚀 Update Deployment (One Command)

```bash
cd migration/SageMakerMigrationAdvisor/deploy
./update-ecs-deployment.sh
```

---

## 📦 Manual Build & Push

```bash
# Set variables
export AWS_REGION=us-east-1
export AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
export ECR_REPO="$AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/sagemaker-migration-advisor"

# Login to ECR
aws ecr get-login-password --region $AWS_REGION | docker login --username AWS --password-stdin $ECR_REPO

# Build and push
cd migration/SageMakerMigrationAdvisor
docker build -t $ECR_REPO:latest .
docker push $ECR_REPO:latest
```

---

## 🔄 Update ECS Service

```bash
# Force new deployment
aws ecs update-service \
  --cluster sagemaker-migration-advisor-cluster \
  --service sagemaker-migration-advisor-service \
  --force-new-deployment \
  --region us-east-1
```

---

## 📊 Monitor Deployment

```bash
# Watch service status
watch -n 5 'aws ecs describe-services \
  --cluster sagemaker-migration-advisor-cluster \
  --services sagemaker-migration-advisor-service \
  --region us-east-1 \
  --query "services[0].{Status:status,Running:runningCount,Desired:desiredCount,Rollout:deployments[0].rolloutState}"'
```

---

## 📝 View Logs

```bash
# Tail logs (follow)
aws logs tail /ecs/sagemaker-migration-advisor --follow --region us-east-1

# View recent logs
aws logs tail /ecs/sagemaker-migration-advisor --since 10m --region us-east-1
```

---

## 🔍 Check Status

```bash
# Service status
aws ecs describe-services \
  --cluster sagemaker-migration-advisor-cluster \
  --services sagemaker-migration-advisor-service \
  --region us-east-1 \
  --query 'services[0].{Status:status,Running:runningCount,Desired:desiredCount}'

# List tasks
aws ecs list-tasks \
  --cluster sagemaker-migration-advisor-cluster \
  --service-name sagemaker-migration-advisor-service \
  --region us-east-1

# Task details
aws ecs describe-tasks \
  --cluster sagemaker-migration-advisor-cluster \
  --tasks <TASK_ARN> \
  --region us-east-1
```

---

## 🌐 Get Application URL

```bash
cd migration/SageMakerMigrationAdvisor/deploy/terraform
terraform output alb_url
terraform output alb_https_url
```

---

## 🔙 Rollback

```bash
# List task definitions
aws ecs list-task-definitions \
  --family-prefix sagemaker-migration-advisor \
  --region us-east-1

# Rollback to previous revision
aws ecs update-service \
  --cluster sagemaker-migration-advisor-cluster \
  --service sagemaker-migration-advisor-service \
  --task-definition sagemaker-migration-advisor:<REVISION> \
  --region us-east-1
```

---

## 🛑 Stop/Start Service

```bash
# Scale down (stop)
aws ecs update-service \
  --cluster sagemaker-migration-advisor-cluster \
  --service sagemaker-migration-advisor-service \
  --desired-count 0 \
  --region us-east-1

# Scale up (start)
aws ecs update-service \
  --cluster sagemaker-migration-advisor-cluster \
  --service sagemaker-migration-advisor-service \
  --desired-count 1 \
  --region us-east-1
```

---

## 🗑️ Cleanup (Destroy)

```bash
cd migration/SageMakerMigrationAdvisor/deploy/terraform
terraform destroy
```

---

## 🔐 Update IP Whitelist

```bash
cd migration/SageMakerMigrationAdvisor/deploy/terraform

# Edit terraform.tfvars
# Change: my_ip_address = "x.x.x.x/32"

# Apply changes
terraform apply
```

---

## 📸 List ECR Images

```bash
aws ecr describe-images \
  --repository-name sagemaker-migration-advisor \
  --region us-east-1 \
  --query 'sort_by(imageDetails,& imagePushedAt)[*].[imageTags[0],imagePushedAt]' \
  --output table
```

---

## 🧹 Clean Old ECR Images

```bash
# List images older than 30 days
aws ecr describe-images \
  --repository-name sagemaker-migration-advisor \
  --region us-east-1 \
  --query 'imageDetails[?imagePushedAt<`2024-01-01`].[imageDigest]' \
  --output text | \
while read digest; do
  aws ecr batch-delete-image \
    --repository-name sagemaker-migration-advisor \
    --image-ids imageDigest=$digest \
    --region us-east-1
done
```

---

## 🔧 Debug Container

```bash
# Get task ID
TASK_ID=$(aws ecs list-tasks \
  --cluster sagemaker-migration-advisor-cluster \
  --service-name sagemaker-migration-advisor-service \
  --region us-east-1 \
  --query 'taskArns[0]' \
  --output text | awk -F'/' '{print $NF}')

# Execute command in container (requires ECS Exec enabled)
aws ecs execute-command \
  --cluster sagemaker-migration-advisor-cluster \
  --task $TASK_ID \
  --container sagemaker-migration-advisor \
  --interactive \
  --command "/bin/bash" \
  --region us-east-1
```

---

## 📈 CloudWatch Metrics

```bash
# CPU utilization
aws cloudwatch get-metric-statistics \
  --namespace AWS/ECS \
  --metric-name CPUUtilization \
  --dimensions Name=ServiceName,Value=sagemaker-migration-advisor-service Name=ClusterName,Value=sagemaker-migration-advisor-cluster \
  --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 300 \
  --statistics Average \
  --region us-east-1

# Memory utilization
aws cloudwatch get-metric-statistics \
  --namespace AWS/ECS \
  --metric-name MemoryUtilization \
  --dimensions Name=ServiceName,Value=sagemaker-migration-advisor-service Name=ClusterName,Value=sagemaker-migration-advisor-cluster \
  --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 300 \
  --statistics Average \
  --region us-east-1
```

---

## 🎯 Health Check

```bash
# Get ALB target group ARN
TG_ARN=$(aws elbv2 describe-target-groups \
  --region us-east-1 \
  --query 'TargetGroups[?contains(TargetGroupName, `sagemaker`)].TargetGroupArn' \
  --output text)

# Check target health
aws elbv2 describe-target-health \
  --target-group-arn $TG_ARN \
  --region us-east-1
```

---

## 💾 Backup Current State

```bash
# Export current task definition
aws ecs describe-task-definition \
  --task-definition sagemaker-migration-advisor \
  --region us-east-1 > task-definition-backup-$(date +%Y%m%d).json

# Export service configuration
aws ecs describe-services \
  --cluster sagemaker-migration-advisor-cluster \
  --services sagemaker-migration-advisor-service \
  --region us-east-1 > service-backup-$(date +%Y%m%d).json
```

---

## 🔄 Quick Status Check

```bash
# One-liner to check everything
echo "=== ECS Service ===" && \
aws ecs describe-services \
  --cluster sagemaker-migration-advisor-cluster \
  --services sagemaker-migration-advisor-service \
  --region us-east-1 \
  --query 'services[0].{Status:status,Running:runningCount,Desired:desiredCount,Deployment:deployments[0].rolloutState}' && \
echo -e "\n=== Recent Logs ===" && \
aws logs tail /ecs/sagemaker-migration-advisor --since 5m --region us-east-1 | tail -20 && \
echo -e "\n=== Application URL ===" && \
cd migration/SageMakerMigrationAdvisor/deploy/terraform && terraform output alb_url
```

---

**Pro Tip:** Save these commands in your shell history or create aliases for frequently used ones!
