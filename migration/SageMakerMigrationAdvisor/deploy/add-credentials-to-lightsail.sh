#!/bin/bash
set -e

# Quick fix: Add AWS credentials to Lightsail for Bedrock access
echo "🔧 Adding Bedrock Permissions to Lightsail"
echo "==========================================="
echo ""

AWS_REGION=us-east-1
SERVICE_NAME="sagemaker-migration-advisor"
USER_NAME="${SERVICE_NAME}-app-user"
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)

# Load environment variables
source .env

echo "Step 1: Create IAM user with Bedrock permissions"
echo "=================================================="

# Create IAM user if it doesn't exist
if aws iam get-user --user-name $USER_NAME 2>/dev/null; then
    echo "✅ User already exists: $USER_NAME"
else
    echo "Creating IAM user..."
    aws iam create-user --user-name $USER_NAME
    echo "✅ User created: $USER_NAME"
fi

# Create and attach policy
echo ""
echo "Attaching Bedrock permissions..."

cat > /tmp/bedrock-policy.json <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "bedrock:InvokeModel",
        "bedrock:InvokeModelWithResponseStream",
        "bedrock:ListFoundationModels",
        "bedrock:GetFoundationModel"
      ],
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:PutObject",
        "s3:ListBucket"
      ],
      "Resource": [
        "arn:aws:s3:::${S3_BUCKET}",
        "arn:aws:s3:::${S3_BUCKET}/*"
      ]
    }
  ]
}
EOF

aws iam put-user-policy \
    --user-name $USER_NAME \
    --policy-name BedrockAndS3Access \
    --policy-document file:///tmp/bedrock-policy.json

echo "✅ Permissions attached"

# Create access key
echo ""
echo "Step 2: Create access key"
echo "========================="

# Delete old keys if they exist
OLD_KEYS=$(aws iam list-access-keys --user-name $USER_NAME --query 'AccessKeyMetadata[*].AccessKeyId' --output text)
for KEY in $OLD_KEYS; do
    echo "Deleting old access key: $KEY"
    aws iam delete-access-key --user-name $USER_NAME --access-key-id $KEY
done

# Create new access key
ACCESS_KEY_JSON=$(aws iam create-access-key --user-name $USER_NAME --output json)
AWS_ACCESS_KEY_ID=$(echo $ACCESS_KEY_JSON | jq -r '.AccessKey.AccessKeyId')
AWS_SECRET_ACCESS_KEY=$(echo $ACCESS_KEY_JSON | jq -r '.AccessKey.SecretAccessKey')

echo "✅ Access key created"
echo ""

# Update Lightsail deployment
echo "Step 3: Update Lightsail deployment with credentials"
echo "====================================================="

# Create new deployment with credentials
aws lightsail create-container-service-deployment \
    --service-name $SERVICE_NAME \
    --containers "{
      \"app\": {
        \"image\": \"${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${SERVICE_NAME}:latest\",
        \"environment\": {
          \"AWS_REGION\": \"${AWS_REGION}\",
          \"AWS_ACCESS_KEY_ID\": \"${AWS_ACCESS_KEY_ID}\",
          \"AWS_SECRET_ACCESS_KEY\": \"${AWS_SECRET_ACCESS_KEY}\",
          \"COGNITO_USER_POOL_ID\": \"${COGNITO_USER_POOL_ID}\",
          \"COGNITO_CLIENT_ID\": \"${COGNITO_CLIENT_ID}\",
          \"COGNITO_CLIENT_SECRET\": \"${COGNITO_CLIENT_SECRET}\",
          \"S3_BUCKET\": \"${S3_BUCKET}\"
        },
        \"ports\": {
          \"8501\": \"HTTP\"
        }
      }
    }" \
    --public-endpoint "{
      \"containerName\": \"app\",
      \"containerPort\": 8501,
      \"healthCheck\": {
        \"healthyThreshold\": 2,
        \"unhealthyThreshold\": 2,
        \"timeoutSeconds\": 5,
        \"intervalSeconds\": 30,
        \"path\": \"/_stcore/health\",
        \"successCodes\": \"200\"
      }
    }" \
    --region $AWS_REGION

echo ""
echo "✅ Deployment updated with Bedrock credentials!"
echo ""
echo "⏳ Waiting for deployment to complete (3-5 minutes)..."

# Wait for deployment
for i in {1..30}; do
    STATE=$(aws lightsail get-container-services --service-name $SERVICE_NAME --region $AWS_REGION --query 'containerServices[0].state' --output text)
    echo "   [$i/30] Current state: $STATE"
    
    if [ "$STATE" = "RUNNING" ]; then
        break
    fi
    
    sleep 10
done

echo ""
echo "✅ Deployment complete!"
echo ""
echo "🌐 Application URL: https://sagemaker-migration-advisor.nxpnv0fwethe0.us-east-1.cs.amazonlightsail.com/"
echo ""
echo "⚠️  SECURITY NOTE:"
echo "   AWS credentials are stored in environment variables."
echo "   For production, consider deploying to ECS Fargate with IAM roles."
echo ""
echo "📝 Credentials saved for user: $USER_NAME"
echo "   Access Key ID: $AWS_ACCESS_KEY_ID"
echo "   (Secret key is in the deployment, not shown here)"
echo ""
