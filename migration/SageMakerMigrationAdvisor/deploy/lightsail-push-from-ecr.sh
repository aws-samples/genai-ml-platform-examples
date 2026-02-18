#!/bin/bash
set -e

# Push image from ECR to Lightsail using AWS CLI
echo "🚀 Pushing image from ECR to Lightsail"
echo "======================================="

SERVICE_NAME="sagemaker-migration-advisor"
IMAGE_NAME="app"
AWS_REGION=${AWS_REGION:-us-east-1}
ECR_IMAGE="YOUR_AWS_ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com/sagemaker-migration-advisor:latest"

# Step 1: Pull image from ECR (using CodeBuild since Docker Desktop is blocked)
echo "1️⃣  Using AWS CLI to push image to Lightsail..."
echo "   Source: $ECR_IMAGE"
echo "   Target: Lightsail service $SERVICE_NAME"

# Use aws lightsail push-container-image command
# This command pulls from ECR and pushes to Lightsail in one step
aws lightsail push-container-image \
    --service-name $SERVICE_NAME \
    --label $IMAGE_NAME \
    --image $ECR_IMAGE \
    --region $AWS_REGION

echo ""
echo "✅ Image pushed to Lightsail!"
echo ""
echo "📝 Next: Deploy the image"
echo "   The image is now available as: :$SERVICE_NAME.$IMAGE_NAME.X"
echo "   (X is the version number shown above)"
echo ""
