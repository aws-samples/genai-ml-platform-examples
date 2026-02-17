#!/bin/bash
set -e

# Setup Colima (Docker Desktop alternative) and build image
echo "🐳 Setting up Colima and building Docker image"
echo "==============================================="

# Step 1: Check if Colima is installed
if ! command -v colima &> /dev/null; then
    echo "1️⃣  Installing Colima..."
    brew install colima docker
else
    echo "1️⃣  Colima already installed"
fi

# Step 2: Start Colima if not running
echo "2️⃣  Starting Colima..."
if ! colima status &> /dev/null; then
    colima start --cpu 2 --memory 4
else
    echo "   Colima already running"
fi

# Step 3: Verify Docker works
echo "3️⃣  Verifying Docker..."
docker version

# Step 4: Build the image
echo "4️⃣  Building Docker image..."
docker build -t sagemaker-migration-advisor:latest .

# Step 5: Test the image
echo "5️⃣  Testing image..."
CONTAINER_ID=$(docker run -d -p 8501:8501 \
    -e AWS_REGION=us-east-1 \
    -e COGNITO_USER_POOL_ID=us-east-1_HGVMNNSUT \
    -e COGNITO_CLIENT_ID=5q3usglon7vdtpb856khjgv3ik \
    -e COGNITO_CLIENT_SECRET=1sc3873rs6gs04pp3avmehlmqbo1p1bbqltqo2e6spk5r7o5gru4 \
    -e S3_BUCKET=sagemaker-migration-advisor-artifacts-YOUR_AWS_ACCOUNT_ID \
    sagemaker-migration-advisor:latest)

echo "   Container started: $CONTAINER_ID"
echo "   Waiting 15 seconds for app to start..."
sleep 15

# Test health endpoint
echo "   Testing health endpoint..."
if curl -f http://localhost:8501/_stcore/health; then
    echo ""
    echo "   ✅ Health check passed!"
    echo "   🌐 Test the app at: http://localhost:8501"
    echo ""
    echo "   Press Enter to stop the test container and push to Lightsail..."
    read
else
    echo "   ❌ Health check failed"
    docker logs $CONTAINER_ID
fi

# Stop test container
echo "   Stopping test container..."
docker stop $CONTAINER_ID
docker rm $CONTAINER_ID

# Step 6: Push to Lightsail
echo "6️⃣  Pushing to Lightsail..."
SERVICE_NAME="sagemaker-migration-advisor"
IMAGE_NAME="app"
AWS_REGION=${AWS_REGION:-us-east-1}

aws lightsail push-container-image \
    --service-name $SERVICE_NAME \
    --label $IMAGE_NAME \
    --image sagemaker-migration-advisor:latest \
    --region $AWS_REGION

echo ""
echo "✅ Image pushed to Lightsail!"
echo ""
echo "📝 Copy the image reference from above (format: :$SERVICE_NAME.$IMAGE_NAME.X)"
echo "   Then deploy it to your Lightsail service"
echo ""
