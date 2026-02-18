#!/bin/bash
set -e

# Cognito Setup Script for SageMaker Migration Advisor
# This script creates and configures Cognito User Pool and Client

echo "🔐 Setting up AWS Cognito for SageMaker Migration Advisor"
echo "=========================================================="

# Configuration
AWS_REGION=${AWS_REGION:-us-east-1}
APP_NAME="sagemaker-migration-advisor"
USER_POOL_NAME="${APP_NAME}-user-pool"
CLIENT_NAME="${APP_NAME}-client"

echo "📋 Configuration:"
echo "   AWS Region: $AWS_REGION"
echo "   User Pool Name: $USER_POOL_NAME"
echo "   Client Name: $CLIENT_NAME"
echo ""

# Check if AWS CLI is installed
if ! command -v aws &> /dev/null; then
    echo "❌ AWS CLI is not installed. Please install it first."
    exit 1
fi

# Check AWS credentials
echo "🔍 Checking AWS credentials..."
if ! aws sts get-caller-identity &> /dev/null; then
    echo "❌ AWS credentials not configured. Please run 'aws configure' first."
    exit 1
fi

AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
echo "✅ Connected to AWS Account: $AWS_ACCOUNT_ID"
echo ""

# Step 1: Create Cognito User Pool
echo "1️⃣  Creating Cognito User Pool..."

USER_POOL_ID=$(aws cognito-idp create-user-pool \
    --pool-name "$USER_POOL_NAME" \
    --policies '{
        "PasswordPolicy": {
            "MinimumLength": 8,
            "RequireUppercase": true,
            "RequireLowercase": true,
            "RequireNumbers": true,
            "RequireSymbols": true
        }
    }' \
    --auto-verified-attributes email \
    --username-attributes email \
    --schema '[
        {
            "Name": "email",
            "AttributeDataType": "String",
            "Required": true,
            "Mutable": true
        },
        {
            "Name": "name",
            "AttributeDataType": "String",
            "Required": false,
            "Mutable": true
        }
    ]' \
    --mfa-configuration OFF \
    --account-recovery-setting '{
        "RecoveryMechanisms": [
            {
                "Priority": 1,
                "Name": "verified_email"
            }
        ]
    }' \
    --user-pool-tags "Application=$APP_NAME,ManagedBy=Script" \
    --region "$AWS_REGION" \
    --query 'UserPool.Id' \
    --output text)

echo "✅ User Pool created: $USER_POOL_ID"

# Step 2: Create User Pool Client
echo "2️⃣  Creating User Pool Client..."

CLIENT_OUTPUT=$(aws cognito-idp create-user-pool-client \
    --user-pool-id "$USER_POOL_ID" \
    --client-name "$CLIENT_NAME" \
    --generate-secret \
    --explicit-auth-flows ALLOW_USER_PASSWORD_AUTH ALLOW_REFRESH_TOKEN_AUTH ALLOW_USER_SRP_AUTH \
    --prevent-user-existence-errors ENABLED \
    --enable-token-revocation \
    --access-token-validity 60 \
    --id-token-validity 60 \
    --refresh-token-validity 30 \
    --token-validity-units '{
        "AccessToken": "minutes",
        "IdToken": "minutes",
        "RefreshToken": "days"
    }' \
    --region "$AWS_REGION" \
    --output json)

CLIENT_ID=$(echo "$CLIENT_OUTPUT" | jq -r '.UserPoolClient.ClientId')
CLIENT_SECRET=$(echo "$CLIENT_OUTPUT" | jq -r '.UserPoolClient.ClientSecret')

echo "✅ Client created: $CLIENT_ID"

# Step 3: Create User Pool Domain (for hosted UI - optional)
echo "3️⃣  Creating User Pool Domain..."

DOMAIN_PREFIX="${APP_NAME}-${AWS_ACCOUNT_ID}"

if aws cognito-idp create-user-pool-domain \
    --domain "$DOMAIN_PREFIX" \
    --user-pool-id "$USER_POOL_ID" \
    --region "$AWS_REGION" &> /dev/null; then
    echo "✅ Domain created: $DOMAIN_PREFIX.auth.$AWS_REGION.amazoncognito.com"
else
    echo "⚠️  Domain already exists or could not be created (this is optional)"
fi

# Step 4: Create admin user group
echo "4️⃣  Creating admin user group..."

aws cognito-idp create-group \
    --group-name "Admins" \
    --user-pool-id "$USER_POOL_ID" \
    --description "Administrator users with full access" \
    --region "$AWS_REGION" &> /dev/null || echo "⚠️  Admin group may already exist"

echo "✅ Admin group created"

# Step 5: Create standard user group
echo "5️⃣  Creating standard user group..."

aws cognito-idp create-group \
    --group-name "Users" \
    --user-pool-id "$USER_POOL_ID" \
    --description "Standard users with basic access" \
    --region "$AWS_REGION" &> /dev/null || echo "⚠️  Users group may already exist"

echo "✅ Users group created"

# Step 6: Save configuration to .env file
echo "6️⃣  Saving configuration..."

cat > ../.env << EOF
# AWS Cognito Configuration
# Generated on $(date)

AWS_REGION=$AWS_REGION
COGNITO_USER_POOL_ID=$USER_POOL_ID
COGNITO_CLIENT_ID=$CLIENT_ID
COGNITO_CLIENT_SECRET=$CLIENT_SECRET
COGNITO_DOMAIN=$DOMAIN_PREFIX.auth.$AWS_REGION.amazoncognito.com

# S3 Configuration (update after creating S3 bucket)
S3_BUCKET=${APP_NAME}-artifacts-${AWS_ACCOUNT_ID}
EOF

echo "✅ Configuration saved to .env file"

# Step 7: Display summary
echo ""
echo "=========================================================="
echo "✅ Cognito Setup Complete!"
echo "=========================================================="
echo ""
echo "📝 Configuration Details:"
echo "   User Pool ID: $USER_POOL_ID"
echo "   Client ID: $CLIENT_ID"
echo "   Client Secret: $CLIENT_SECRET"
echo "   Domain: $DOMAIN_PREFIX.auth.$AWS_REGION.amazoncognito.com"
echo ""
echo "🔧 Next Steps:"
echo ""
echo "1. Create test users:"
echo "   ./create-user.sh <email> <name>"
echo ""
echo "2. Or manually create a user:"
echo "   aws cognito-idp admin-create-user \\"
echo "     --user-pool-id $USER_POOL_ID \\"
echo "     --username user@example.com \\"
echo "     --user-attributes Name=email,Value=user@example.com Name=name,Value=\"John Doe\" \\"
echo "     --temporary-password 'TempPass123!' \\"
echo "     --message-action SUPPRESS \\"
echo "     --region $AWS_REGION"
echo ""
echo "3. Set permanent password:"
echo "   aws cognito-idp admin-set-user-password \\"
echo "     --user-pool-id $USER_POOL_ID \\"
echo "     --username user@example.com \\"
echo "     --password 'YourPassword123!' \\"
echo "     --permanent \\"
echo "     --region $AWS_REGION"
echo ""
echo "4. Add user to admin group:"
echo "   aws cognito-idp admin-add-user-to-group \\"
echo "     --user-pool-id $USER_POOL_ID \\"
echo "     --username user@example.com \\"
echo "     --group-name Admins \\"
echo "     --region $AWS_REGION"
echo ""
echo "5. Test the application locally:"
echo "   cd .. && source venv/bin/activate"
echo "   source .env"
echo "   streamlit run app.py"
echo ""
echo "📄 Configuration saved to: ../.env"
echo ""
