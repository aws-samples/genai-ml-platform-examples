#!/bin/bash
set -e

# Build and Push Docker Image to ECR using CodeBuild
# This script zips local code, uploads to S3, and triggers CodeBuild

echo "🚀 Building Docker Image with CodeBuild (from local code)"
echo "=========================================================="

# Configuration
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
AWS_REGION=${AWS_REGION:-us-east-1}
PROJECT_NAME="sagemaker-migration-advisor-builder"
ECR_REPO_NAME="sagemaker-migration-advisor"

echo "📋 Configuration:"
echo "   AWS Account: $AWS_ACCOUNT_ID"
echo "   AWS Region: $AWS_REGION"
echo "   Project Name: $PROJECT_NAME"
echo "   ECR Repository: $ECR_REPO_NAME"
echo ""

# Get the current directory (should be in deploy/)
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Load S3 bucket from .env
cd "$PROJECT_ROOT"
source .env
S3_BUCKET=${S3_BUCKET:-sagemaker-migration-advisor-artifacts-${AWS_ACCOUNT_ID}}

# Step 1: Create source archive
echo "1️⃣  Creating source archive from local code..."
TIMESTAMP=$(date +%Y%m%d-%H%M%S)
ARCHIVE_NAME="source-${TIMESTAMP}.zip"

# Create zip excluding unnecessary files
cd "$PROJECT_ROOT"
zip -r "/tmp/$ARCHIVE_NAME" . \
    -x "*.git*" \
    -x "*__pycache__*" \
    -x "*.pyc" \
    -x "*venv/*" \
    -x "*.DS_Store" \
    -x "*logs/*" \
    -x "*generated-diagrams/*" \
    -x "*/terraform/.terraform/*" \
    -x "*/terraform/*.tfstate*" \
    -x "*/terraform/tfplan"

echo "   ✅ Source archive created: /tmp/$ARCHIVE_NAME"

# Step 2: Upload to S3
echo ""
echo "2️⃣  Uploading source to S3..."
aws s3 cp "/tmp/$ARCHIVE_NAME" "s3://$S3_BUCKET/codebuild-source/$ARCHIVE_NAME"
echo "   ✅ Uploaded to s3://$S3_BUCKET/codebuild-source/$ARCHIVE_NAME"

# Step 3: Ensure ECR repository exists
echo ""
echo "3️⃣  Checking ECR repository..."
if ! aws ecr describe-repositories --repository-names $ECR_REPO_NAME --region $AWS_REGION &>/dev/null; then
    echo "   Creating ECR repository..."
    aws ecr create-repository --repository-name $ECR_REPO_NAME --region $AWS_REGION
else
    echo "   ✅ ECR repository exists"
fi

# Step 4: Create IAM role for CodeBuild
ROLE_NAME="${PROJECT_NAME}-role"
echo ""
echo "4️⃣  Setting up IAM role..."

# Create trust policy
cat > /tmp/codebuild-trust-policy.json <<EOF
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
    echo "   ✅ Role exists"
else
    echo "   Creating role..."
    aws iam create-role \
        --role-name $ROLE_NAME \
        --assume-role-policy-document file:///tmp/codebuild-trust-policy.json
fi

# Create policy
cat > /tmp/codebuild-policy.json <<EOF
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
        "ecr:BatchGetImage",
        "ecr:PutImage",
        "ecr:InitiateLayerUpload",
        "ecr:UploadLayerPart",
        "ecr:CompleteLayerUpload"
      ],
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:PutObject"
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
    --policy-document file:///tmp/codebuild-policy.json

echo "   Waiting for IAM role to propagate..."
sleep 10

# Step 5: Create buildspec for ECR push
echo ""
echo "5️⃣  Creating buildspec..."
cat > /tmp/buildspec-ecr.yml <<EOF
version: 0.2

