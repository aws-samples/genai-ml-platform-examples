# Deployment Scripts

This directory contains deployment scripts and infrastructure code for the SageMaker Migration Advisor.

---

## Deployment Options

Choose the deployment that fits your needs:

| Option | Best For | Security | IP Whitelisting | Cost |
|--------|----------|----------|-----------------|------|
| **Lightsail** | Dev/Test | IAM user credentials | ❌ No | ~$40/mo |
| **ECS Fargate** | Production | IAM task roles ✅ | ✅ Yes | ~$47/mo |

---

## Quick Start

### Option A: Lightsail (Simple)

```bash
# 1. Deploy infrastructure
cd terraform
terraform init && terraform apply

# 2. Create user
cd .. && source ../.env
./create-user.sh admin@example.com "Admin" "SecurePass123!" "Admins"

# 3. Deploy to Lightsail
./codebuild-lightsail.sh
./add-credentials-to-lightsail.sh
```

### Option B: ECS Fargate (Production) ⭐ NEW

```bash
# 1. Deploy infrastructure
cd terraform
terraform init && terraform apply

# 2. Create user
cd .. && source ../.env
./create-user.sh admin@example.com "Admin" "SecurePass123!" "Admins"

# 3. Deploy to ECS
./deploy-ecs.sh
```

---

## Directory Structure

```
deploy/
├── terraform/              # Infrastructure as Code
│   ├── main.tf            # Shared resources (ECR, Cognito, S3)
│   ├── ecs-fargate.tf     # ECS Fargate deployment ⭐ NEW
│   ├── variables.tf       # Common variables
│   └── ecs-variables.tf   # ECS-specific variables ⭐ NEW
├── codebuild-lightsail.sh # Deploy to Lightsail
├── deploy-ecs.sh          # Deploy to ECS Fargate ⭐ NEW
├── add-credentials-to-lightsail.sh # Add Bedrock permissions (Lightsail only)
├── setup-cognito.sh       # Setup Cognito (alternative to Terraform)
├── create-user.sh         # Create Cognito user
├── delete-user.sh         # Delete Cognito user
├── reset-password.sh      # Reset user password
└── list-users.sh          # List all Cognito users
```

---

## Deployment Scripts

### Infrastructure Management

#### `terraform/`
Terraform code for infrastructure.

**Shared Resources (both deployments):**
- ECR repository
- Cognito User Pool
- S3 bucket

**ECS-specific Resources:**
- ECS Cluster
- ECS Service (Fargate)
- Application Load Balancer
- Security Groups (IP whitelisted)
- IAM Task Roles

**Usage:**
```bash
cd terraform
terraform init
terraform plan
terraform apply
```

### Lightsail Deployment

#### `codebuild-lightsail.sh`
Deploys application to AWS Lightsail Container Service.

**What it does:**
1. Creates Lightsail service (if not exists)
2. Enables ECR access
3. Creates CodeBuild project
4. Builds and pushes Docker image
5. Deploys to Lightsail

**Usage:**
```bash
./codebuild-lightsail.sh
```

#### `add-credentials-to-lightsail.sh`
Adds AWS credentials to Lightsail for Bedrock access.

**What it does:**
1. Creates IAM user
2. Attaches Bedrock/S3 policies
3. Creates access key
4. Updates Lightsail environment

**Usage:**
```bash
./add-credentials-to-lightsail.sh
```

### ECS Fargate Deployment ⭐ NEW

#### `deploy-ecs.sh`
Deploys application to ECS Fargate with ALB and IP whitelisting.

**What it does:**
1. Prompts for your IP address (or auto-detects)
2. Prompts for HTTPS configuration (optional)
3. Verifies Docker image exists in ECR
4. Creates terraform.tfvars with your settings
5. Deploys ECS infrastructure:
   - ECS Cluster with Container Insights
   - ECS Service (Fargate, 1 vCPU, 2 GB RAM)
   - Application Load Balancer (HTTP/HTTPS)
   - Security Groups (IP whitelisted)
   - IAM Task Roles (Bedrock, S3, Cognito)
   - CloudWatch Log Group
   - Route53 DNS (optional)
6. Outputs ALB URL and management commands

**Usage:**
```bash
./deploy-ecs.sh
```

**HTTPS Support:**
The deployment script now supports HTTPS with ACM certificates. During deployment, you'll be prompted:
- Enable HTTPS? (yes/no)
- Certificate ARN (if yes)
- Custom domain name (optional)

For detailed HTTPS setup instructions, see: `terraform/HTTPS_SETUP_GUIDE.md`

**Security Features:**
- ✅ IAM task roles (no credentials stored)
- ✅ IP whitelisting via security groups
- ✅ HTTPS support with ACM certificates
- ✅ HTTP to HTTPS redirect (when HTTPS enabled)
- ✅ Private networking with public ALB
- ✅ CloudWatch logging enabled

### User Management Scripts

#### `create-user.sh`
Creates a new Cognito user.

**Usage:**
```bash
./create-user.sh <email> <name> [password] [group]
```

**Example:**
```bash
./create-user.sh user@example.com "John Doe" "SecurePass123!" "Users"
```

#### `delete-user.sh`
Deletes a Cognito user.

**Usage:**
```bash
./delete-user.sh <email>
```

#### `reset-password.sh`
Resets a user's password.

**Usage:**
```bash
./reset-password.sh <email> <new-password>
```

#### `list-users.sh`
Lists all Cognito users.

**Usage:**
```bash
./list-users.sh
```

---

## Environment Variables

