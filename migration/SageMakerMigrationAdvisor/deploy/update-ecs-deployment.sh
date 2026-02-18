#!/bin/bash

# Update ECS Fargate Deployment with Latest Code
# This script rebuilds the Docker image and updates the ECS service

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}ECS Deployment Update Script${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

# Get current directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Check if AWS CLI is installed
if ! command -v aws &> /dev/null; then
    echo -e "${RED}Error: AWS CLI is not installed${NC}"
    exit 1
fi

# Get AWS account ID and region
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
AWS_REGION=$(aws configure get region || echo "us-east-1")

echo -e "${BLUE}AWS Account ID:${NC} $AWS_ACCOUNT_ID"
echo -e "${BLUE}AWS Region:${NC} $AWS_REGION"
echo ""

# Configuration
ECR_REPO_NAME="sagemaker-migration-advisor"
ECR_REPO_URI="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${ECR_REPO_NAME}"
ECS_CLUSTER_NAME="sagemaker-migration-advisor-cluster"
ECS_SERVICE_NAME="sagemaker-migration-advisor-service"

echo -e "${YELLOW}Step 1: Building and Pushing New Docker Image${NC}"
echo "=================================================="
echo ""

# Check if ECR repository exists
echo -e "${BLUE}Checking ECR repository...${NC}"
if ! aws ecr describe-repositories --repository-names $ECR_REPO_NAME --region $AWS_REGION &>/dev/null; then
    echo -e "${YELLOW}Creating ECR repository...${NC}"
    aws ecr create-repository --repository-name $ECR_REPO_NAME --region $AWS_REGION
    echo -e "${GREEN}✓ ECR repository created${NC}"
else
    echo -e "${GREEN}✓ ECR repository exists${NC}"
fi
echo ""

# Login to ECR
echo -e "${BLUE}Logging in to Amazon ECR...${NC}"
aws ecr get-login-password --region $AWS_REGION | docker login --username AWS --password-stdin $ECR_REPO_URI
echo -e "${GREEN}✓ Logged in to ECR${NC}"
echo ""

# Build Docker image
echo -e "${BLUE}Building Docker image...${NC}"
cd "$PROJECT_ROOT"
IMAGE_TAG=$(date +%Y%m%d-%H%M%S)

docker build -t $ECR_REPO_URI:latest -t $ECR_REPO_URI:$IMAGE_TAG .

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Docker image built successfully${NC}"
else
    echo -e "${RED}✗ Docker build failed${NC}"
    exit 1
fi
echo ""

# Push to ECR
echo -e "${BLUE}Pushing Docker image to ECR...${NC}"
docker push $ECR_REPO_URI:latest
docker push $ECR_REPO_URI:$IMAGE_TAG

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Docker image pushed successfully${NC}"
    echo -e "${GREEN}  Latest: $ECR_REPO_URI:latest${NC}"
    echo -e "${GREEN}  Tagged: $ECR_REPO_URI:$IMAGE_TAG${NC}"
else
    echo -e "${RED}✗ Docker push failed${NC}"
    exit 1
fi
echo ""

echo -e "${YELLOW}Step 2: Updating ECS Service${NC}"
echo "=================================================="
echo ""

# Check if ECS cluster exists
echo -e "${BLUE}Checking ECS cluster...${NC}"
if ! aws ecs describe-clusters --clusters $ECS_CLUSTER_NAME --region $AWS_REGION --query 'clusters[0].status' --output text 2>/dev/null | grep -q "ACTIVE"; then
    echo -e "${RED}Error: ECS cluster '$ECS_CLUSTER_NAME' not found or not active${NC}"
    echo -e "${YELLOW}Please deploy the infrastructure first:${NC}"
    echo -e "  cd $SCRIPT_DIR"
    echo -e "  ./deploy-ecs.sh"
    exit 1
fi
echo -e "${GREEN}✓ ECS cluster is active${NC}"
echo ""

# Check if ECS service exists
echo -e "${BLUE}Checking ECS service...${NC}"
if ! aws ecs describe-services --cluster $ECS_CLUSTER_NAME --services $ECS_SERVICE_NAME --region $AWS_REGION --query 'services[0].status' --output text 2>/dev/null | grep -q "ACTIVE"; then
    echo -e "${RED}Error: ECS service '$ECS_SERVICE_NAME' not found or not active${NC}"
    echo -e "${YELLOW}Please deploy the infrastructure first:${NC}"
    echo -e "  cd $SCRIPT_DIR"
    echo -e "  ./deploy-ecs.sh"
    exit 1
fi
echo -e "${GREEN}✓ ECS service is active${NC}"
echo ""

# Get current task definition
echo -e "${BLUE}Getting current task definition...${NC}"
TASK_DEFINITION_ARN=$(aws ecs describe-services \
    --cluster $ECS_CLUSTER_NAME \
    --services $ECS_SERVICE_NAME \
    --region $AWS_REGION \
    --query 'services[0].taskDefinition' \
    --output text)

if [ -z "$TASK_DEFINITION_ARN" ]; then
    echo -e "${RED}Error: Could not get task definition${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Current task definition: $TASK_DEFINITION_ARN${NC}"
echo ""

# Force new deployment
echo -e "${BLUE}Forcing new deployment with updated image...${NC}"
aws ecs update-service \
    --cluster $ECS_CLUSTER_NAME \
    --service $ECS_SERVICE_NAME \
    --force-new-deployment \
    --region $AWS_REGION \
    > /dev/null

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ ECS service update initiated${NC}"
else
    echo -e "${RED}✗ ECS service update failed${NC}"
    exit 1
fi
echo ""

echo -e "${YELLOW}Step 3: Monitoring Deployment${NC}"
echo "=================================================="
echo ""

echo -e "${BLUE}Waiting for deployment to complete...${NC}"
echo -e "${YELLOW}This may take 3-5 minutes${NC}"
echo ""

# Monitor deployment
DEPLOYMENT_START=$(date +%s)
MAX_WAIT=600  # 10 minutes

while true; do
    # Get deployment status
    DEPLOYMENT_STATUS=$(aws ecs describe-services \
        --cluster $ECS_CLUSTER_NAME \
        --services $ECS_SERVICE_NAME \
        --region $AWS_REGION \
        --query 'services[0].deployments[0]' \
        --output json)
    
    RUNNING_COUNT=$(echo $DEPLOYMENT_STATUS | jq -r '.runningCount')
    DESIRED_COUNT=$(echo $DEPLOYMENT_STATUS | jq -r '.desiredCount')
    STATUS=$(echo $DEPLOYMENT_STATUS | jq -r '.rolloutState')
    
    CURRENT_TIME=$(date +%s)
    ELAPSED=$((CURRENT_TIME - DEPLOYMENT_START))
    
    echo -e "${BLUE}Status: $STATUS | Running: $RUNNING_COUNT/$DESIRED_COUNT | Elapsed: ${ELAPSED}s${NC}"
    
    # Check if deployment is complete
    if [ "$STATUS" = "COMPLETED" ] && [ "$RUNNING_COUNT" = "$DESIRED_COUNT" ]; then
        echo ""
        echo -e "${GREEN}✓ Deployment completed successfully!${NC}"
        break
    fi
    
    # Check for failed deployment
    if [ "$STATUS" = "FAILED" ]; then
        echo ""
        echo -e "${RED}✗ Deployment failed${NC}"
        echo ""
        echo -e "${YELLOW}Check service events:${NC}"
        aws ecs describe-services \
            --cluster $ECS_CLUSTER_NAME \
            --services $ECS_SERVICE_NAME \
            --region $AWS_REGION \
            --query 'services[0].events[0:5]' \
            --output table
        exit 1
    fi
    
    # Check timeout
    if [ $ELAPSED -gt $MAX_WAIT ]; then
        echo ""
        echo -e "${RED}✗ Deployment timeout (${MAX_WAIT}s)${NC}"
        echo ""
        echo -e "${YELLOW}Check service status:${NC}"
        aws ecs describe-services \
            --cluster $ECS_CLUSTER_NAME \
            --services $ECS_SERVICE_NAME \
            --region $AWS_REGION \
            --query 'services[0].events[0:5]' \
            --output table
        exit 1
    fi
    
    sleep 15
done

echo ""
echo -e "${YELLOW}Step 4: Verification${NC}"
echo "=================================================="
echo ""

# Get ALB URL
echo -e "${BLUE}Getting application URL...${NC}"
cd "$SCRIPT_DIR/terraform"
ALB_URL=$(terraform output -raw alb_url 2>/dev/null || echo "")
ALB_HTTPS_URL=$(terraform output -raw alb_https_url 2>/dev/null || echo "")

if [ -n "$ALB_URL" ]; then
    echo -e "${GREEN}✓ Application URL: $ALB_URL${NC}"
    if [ -n "$ALB_HTTPS_URL" ] && [[ "$ALB_HTTPS_URL" == https://* ]]; then
        echo -e "${GREEN}✓ HTTPS URL: $ALB_HTTPS_URL${NC}"
    fi
else
    echo -e "${YELLOW}Could not retrieve ALB URL from Terraform${NC}"
fi
echo ""

# Get task information
echo -e "${BLUE}Current running tasks:${NC}"
TASK_ARNS=$(aws ecs list-tasks \
    --cluster $ECS_CLUSTER_NAME \
    --service-name $ECS_SERVICE_NAME \
    --region $AWS_REGION \
    --query 'taskArns' \
    --output text)

if [ -n "$TASK_ARNS" ]; then
    for TASK_ARN in $TASK_ARNS; do
        TASK_ID=$(echo $TASK_ARN | awk -F'/' '{print $NF}')
        echo -e "  ${GREEN}✓${NC} Task: $TASK_ID"
    done
else
    echo -e "  ${YELLOW}No tasks found${NC}"
fi
echo ""

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Deployment Update Complete!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

echo -e "${YELLOW}Summary:${NC}"
echo -e "  ${GREEN}✓${NC} Docker image built and pushed"
echo -e "  ${GREEN}✓${NC} ECS service updated"
echo -e "  ${GREEN}✓${NC} New tasks deployed"
echo ""

echo -e "${YELLOW}Useful Commands:${NC}"
echo ""
echo -e "${BLUE}View service status:${NC}"
echo "  aws ecs describe-services \\"
echo "    --cluster $ECS_CLUSTER_NAME \\"
echo "    --services $ECS_SERVICE_NAME \\"
echo "    --region $AWS_REGION"
echo ""

echo -e "${BLUE}View logs:${NC}"
echo "  aws logs tail /ecs/sagemaker-migration-advisor --follow --region $AWS_REGION"
echo ""

echo -e "${BLUE}View tasks:${NC}"
echo "  aws ecs list-tasks \\"
echo "    --cluster $ECS_CLUSTER_NAME \\"
echo "    --service-name $ECS_SERVICE_NAME \\"
echo "    --region $AWS_REGION"
echo ""

echo -e "${GREEN}✅ Update completed successfully!${NC}"
