#!/bin/bash
set -e

# Deploy to Lightsail using CodeBuild to handle Docker operations
# This script creates a CodeBuild project that pulls from ECR and pushes to Lightsail

echo "🚀 Deploying to Lightsail via CodeBuild"
echo "========================================"

# Configuration
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
AWS_REGION=${AWS_REGION:-us-east-1}
SERVICE_NAME="sagemaker-migration-advisor"
PROJECT_NAME="${SERVICE_NAME}-lightsail-pusher"

echo "📋 Configuration:"
echo "   AWS Account: $AWS_ACCOUNT_ID"
echo "   AWS Region: $AWS_REGION"
echo "   Service Name: $SERVICE_NAME"
echo ""

# Get Cognito details from .env file
echo "📋 Loading configuration from .env..."
cd "$(dirname "$0")/.."
source .env

echo "   Cognito User Pool: $COGNITO_USER_POOL_ID"
echo "   Cognito Client: $COGNITO_CLIENT_ID"
echo "   S3 Bucket: $S3_BUCKET"
echo ""

# Step 1: Check if Lightsail service exists
echo "1️⃣  Checking Lightsail container service..."
SERVICE_STATE=$(aws lightsail get-container-services --service-name $SERVICE_NAME --region $AWS_REGION --query 'containerServices[0].state' --output text 2>/dev/null || echo "NOT_FOUND")

if [ "$SERVICE_STATE" = "NOT_FOUND" ]; then
    echo "   ❌ Service doesn't exist. Creating it..."
    aws lightsail create-container-service \
        --service-name $SERVICE_NAME \
        --power medium \
        --scale 1 \
        --region $AWS_REGION
    
    echo "   ⏳ Waiting for service to be ready (3-5 minutes)..."
    sleep 180
else
    echo "   ✅ Service exists (State: $SERVICE_STATE)"
fi

# Step 2: Enable ECR private registry access
echo ""
echo "2️⃣  Enabling ECR private registry access..."
aws lightsail set-resource-access-for-bucket \
    --resource-name $SERVICE_NAME \
    --access allow \
    --region $AWS_REGION 2>/dev/null || true

# Step 3: Create buildspec for Lightsail push
echo ""
echo "3️⃣  Creating buildspec for Lightsail deployment..."
cat > buildspec-lightsail.yml <<'EOF'
version: 0.2

phases:
  pre_build:
    commands:
      - echo "Logging in to Amazon ECR..."
      - aws ecr get-login-password --region $AWS_REGION | docker login --username AWS --password-stdin $ECR_REPO_URL
      - echo "Pulling image from ECR..."
      - docker pull $ECR_REPO_URL:latest
      
  build:
    commands:
      - echo "Tagging image for Lightsail..."
      - docker tag $ECR_REPO_URL:latest $SERVICE_NAME:latest
      - echo "Pushing image to Lightsail..."
      - aws lightsail push-container-image --service-name $SERVICE_NAME --label app --image $SERVICE_NAME:latest --region $AWS_REGION | tee /tmp/push-output.txt
      - IMAGE_REF=$(cat /tmp/push-output.txt | grep "Refer to this image as" | sed 's/.*"\(.*\)".*/\1/' || cat /tmp/push-output.txt | grep ":$SERVICE_NAME" | tail -1)
      - echo "Image reference - $IMAGE_REF"
      - echo $IMAGE_REF > /tmp/image-ref.txt
      
  post_build:
    commands:
      - echo "Creating Lightsail deployment..."
      - IMAGE_REF=$(cat /tmp/image-ref.txt)
      - |
        aws lightsail create-container-service-deployment \
          --service-name $SERVICE_NAME \
          --containers "{\"app\":{\"image\":\"$IMAGE_REF\",\"environment\":{\"AWS_REGION\":\"$AWS_REGION\",\"COGNITO_USER_POOL_ID\":\"$COGNITO_USER_POOL_ID\",\"COGNITO_CLIENT_ID\":\"$COGNITO_CLIENT_ID\",\"COGNITO_CLIENT_SECRET\":\"$COGNITO_CLIENT_SECRET\",\"S3_BUCKET\":\"$S3_BUCKET\"},\"ports\":{\"8501\":\"HTTP\"}}}" \
          --public-endpoint "{\"containerName\":\"app\",\"containerPort\":8501,\"healthCheck\":{\"healthyThreshold\":2,\"unhealthyThreshold\":2,\"timeoutSeconds\":5,\"intervalSeconds\":30,\"path\":\"/_stcore/health\",\"successCodes\":\"200\"}}" \
          --region $AWS_REGION
      - echo "Deployment created successfully!"

