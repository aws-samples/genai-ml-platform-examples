#!/bin/bash
set -e

# Pull image from ECR and push to Lightsail
echo "🚀 Pulling from ECR and pushing to Lightsail"
echo "============================================="

SERVICE_NAME="sagemaker-migration-advisor"
IMAGE_NAME="app"
AWS_REGION=${AWS_REGION:-us-east-1}
ECR_IMAGE="YOUR_AWS_ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com/sagemaker-migration-advisor:latest"

# Step 1: Login to ECR
echo "1️⃣  Logging in to ECR..."
aws ecr get-login-password --region $AWS_REGION | docker login --username AWS --password-stdin YOUR_AWS_ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com

# Step 2: Pull image from ECR
echo "2️⃣  Pulling image from ECR..."
docker pull $ECR_IMAGE

# Step 3: Tag for Lightsail
echo "3️⃣  Tagging for Lightsail..."
docker tag $ECR_IMAGE $SERVICE_NAME:latest

# Step 4: Push to Lightsail
echo "4️⃣  Pushing to Lightsail..."
aws lightsail push-container-image \
    --service-name $SERVICE_NAME \
    --label $IMAGE_NAME \
    --image $SERVICE_NAME:latest \
    --region $AWS_REGION

echo ""
echo "✅ Image pushed to Lightsail!"
echo ""
echo "📝 Copy the image reference from above (format: :$SERVICE_NAME.$IMAGE_NAME.X)"
echo ""
