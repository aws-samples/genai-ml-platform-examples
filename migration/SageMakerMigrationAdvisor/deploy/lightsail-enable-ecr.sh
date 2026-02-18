#!/bin/bash
set -e

# Enable ECR access for Lightsail Container Service
echo "🔐 Enabling ECR access for Lightsail"
echo "===================================="

SERVICE_NAME="sagemaker-migration-advisor"
AWS_REGION=${AWS_REGION:-us-east-1}

# Create IAM role for Lightsail to access ECR
echo "1️⃣  Creating IAM role for Lightsail ECR access..."

ROLE_NAME="LightsailECRAccess"

# Check if role exists
if aws iam get-role --role-name $ROLE_NAME 2>/dev/null; then
    echo "   Role already exists"
else
    # Create trust policy
    cat > /tmp/lightsail-trust-policy.json <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "lightsail.amazonaws.com"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
EOF

    aws iam create-role \
        --role-name $ROLE_NAME \
        --assume-role-policy-document file:///tmp/lightsail-trust-policy.json

    # Attach ECR read policy
    aws iam attach-role-policy \
        --role-name $ROLE_NAME \
        --policy-arn arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryReadOnly

    echo "   Role created"
    sleep 10
fi

# Enable private registry access
echo "2️⃣  Enabling private registry access..."
aws lightsail update-container-service \
    --service-name $SERVICE_NAME \
    --private-registry-access ecrImagePullerRole={isActive=true} \
    --region $AWS_REGION

echo ""
echo "✅ ECR access enabled!"
echo "   Lightsail can now pull images from ECR"
echo ""