artifacts:
  files:
    - /tmp/image-ref.txt
EOF

# Step 4: Check if CodeBuild project exists
echo ""
echo "4️⃣  Setting up CodeBuild project..."
if aws codebuild batch-get-projects --names $PROJECT_NAME --region $AWS_REGION 2>/dev/null | grep -q "name"; then
    echo "   Project exists, updating it..."
    UPDATE_PROJECT=true
else
    echo "   Creating new project..."
    UPDATE_PROJECT=false
fi

# Step 5: Create/Update IAM role for CodeBuild
ROLE_NAME="${PROJECT_NAME}-role"
echo ""
echo "5️⃣  Setting up IAM role..."

# Create trust policy
cat > /tmp/trust-policy.json <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "codebuild.amazonaws.com"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
EOF

# Create or update role
if aws iam get-role --role-name $ROLE_NAME 2>/dev/null; then
    echo "   Role exists"
else
    echo "   Creating role..."
    aws iam create-role \
        --role-name $ROLE_NAME \
        --assume-role-policy-document file:///tmp/trust-policy.json
fi

# Create policy
cat > /tmp/role-policy.json <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "logs:CreateLogGroup",
        "logs:CreateLogStream",
        "logs:PutLogEvents"
      ],
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "ecr:GetAuthorizationToken",
        "ecr:BatchCheckLayerAvailability",
        "ecr:GetDownloadUrlForLayer",
        "ecr:BatchGetImage"
      ],
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "lightsail:*"
      ],
      "Resource": "*"
    }
  ]
}
EOF

# Attach policy
aws iam put-role-policy \
    --role-name $ROLE_NAME \
    --policy-name ${PROJECT_NAME}-policy \
    --policy-document file:///tmp/role-policy.json

echo "   Waiting for IAM role to propagate..."
sleep 10

# Step 6: Create or update CodeBuild project
ROLE_ARN="arn:aws:iam::${AWS_ACCOUNT_ID}:role/${ROLE_NAME}"
ECR_REPO_URL="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${SERVICE_NAME}"

echo ""
echo "6️⃣  Creating/updating CodeBuild project..."

# Upload buildspec to S3
aws s3 cp buildspec-lightsail.yml s3://$S3_BUCKET/buildspecs/buildspec-lightsail.yml

