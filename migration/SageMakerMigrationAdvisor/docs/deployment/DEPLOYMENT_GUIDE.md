# SageMaker Migration Advisor - Deployment Guide

Complete guide for deploying the SageMaker Migration Advisor with two deployment options:
1. **AWS Lightsail** - Simple, cost-effective deployment
2. **ECS Fargate + ALB** - Production-ready with IAM roles and IP whitelisting

---

## Deployment Options Comparison

| Feature | Lightsail | ECS Fargate + ALB |
|---------|-----------|-------------------|
| **Setup Complexity** | Simple | Moderate |
| **Security** | IAM user credentials | IAM task roles (no credentials) |
| **IP Whitelisting** | Not supported | ✅ Supported |
| **Scalability** | Limited | Auto-scaling ready |
| **Cost** | ~$40/month | ~$30-50/month |
| **Best For** | Development/Testing | Production/Internal Use |

---

## Prerequisites

- AWS CLI configured with appropriate credentials
- Terraform installed (for infrastructure setup)
- Access to AWS Bedrock in your region
- Docker image building capability (via AWS CodeBuild)

---

## Common Setup (Both Deployments)

### Step 1: Deploy Shared Infrastructure with Terraform

This creates ECR repository, Cognito User Pool, and S3 bucket (shared by both deployment options).

```bash
cd migration/SageMakerMigrationAdvisor/deploy/terraform
terraform init
terraform apply
```

**Outputs you'll get:**
- Cognito User Pool ID
- Cognito Client ID and Secret
- ECR Repository URL
- S3 Bucket Name

### Step 2: Create Cognito Test User

After Terraform creates the Cognito User Pool, create a test user:

```bash
cd ../deploy
./create-user.sh admin@example.com "Admin User" "SecurePass123!" "Admins"
```

This creates an admin user with the specified password.

### Step 3: Build and Push Docker Image to ECR

Use CodeBuild to build and push the image (no local Docker required):

```bash
./codebuild-deploy.sh
```

This script creates a CodeBuild project that builds the image and pushes to ECR.

---

## Option A: Lightsail Deployment

**Best for:** Development, testing, simple deployments

### Deployment Steps

#### 1. Deploy to Lightsail

This pulls the image from ECR and deploys to Lightsail Container Service.

```bash
cd deploy
./codebuild-lightsail.sh
```

**What this does:**
1. Creates Lightsail Container Service (if not exists)
2. Enables ECR private registry access
3. Uses CodeBuild to pull from ECR and push to Lightsail registry
4. Creates deployment with proper environment variables
5. Waits for deployment to complete

#### 2. Add Bedrock Permissions

Lightsail containers don't support IAM roles, so we need to add AWS credentials.

```bash
./add-credentials-to-lightsail.sh
```

**What this does:**
1. Creates IAM user: `sagemaker-migration-advisor-app-user`
2. Attaches Bedrock and S3 permissions
3. Creates access key
4. Updates Lightsail deployment with credentials in environment variables

### Access the Application

Get your application URL:

```bash
aws lightsail get-container-services \
  --service-name sagemaker-migration-advisor \
  --region us-east-1 \
  --query 'containerServices[0].url' \
  --output text
```

**Login:**
- Username: `admin@example.com`
- Password: `SecurePass123!` (or the password you set)

### Lightsail Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                         User Browser                         │
└────────────────────────┬────────────────────────────────────┘
                         │ HTTPS
                         ▼
┌─────────────────────────────────────────────────────────────┐
│              AWS Lightsail Container Service                 │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  Streamlit App (app.py)                              │  │
│  │  - Cognito Authentication                            │  │
│  │  - Mode Selection (Lite/Regular)                     │  │
│  │  - WebSocket Support ✅                              │  │
│  │  - IAM User Credentials (env vars)                   │  │
│  └──────────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────────┘
         │              │              │              │
         │              │              │              │
         ▼              ▼              ▼              ▼
    ┌────────┐    ┌─────────┐   ┌─────────┐   ┌──────────┐
    │ Amazon │    │ Amazon  │   │ Amazon  │   │  Amazon  │
    │Cognito │    │ Bedrock │   │   S3    │   │   ECR    │
    └────────┘    └─────────┘   └─────────┘   └──────────┘
