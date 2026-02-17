#!/bin/bash
set -e

# Push Docker image to Lightsail
echo "🐳 Pushing Docker image to Lightsail"
echo "===================================="

SERVICE_NAME="sagemaker-migration-advisor"
IMAGE_NAME="app"
AWS_REGION=${AWS_REGION:-us-east-1}

# Step 1: Get Lightsail registry credentials
echo "1️⃣  Getting Lightsail registry credentials..."
REGISTRY_CREDS=$(aws lightsail create-container-service-registry-login --region $AWS_REGION)
REGISTRY_URL=$(echo $REGISTRY_CREDS | jq -r '.registryLogin.registry')
USERNAME=$(echo $REGISTRY_CREDS | jq -r '.registryLogin.username')
PASSWORD=$(echo $REGISTRY_CREDS | jq -r '.registryLogin.password')

echo "   Registry: $REGISTRY_URL"

# Step 2: Login to Lightsail registry
echo "2️⃣  Logging in to Lightsail registry..."
echo $PASSWORD | docker login --username $USERNAME --password-stdin $REGISTRY_URL

# Step 3: Tag image for Lightsail
echo "3️⃣  Tagging image for Lightsail..."
docker tag sagemaker-migration-advisor:latest $REGISTRY_URL/$SERVICE_NAME.$IMAGE_NAME:latest

# Step 4: Push to Lightsail
echo "4️⃣  Pushing image to Lightsail..."
docker push $REGISTRY_URL/$SERVICE_NAME.$IMAGE_NAME:latest

echo ""
echo "✅ Image pushed successfully!"
echo "   Image: $REGISTRY_URL/$SERVICE_NAME.$IMAGE_NAME:latest"
echo ""