if [ "$UPDATE_PROJECT" = true ]; then
    aws codebuild update-project \
        --name $PROJECT_NAME \
        --source type=S3,location=$S3_BUCKET/buildspecs/buildspec-lightsail.yml \
        --artifacts type=NO_ARTIFACTS \
        --environment "{
          \"type\": \"LINUX_CONTAINER\",
          \"image\": \"aws/codebuild/standard:7.0\",
          \"computeType\": \"BUILD_GENERAL1_SMALL\",
          \"privilegedMode\": true,
          \"environmentVariables\": [
            {\"name\":\"AWS_REGION\",\"value\":\"$AWS_REGION\"},
            {\"name\":\"SERVICE_NAME\",\"value\":\"$SERVICE_NAME\"},
            {\"name\":\"ECR_REPO_URL\",\"value\":\"$ECR_REPO_URL\"},
            {\"name\":\"COGNITO_USER_POOL_ID\",\"value\":\"$COGNITO_USER_POOL_ID\"},
            {\"name\":\"COGNITO_CLIENT_ID\",\"value\":\"$COGNITO_CLIENT_ID\"},
            {\"name\":\"COGNITO_CLIENT_SECRET\",\"value\":\"$COGNITO_CLIENT_SECRET\"},
            {\"name\":\"S3_BUCKET\",\"value\":\"$S3_BUCKET\"}
          ]
        }" \
        --service-role $ROLE_ARN \
        --region $AWS_REGION
else
    aws codebuild create-project \
        --name $PROJECT_NAME \
        --source type=S3,location=$S3_BUCKET/buildspecs/buildspec-lightsail.yml \
        --artifacts type=NO_ARTIFACTS \
        --environment "{
          \"type\": \"LINUX_CONTAINER\",
          \"image\": \"aws/codebuild/standard:7.0\",
          \"computeType\": \"BUILD_GENERAL1_SMALL\",
          \"privilegedMode\": true,
          \"environmentVariables\": [
            {\"name\":\"AWS_REGION\",\"value\":\"$AWS_REGION\"},
            {\"name\":\"SERVICE_NAME\",\"value\":\"$SERVICE_NAME\"},
            {\"name\":\"ECR_REPO_URL\",\"value\":\"$ECR_REPO_URL\"},
            {\"name\":\"COGNITO_USER_POOL_ID\",\"value\":\"$COGNITO_USER_POOL_ID\"},
            {\"name\":\"COGNITO_CLIENT_ID\",\"value\":\"$COGNITO_CLIENT_ID\"},
            {\"name\":\"COGNITO_CLIENT_SECRET\",\"value\":\"$COGNITO_CLIENT_SECRET\"},
            {\"name\":\"S3_BUCKET\",\"value\":\"$S3_BUCKET\"}
          ]
        }" \
        --service-role $ROLE_ARN \
        --region $AWS_REGION
fi

# Step 7: Start the build
echo ""
echo "7️⃣  Starting CodeBuild to push image to Lightsail..."
BUILD_ID=$(aws codebuild start-build --project-name $PROJECT_NAME --region $AWS_REGION --query 'build.id' --output text)

echo "   Build ID: $BUILD_ID"
echo "   Monitoring build progress..."
echo ""

# Monitor build
while true; do
    BUILD_STATUS=$(aws codebuild batch-get-builds --ids $BUILD_ID --region $AWS_REGION --query 'builds[0].buildStatus' --output text)
    PHASE=$(aws codebuild batch-get-builds --ids $BUILD_ID --region $AWS_REGION --query 'builds[0].currentPhase' --output text)
    
    echo "   Status: $BUILD_STATUS | Phase: $PHASE"
    
    if [ "$BUILD_STATUS" = "SUCCEEDED" ]; then
        echo ""
        echo "✅ Build completed successfully!"
        break
    elif [ "$BUILD_STATUS" = "FAILED" ] || [ "$BUILD_STATUS" = "FAULT" ] || [ "$BUILD_STATUS" = "TIMED_OUT" ] || [ "$BUILD_STATUS" = "STOPPED" ]; then
        echo ""
        echo "❌ Build failed with status: $BUILD_STATUS"
        echo ""
        echo "View logs at:"
        echo "https://console.aws.amazon.com/codesuite/codebuild/projects/$PROJECT_NAME/history"
        exit 1
    fi
    
    sleep 10
done

# Step 8: Wait for Lightsail deployment
echo ""
echo "8️⃣  Waiting for Lightsail deployment to complete..."
echo "   This typically takes 3-5 minutes..."
echo ""

for i in {1..30}; do
    STATE=$(aws lightsail get-container-services --service-name $SERVICE_NAME --region $AWS_REGION --query 'containerServices[0].state' --output text)
    echo "   [$i/30] Current state: $STATE"
    
    if [ "$STATE" = "RUNNING" ]; then
        break
    fi
    
    sleep 10
done

# Get service URL
SERVICE_URL=$(aws lightsail get-container-services --service-name $SERVICE_NAME --region $AWS_REGION --query 'containerServices[0].url' --output text)

echo ""
echo "✅ Deployment completed successfully!"
echo "========================================"
echo "🌐 Application URL: https://$SERVICE_URL"
echo ""
echo "📝 Service Details:"
echo "   Service Name: $SERVICE_NAME"
echo "   Region: $AWS_REGION"
echo "   Power: medium (1 GB RAM, 0.5 vCPU)"
echo "   Scale: 1 instance"
echo ""
echo "🔧 To view service status:"
echo "   aws lightsail get-container-services --service-name $SERVICE_NAME --region $AWS_REGION"
echo ""
echo "🔧 To view logs:"
echo "   aws lightsail get-container-log --service-name $SERVICE_NAME --container-name app --region $AWS_REGION"
echo ""
echo "🔧 To view CodeBuild logs:"
echo "   https://console.aws.amazon.com/codesuite/codebuild/projects/$PROJECT_NAME/history"
echo ""
