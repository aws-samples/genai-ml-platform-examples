#!/bin/bash
set -e

# Build locally and push to Lightsail
# REQUIRES: Docker Desktop signed in

echo "🚀 Building locally and pushing to Lightsail"
echo "============================================="

SERVICE_NAME="sagemaker-migration-advisor"
IMAGE_NAME="app"
AWS_REGION=${AWS_REGION:-us-east-1}

# Step 1: Build Docker image locally
echo "1️⃣  Building Docker image locally..."
docker build -t $SERVICE_NAME:latest .

# Step 2: Test the image locally (optional)
echo "2️⃣  Testing image locally..."
echo "   Starting container on port 8501..."
CONTAINER_ID=$(docker run -d -p 8501:8501 \
    -e AWS_REGION=us-east-1 \
    -e COGNITO_USER_POOL_ID=us-east-1_HGVMNNSUT \
    -e COGNITO_CLIENT_ID=5q3usglon7vdtpb856khjgv3ik \
    -e COGNITO_CLIENT_SECRET=1sc3873rs6gs04pp3avmehlmqbo1p1bbqltqo2e6spk5r7o5gru4 \
    -e S3_BUCKET=sagemaker-migration-advisor-artifacts-YOUR_AWS_ACCOUNT_ID \
    $SERVICE_NAME:latest)

echo "   Container started: $CONTAINER_ID"
echo "   Waiting 10 seconds for app to start..."
sleep 10

# Test health endpoint
echo "   Testing health endpoint..."
if curl -f http://localhost:8501/_stcore/health; then
    echo "   ✅ Health check passed!"
else
    echo "   ❌ Health check failed"
    docker logs $CONTAINER_ID
fi

# Stop test container
echo "   Stopping test container..."
docker stop $CONTAINER_ID
docker rm $CONTAINER_ID

# Step 3: Push to Lightsail
echo "3️⃣  Pushing to Lightsail..."

# Use AWS CLI to push (this handles authentication automatically)
aws lightsail push-container-image \
    --service-name $SERVICE_NAME \
    --label $IMAGE_NAME \
    --image $SERVICE_NAME:latest \
    --region $AWS_REGION

echo ""
echo "✅ Image pushed to Lightsail!"
echo ""
echo "📝 The output above shows the image reference like:"
echo "   :$SERVICE_NAME.$IMAGE_NAME.X"
echo ""
echo "📝 Next: Deploy the image to Lightsail"
echo "   Update the deployment with the image reference shown above"
echo ""