```

---

## Option B: ECS Fargate + ALB Deployment

**Best for:** Production, internal use, IP whitelisting required

### Deployment Steps

#### 1. Deploy to ECS Fargate

This creates ECS cluster, Fargate service, ALB, and all necessary resources.

```bash
cd deploy
./deploy-ecs.sh
```

**What this does:**
1. Prompts for your IP address (for ALB access restriction)
2. Verifies Docker image exists in ECR
3. Creates terraform.tfvars with your IP
4. Deploys ECS infrastructure:
   - ECS Cluster with Container Insights
   - ECS Task Definition (1 vCPU, 2 GB RAM)
   - ECS Service (Fargate launch type)
   - Application Load Balancer
   - Security Groups (IP whitelisted)
   - IAM Task Roles (Bedrock, S3, Cognito)
   - CloudWatch Log Group
5. Outputs ALB URL and management commands

**Security Features:**
- ✅ IAM task roles (no credentials in environment)
- ✅ IP whitelisting via security groups
- ✅ Private networking with public ALB
- ✅ CloudWatch logging enabled

### Access the Application

The deployment script will output the ALB URL:

```
Application URL: http://sagemaker-migration-advisor-alb-xxxxxxxxx.us-east-1.elb.amazonaws.com
```

**Login:**
- Username: `admin@example.com`
- Password: `SecurePass123!` (or the password you set)

**Note:** Only accessible from your whitelisted IP address.

### ECS Fargate Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    User Browser (Your IP)                    │
└────────────────────────┬────────────────────────────────────┘
                         │ HTTP/HTTPS
                         ▼
┌─────────────────────────────────────────────────────────────┐
│         Application Load Balancer (Public Subnet)            │
│  Security Group: Allow from YOUR_IP/32 only                  │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│              ECS Fargate Tasks (Public Subnet)               │
│  Security Group: Allow from ALB only                         │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  Streamlit App Container                             │  │
│  │  - Cognito Authentication                            │  │
│  │  - Mode Selection (Lite/Regular)                     │  │
│  │  - WebSocket Support ✅                              │  │
│  │  - IAM Task Role (no credentials!) ✅                │  │
│  └──────────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────────┘
         │              │              │              │
         │              │              │              │
         ▼              ▼              ▼              ▼
    ┌────────┐    ┌─────────┐   ┌─────────┐   ┌──────────┐
    │ Amazon │    │ Amazon  │   │ Amazon  │   │  Amazon  │
    │Cognito │    │ Bedrock │   │   S3    │   │   ECR    │
    └────────┘    └─────────┘   └─────────┘   └──────────┘
```

### ECS Management Commands

#### View Service Status
```bash
aws ecs describe-services \
  --cluster sagemaker-migration-advisor-cluster \
  --services sagemaker-migration-advisor \
  --region us-east-1
```

#### View Application Logs
```bash
aws logs tail /ecs/sagemaker-migration-advisor --follow --region us-east-1
```

#### Update Task Count (Scale)
```bash
aws ecs update-service \
  --cluster sagemaker-migration-advisor-cluster \
  --service sagemaker-migration-advisor \
  --desired-count 2 \
  --region us-east-1
```

#### Force New Deployment (After Image Update)
```bash
aws ecs update-service \
  --cluster sagemaker-migration-advisor-cluster \
  --service sagemaker-migration-advisor \
  --force-new-deployment \
  --region us-east-1
```

---

## Common Management Tasks

### View Service Status (Lightsail)
```bash
aws lightsail get-container-services \
  --service-name sagemaker-migration-advisor \
  --region us-east-1
```

### View Application Logs (Lightsail)
```bash
aws lightsail get-container-log \
  --service-name sagemaker-migration-advisor \
  --container-name app \
  --region us-east-1
```

### Create Additional Users (Both Deployments)
```bash
cd deploy
./create-user.sh user@example.com "User Name" "UserPass123!" "Users"
```

### Reset User Password (Both Deployments)
```bash
cd deploy
./reset-password.sh user@example.com "NewPassword123!"
```

---

## Redeployment After Code Changes

### For Lightsail:

```bash
# 1. Build new image and push to ECR
cd deploy
./codebuild-deploy.sh

# 2. Deploy to Lightsail (pulls from ECR)
./codebuild-lightsail.sh

# 3. If needed, update credentials
./add-credentials-to-lightsail.sh
```

### For ECS Fargate:

```bash
# 1. Build new image and push to ECR
cd deploy
./codebuild-deploy.sh

# 2. Force new deployment (pulls latest image)
aws ecs update-service \
  --cluster sagemaker-migration-advisor-cluster \
  --service sagemaker-migration-advisor \
  --force-new-deployment \
  --region us-east-1
```

---

## Switching Between Deployments

You can have both deployments running simultaneously or switch between them:

### Deploy Both:
```bash
# Deploy shared infrastructure first
cd deploy/terraform
terraform apply

# Build and push image to ECR
cd ..
./codebuild-deploy.sh

# Deploy Lightsail
./codebuild-lightsail.sh
./add-credentials-to-lightsail.sh

# Deploy ECS Fargate
./deploy-ecs.sh
```

### Deploy Only One:

**Lightsail Only:**
```bash
cd deploy/terraform
terraform apply  # Creates shared resources
cd ..
./codebuild-deploy.sh  # Build and push to ECR
./codebuild-lightsail.sh  # Deploy to Lightsail
./add-credentials-to-lightsail.sh  # Add credentials
```

**ECS Fargate Only:**
```bash
cd deploy/terraform
terraform apply  # Creates shared resources
cd ..
./codebuild-deploy.sh  # Build and push to ECR
./deploy-ecs.sh  # Deploy to ECS
```

---

## Troubleshooting

### Application Not Loading (Lightsail)
1. Check service status
2. View container logs
3. Verify health check endpoint: `/_stcore/health`

### Application Not Loading (ECS)
1. Check ECS service status
2. View CloudWatch logs
3. Check ALB target health
4. Verify security group allows your IP

