#!/bin/bash
set -e

# Build and Push Docker Image to ECR
# This script handles the Docker build and push process

echo "🐳 Building and Pushing Docker Image to ECR"
echo "============================================"

# Configuration
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
AWS_REGION=${AWS_REGION:-us-east-1}
ECR_REPO_NAME="sagemaker-migration-advisor"
ECR_REPO_URL="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${ECR_REPO_NAME}"

echo "📋 Configuration:"
echo "   AWS Account: $AWS_ACCOUNT_ID"
echo "   AWS Region: $AWS_REGION"
echo "   ECR Repository: $ECR_REPO_URL"
echo ""

# Step 1: Login to ECR
echo "1️⃣  Logging in to ECR..."
aws ecr get-login-password --region $AWS_REGION | docker login --username AWS --password-stdin $ECR_REPO_URL

# Step 2: Build Docker image
echo "2️⃣  Building Docker image..."
docker build -t $ECR_REPO_NAME:latest .

# Step 3: Tag image for ECR
echo "3️⃣  Tagging Docker image..."
docker tag $ECR_REPO_NAME:latest $ECR_REPO_URL:latest

# Step 4: Push image to ECR
echo "4️⃣  Pushing Docker image to ECR..."
docker push $ECR_REPO_URL:latest

echo ""
echo "✅ Docker image successfully pushed to ECR!"
echo "   Image: $ECR_REPO_URL:latest"
echo ""