phases:
  pre_build:
    commands:
      - echo Logging in to Amazon ECR...
      - aws ecr get-login-password --region \$AWS_DEFAULT_REGION | docker login --username AWS --password-stdin \$AWS_ACCOUNT_ID.dkr.ecr.\$AWS_DEFAULT_REGION.amazonaws.com
      - REPOSITORY_URI=\$AWS_ACCOUNT_ID.dkr.ecr.\$AWS_DEFAULT_REGION.amazonaws.com/\$IMAGE_REPO_NAME
      - IMAGE_TAG=\$(date +%Y%m%d-%H%M%S)
      
  build:
    commands:
      - echo Build started on \$(date)
      - echo Building the Docker image...
      - docker build -t \$REPOSITORY_URI:latest .
      - docker tag \$REPOSITORY_URI:latest \$REPOSITORY_URI:\$IMAGE_TAG
      
  post_build:
    commands:
      - echo Build completed on \$(date)
      - echo Pushing the Docker images...
      - docker push \$REPOSITORY_URI:latest
      - docker push \$REPOSITORY_URI:\$IMAGE_TAG
      - echo Image pushed successfully!
      - echo "Latest image - \$REPOSITORY_URI:latest"
      - echo "Tagged image - \$REPOSITORY_URI:\$IMAGE_TAG"
EOF

# Step 6: Check if CodeBuild project exists
echo ""
echo "6️⃣  Setting up CodeBuild project..."
ROLE_ARN="arn:aws:iam::${AWS_ACCOUNT_ID}:role/${ROLE_NAME}"

if aws codebuild batch-get-projects --names $PROJECT_NAME --region $AWS_REGION 2>/dev/null | grep -q "name"; then
    echo "   Updating existing project..."
    aws codebuild update-project \
        --name $PROJECT_NAME \
        --source "{
          \"type\": \"S3\",
          \"location\": \"$S3_BUCKET/codebuild-source/$ARCHIVE_NAME\"
        }" \
        --artifacts type=NO_ARTIFACTS \
        --environment "{
          \"type\": \"LINUX_CONTAINER\",
          \"image\": \"aws/codebuild/standard:7.0\",
          \"computeType\": \"BUILD_GENERAL1_SMALL\",
          \"privilegedMode\": true,
          \"environmentVariables\": [
            {\"name\":\"AWS_DEFAULT_REGION\",\"value\":\"$AWS_REGION\"},
            {\"name\":\"AWS_ACCOUNT_ID\",\"value\":\"$AWS_ACCOUNT_ID\"},
            {\"name\":\"IMAGE_REPO_NAME\",\"value\":\"$ECR_REPO_NAME\"}
          ]
        }" \
        --service-role $ROLE_ARN \
        --region $AWS_REGION
else
    echo "   Creating new project..."
    aws codebuild create-project \
        --name $PROJECT_NAME \
        --source "{
          \"type\": \"S3\",
          \"location\": \"$S3_BUCKET/codebuild-source/$ARCHIVE_NAME\"
        }" \
        --artifacts type=NO_ARTIFACTS \
        --environment "{
          \"type\": \"LINUX_CONTAINER\",
          \"image\": \"aws/codebuild/standard:7.0\",
          \"computeType\": \"BUILD_GENERAL1_SMALL\",
          \"privilegedMode\": true,
          \"environmentVariables\": [
            {\"name\":\"AWS_DEFAULT_REGION\",\"value\":\"$AWS_REGION\"},
            {\"name\":\"AWS_ACCOUNT_ID\",\"value\":\"$AWS_ACCOUNT_ID\"},
            {\"name\":\"IMAGE_REPO_NAME\",\"value\":\"$ECR_REPO_NAME\"}
          ]
        }" \
        --service-role $ROLE_ARN \
        --region $AWS_REGION
fi

# Step 7: Start the build
echo ""
echo "7️⃣  Starting CodeBuild..."
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
        echo ""
        echo "📦 Docker image pushed to ECR:"
        echo "   ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${ECR_REPO_NAME}:latest"
        echo ""
        echo "🔧 Next steps:"
        echo "   1. Update ECS service to use new image:"
        echo "      cd deploy && ./deploy-ecs.sh"
        echo ""
        echo "   2. Or update Lightsail deployment:"
        echo "      cd deploy && ./codebuild-lightsail.sh"
        echo ""
        break
    elif [ "$BUILD_STATUS" = "FAILED" ] || [ "$BUILD_STATUS" = "FAULT" ] || [ "$BUILD_STATUS" = "TIMED_OUT" ] || [ "$BUILD_STATUS" = "STOPPED" ]; then
        echo ""
        echo "❌ Build failed with status: $BUILD_STATUS"
        echo ""
        echo "View logs at:"
        echo "https://console.aws.amazon.com/codesuite/codebuild/${AWS_REGION}/projects/$PROJECT_NAME/history"
        exit 1
    fi
    
    sleep 10
done

echo "✅ Image build and push completed!"
echo "========================================"