### Authentication Issues (Both)
1. Verify Cognito credentials in `.env`
2. Check user exists in Cognito
3. Reset password if needed

### Bedrock Access Denied (Lightsail)
1. Verify IAM user has Bedrock permissions
2. Check credentials are in Lightsail environment
3. Verify Bedrock model access in your region

### Bedrock Access Denied (ECS)
1. Verify IAM task role has Bedrock permissions
2. Check task role is attached to task definition
3. Verify Bedrock model access in your region

### IP Access Denied (ECS)
1. Verify your current IP matches the whitelisted IP
2. Update security group if IP changed:
```bash
cd deploy/terraform
# Edit terraform.tfvars with new IP
terraform apply
```

### WebSocket Connection Issues
- Both Lightsail and ECS support WebSockets
- Check browser console for errors
- Verify HTTPS/HTTP connection

---

## Security Considerations

### Lightsail Deployment
- ⚠️ AWS credentials stored in environment variables
- ⚠️ Not ideal for production use
- ✅ Credentials are scoped to specific resources
- ✅ IAM user has minimal permissions
- ❌ No IP whitelisting support

### ECS Fargate Deployment
- ✅ IAM task roles (no credentials stored)
- ✅ IP whitelisting via security groups
- ✅ Private networking with public ALB
- ✅ CloudWatch logging enabled
- ✅ Production-ready security posture

### Additional Recommendations
1. **Enable CloudTrail** for audit logging
2. **Set up CloudWatch alarms** for monitoring
3. **Rotate credentials** (Lightsail only) every 90 days
4. **Use HTTPS** with ACM certificate (both deployments)
5. **Enable VPC Flow Logs** (ECS only)

---

## Cost Breakdown

### Lightsail Deployment
| Service | Cost |
|---------|------|
| Lightsail Container (medium) | ~$40/month |
| Cognito | Free tier (up to 50K MAUs) |
| ECR | ~$0.10/GB/month |
| S3 | ~$0.023/GB/month |
| CodeBuild | ~$0.005/min (pay per build) |
| Bedrock | Pay per token usage |
| **Total** | **~$40-50/month + usage** |

### ECS Fargate Deployment
| Service | Cost |
|---------|------|
| ECS Fargate (1 task, 1 vCPU, 2 GB) | ~$30/month |
| Application Load Balancer | ~$16/month |
| CloudWatch Logs | ~$0.50/GB ingested |
| Cognito | Free tier (up to 50K MAUs) |
| ECR | ~$0.10/GB/month |
| S3 | ~$0.023/GB/month |
| Bedrock | Pay per token usage |
| **Total** | **~$46-55/month + usage** |

---

## Cleanup

### Delete Lightsail Deployment
```bash
# 1. Delete Lightsail service
aws lightsail delete-container-service \
  --service-name sagemaker-migration-advisor \
  --region us-east-1

# 2. Delete IAM user
aws iam delete-access-key \
  --user-name sagemaker-migration-advisor-app-user \
  --access-key-id <ACCESS_KEY_ID>
aws iam delete-user-policy \
  --user-name sagemaker-migration-advisor-app-user \
  --policy-name BedrockAndS3Access
aws iam delete-user \
  --user-name sagemaker-migration-advisor-app-user

# 3. Delete CodeBuild project
aws codebuild delete-project \
  --name sagemaker-migration-advisor-lightsail-pusher \
  --region us-east-1
```

### Delete ECS Deployment
```bash
cd deploy/terraform

# Delete ECS resources only (keep shared resources)
terraform destroy \
  -target=aws_ecs_service.migration_advisor \
  -target=aws_ecs_task_definition.migration_advisor \
  -target=aws_ecs_cluster.migration_advisor \
  -target=aws_lb.migration_advisor \
  -target=aws_lb_target_group.migration_advisor \
  -target=aws_lb_listener.http \
  -target=aws_security_group.alb \
  -target=aws_security_group.ecs_tasks \
  -target=aws_iam_role.ecs_task \
  -target=aws_iam_role.ecs_task_execution \
  -target=aws_cloudwatch_log_group.ecs_tasks
```

### Delete All Resources (Both Deployments)
```bash
# Delete Lightsail (if exists)
aws lightsail delete-container-service \
  --service-name sagemaker-migration-advisor \
  --region us-east-1

# Delete all Terraform resources
cd deploy/terraform
terraform destroy
```

---

## Support

For issues or questions:
1. Check application logs (Lightsail or CloudWatch)
2. Review security group rules (ECS)
3. Verify IAM permissions
4. Check Bedrock model availability in your region

---

## Next Steps

### After Lightsail Deployment:
1. ✅ Test the application with both Lite and Regular modes
2. ✅ Create additional Cognito users as needed
3. ✅ Monitor usage and costs
4. ⚠️ Consider migrating to ECS Fargate for production

### After ECS Deployment:
1. ✅ Test the application with both Lite and Regular modes
2. ✅ Create additional Cognito users as needed
3. ✅ Set up CloudWatch alarms for monitoring
4. ✅ Configure HTTPS with ACM certificate
5. ✅ Enable auto-scaling if needed