Required environment variables (set in `../.env`):

```bash
AWS_REGION=us-east-1
COGNITO_USER_POOL_ID=us-east-1_xxxxxxxxx
COGNITO_CLIENT_ID=xxxxxxxxxxxxxxxxxxxxxxxxxx
COGNITO_CLIENT_SECRET=xxxxxxxxxxxxxxxxxxxxxxxxxx
S3_BUCKET=sagemaker-migration-advisor-artifacts-xxxxxxxxxxxx
```

---

## Deployment Flows

### Lightsail Flow

```
┌─────────────────────────────────────────────────────────────┐
│ 1. terraform apply                                           │
│    Creates: ECR, Cognito, S3                                 │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│ 2. create-user.sh                                            │
│    Creates: Cognito test user                                │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│ 3. codebuild-lightsail.sh                                    │
│    - Builds Docker image                                     │
│    - Pushes to ECR                                           │
│    - Deploys to Lightsail                                    │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│ 4. add-credentials-to-lightsail.sh                           │
│    - Creates IAM user                                        │
│    - Adds Bedrock/S3 permissions                             │
│    - Updates Lightsail environment                           │
└─────────────────────────────────────────────────────────────┘
```

### ECS Fargate Flow ⭐ NEW

```
┌─────────────────────────────────────────────────────────────┐
│ 1. terraform apply                                           │
│    Creates: ECR, Cognito, S3                                 │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│ 2. create-user.sh                                            │
│    Creates: Cognito test user                                │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│ 3. codebuild-lightsail.sh                                    │
│    - Builds Docker image                                     │
│    - Pushes to ECR                                           │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│ 4. deploy-ecs.sh                                             │
│    - Prompts for IP address                                  │
│    - Creates ECS cluster, service, ALB                       │
│    - Configures IAM task roles                               │
│    - Sets up IP whitelisting                                 │
│    - Outputs ALB URL                                         │
└─────────────────────────────────────────────────────────────┘
```

---

## Management Commands

### Lightsail

**View service status:**
```bash
aws lightsail get-container-services \
  --service-name sagemaker-migration-advisor \
  --region us-east-1
```

**View logs:**
```bash
aws lightsail get-container-log \
  --service-name sagemaker-migration-advisor \
  --container-name app \
  --region us-east-1
```

### ECS Fargate

**View service status:**
```bash
aws ecs describe-services \
  --cluster sagemaker-migration-advisor-cluster \
  --services sagemaker-migration-advisor \
  --region us-east-1
```

**View logs (live):**
```bash
aws logs tail /ecs/sagemaker-migration-advisor --follow --region us-east-1
```

**Scale service:**
```bash
aws ecs update-service \
  --cluster sagemaker-migration-advisor-cluster \
  --service sagemaker-migration-advisor \
  --desired-count 2 \
  --region us-east-1
```

**Force new deployment:**
```bash
aws ecs update-service \
  --cluster sagemaker-migration-advisor-cluster \
  --service sagemaker-migration-advisor \
  --force-new-deployment \
  --region us-east-1
```

---

## Troubleshooting

### Terraform Issues

**Error: Resource already exists**
```bash
cd terraform
terraform import <resource_type>.<resource_name> <resource_id>
```

**Error: State lock**
```bash
cd terraform
terraform force-unlock <lock-id>
```

### Lightsail Issues

**Service not starting**
```bash
aws lightsail get-container-services \
  --service-name sagemaker-migration-advisor \
  --region us-east-1
```

**View logs**
```bash
aws lightsail get-container-log \
  --service-name sagemaker-migration-advisor \
  --container-name app \
  --region us-east-1
```

### ECS Issues

**Service not starting**
```bash
# Check service events
aws ecs describe-services \
  --cluster sagemaker-migration-advisor-cluster \
  --services sagemaker-migration-advisor \
  --region us-east-1 \
  --query 'services[0].events[0:5]'
```

**Can't access ALB**
```bash
# Check your current IP
curl https://checkip.amazonaws.com

# Update security group if needed
cd terraform
# Edit terraform.tfvars with new IP
terraform apply
```

### Cognito Issues

**User already exists**
```bash
./delete-user.sh user@example.com
./create-user.sh user@example.com "User Name" "NewPass123!" "Users"
```

**Password doesn't meet requirements**
- Minimum 8 characters
- Must include: uppercase, lowercase, number, symbol

---

## Cleanup

### Delete Lightsail Deployment
```bash
aws lightsail delete-container-service \
  --service-name sagemaker-migration-advisor \
  --region us-east-1

# Delete IAM user
aws iam delete-access-key \
  --user-name sagemaker-migration-advisor-app-user \
  --access-key-id <ACCESS_KEY_ID>
aws iam delete-user-policy \
  --user-name sagemaker-migration-advisor-app-user \
  --policy-name BedrockAndS3Access
aws iam delete-user \
  --user-name sagemaker-migration-advisor-app-user
```

### Delete ECS Deployment
```bash
cd terraform

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

### Delete All Resources
```bash
cd terraform
terraform destroy
```

---

## See Also

- `../DEPLOYMENT_GUIDE.md` - Complete deployment guide (both options)
- `../ECS_DEPLOYMENT_QUICKSTART.md` - ECS quick start guide ⭐ NEW
- `../LIGHTSAIL_DEPLOYMENT_STEPS.md` - Detailed Lightsail steps
- `../SECURITY_CONSIDERATIONS.md` - Security analysis
- `../PERMISSIONS_AND_USERS_SUMMARY.md` - IAM details
