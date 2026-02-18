#!/bin/bash

# Deploy SageMaker Migration Advisor to ECS Fargate with ALB
# This script deploys the application to ECS Fargate with IP whitelisting

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}SageMaker Migration Advisor - ECS Deployment${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

# Get current directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
TERRAFORM_DIR="$SCRIPT_DIR/terraform"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Check if AWS CLI is installed
if ! command -v aws &> /dev/null; then
    echo -e "${RED}Error: AWS CLI is not installed${NC}"
    exit 1
fi

# Check if Terraform is installed
if ! command -v terraform &> /dev/null; then
    echo -e "${RED}Error: Terraform is not installed${NC}"
    exit 1
fi

# Get AWS account ID and region
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
AWS_REGION=$(aws configure get region || echo "us-east-1")

echo -e "${YELLOW}AWS Account ID:${NC} $AWS_ACCOUNT_ID"
echo -e "${YELLOW}AWS Region:${NC} $AWS_REGION"
echo ""

# Prompt for IP address
echo -e "${YELLOW}Enter your IP address for ALB access restriction:${NC}"
echo -e "${YELLOW}(Format: x.x.x.x/32 or leave empty to get current IP)${NC}"
read -p "IP Address: " USER_IP

if [ -z "$USER_IP" ]; then
    echo -e "${YELLOW}Detecting your current IP address...${NC}"
    USER_IP=$(curl -s https://checkip.amazonaws.com)
    if [ -z "$USER_IP" ]; then
        echo -e "${RED}Error: Could not detect IP address${NC}"
        exit 1
    fi
    USER_IP="${USER_IP}/32"
    echo -e "${GREEN}Detected IP: $USER_IP${NC}"
else
    # Add /32 if not already in CIDR notation
    if [[ ! "$USER_IP" =~ / ]]; then
        USER_IP="${USER_IP}/32"
        echo -e "${GREEN}Using IP: $USER_IP${NC}"
    fi
fi

echo ""

# Prompt for HTTPS configuration
echo -e "${YELLOW}HTTPS Configuration (Optional):${NC}"
echo -e "${YELLOW}Do you want to enable HTTPS with an ACM certificate?${NC}"
read -p "Enable HTTPS? (yes/no): " ENABLE_HTTPS

CERT_ARN=""
DOMAIN_NAME=""

if [ "$ENABLE_HTTPS" = "yes" ]; then
    echo ""
    echo -e "${YELLOW}Enter your ACM Certificate ARN:${NC}"
    echo -e "${YELLOW}(Format: arn:aws:acm:region:account:certificate/id)${NC}"
    read -p "Certificate ARN: " CERT_ARN
    
    if [ -z "$CERT_ARN" ]; then
        echo -e "${RED}Error: Certificate ARN is required for HTTPS${NC}"
        exit 1
    fi
    
    echo ""
    echo -e "${YELLOW}Enter your custom domain name (optional):${NC}"
    echo -e "${YELLOW}(Leave empty to use ALB DNS name)${NC}"
    read -p "Domain Name: " DOMAIN_NAME
    
    echo -e "${GREEN}✓ HTTPS will be enabled${NC}"
else
    echo -e "${YELLOW}HTTPS not enabled - using HTTP only${NC}"
fi

echo ""

# Check if ECR image exists
ECR_REPO_NAME="sagemaker-migration-advisor"
ECR_REPO_URI="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${ECR_REPO_NAME}"

echo -e "${YELLOW}Checking if Docker image exists in ECR...${NC}"
if ! aws ecr describe-images \
    --repository-name "$ECR_REPO_NAME" \
    --image-ids imageTag=latest \
    --region "$AWS_REGION" &> /dev/null; then
    echo -e "${RED}Error: Docker image not found in ECR${NC}"
    echo -e "${YELLOW}Please build and push the image first:${NC}"
    echo -e "  cd $SCRIPT_DIR"
    echo -e "  ./codebuild-lightsail.sh"
    exit 1
fi

echo -e "${GREEN}✓ Docker image found in ECR${NC}"
echo ""

# Initialize Terraform if needed
cd "$TERRAFORM_DIR"
if [ ! -d ".terraform" ]; then
    echo -e "${YELLOW}Initializing Terraform...${NC}"
    terraform init
    echo ""
fi

# Create terraform.tfvars for ECS deployment
echo -e "${YELLOW}Creating terraform.tfvars for ECS deployment...${NC}"
cat > terraform.tfvars <<EOF
aws_region      = "$AWS_REGION"
my_ip_address   = "$USER_IP"
ecs_task_cpu    = "1024"
ecs_task_memory = "2048"
ecs_desired_count = 1
EOF

# Add HTTPS configuration if enabled
if [ -n "$CERT_ARN" ]; then
    echo "certificate_arn = \"$CERT_ARN\"" >> terraform.tfvars
fi

if [ -n "$DOMAIN_NAME" ]; then
    echo "domain_name     = \"$DOMAIN_NAME\"" >> terraform.tfvars
fi

echo -e "${GREEN}✓ terraform.tfvars created${NC}"
echo ""

# Plan Terraform changes
echo -e "${YELLOW}Planning Terraform changes...${NC}"
terraform plan -out=tfplan
echo ""

# Confirm deployment
echo -e "${YELLOW}Ready to deploy to ECS Fargate${NC}"
echo -e "${YELLOW}This will create:${NC}"
echo "  - ECS Cluster"
echo "  - ECS Service with Fargate tasks"
echo "  - Application Load Balancer"
echo "  - Security Groups (IP whitelisted)"
echo "  - IAM Roles (with Bedrock, S3, Cognito access)"
echo "  - CloudWatch Log Group"
echo ""
read -p "Continue with deployment? (yes/no): " CONFIRM

if [ "$CONFIRM" != "yes" ]; then
    echo -e "${YELLOW}Deployment cancelled${NC}"
    exit 0
fi

# Apply Terraform
echo ""
echo -e "${YELLOW}Deploying to ECS Fargate...${NC}"
terraform apply tfplan

# Get outputs
echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Deployment Complete!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

ALB_URL=$(terraform output -raw alb_url 2>/dev/null || echo "")
ALB_HTTPS_URL=$(terraform output -raw alb_https_url 2>/dev/null || echo "")
ECS_CLUSTER=$(terraform output -raw ecs_cluster_name 2>/dev/null || echo "")
ECS_SERVICE=$(terraform output -raw ecs_service_name 2>/dev/null || echo "")
LOG_GROUP=$(terraform output -raw cloudwatch_log_group 2>/dev/null || echo "")

if [ -n "$ALB_URL" ]; then
    echo -e "${GREEN}Application URL:${NC} $ALB_URL"
    if [ -n "$ALB_HTTPS_URL" ] && [[ "$ALB_HTTPS_URL" == https://* ]]; then
        echo -e "${GREEN}HTTPS URL:${NC} $ALB_HTTPS_URL"
    fi
    echo ""
    echo -e "${YELLOW}Note: It may take 2-3 minutes for the service to become healthy${NC}"
    echo ""
fi

if [ -n "$ECS_CLUSTER" ] && [ -n "$ECS_SERVICE" ]; then
    echo -e "${YELLOW}ECS Service:${NC}"
    echo "  Cluster: $ECS_CLUSTER"
    echo "  Service: $ECS_SERVICE"
    echo ""
    
    echo -e "${YELLOW}Check service status:${NC}"
    echo "  aws ecs describe-services \\"
    echo "    --cluster $ECS_CLUSTER \\"
    echo "    --services $ECS_SERVICE \\"
    echo "    --region $AWS_REGION"
    echo ""
fi

if [ -n "$LOG_GROUP" ]; then
    echo -e "${YELLOW}View logs:${NC}"
    echo "  aws logs tail $LOG_GROUP --follow --region $AWS_REGION"
    echo ""
fi

echo -e "${YELLOW}Access Restriction:${NC}"
echo "  Only accessible from: $USER_IP"
echo ""

echo -e "${GREEN}Deployment script completed successfully!${NC}"
