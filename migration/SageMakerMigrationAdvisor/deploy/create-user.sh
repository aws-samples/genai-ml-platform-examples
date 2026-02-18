#!/bin/bash
set -e

# Script to create a Cognito user

if [ $# -lt 2 ]; then
    echo "Usage: $0 <email> <name> [password] [group]"
    echo ""
    echo "Examples:"
    echo "  $0 john@example.com \"John Doe\""
    echo "  $0 admin@example.com \"Admin User\" \"SecurePass123!\" \"Admins\""
    exit 1
fi

EMAIL=$1
NAME=$2
PASSWORD=${3:-"TempPass123!"}
GROUP=${4:-"Users"}

# Load configuration
if [ -f ../.env ]; then
    source ../.env
else
    echo "❌ .env file not found. Please run setup-cognito.sh first."
    exit 1
fi

echo "👤 Creating Cognito User"
echo "========================"
echo "Email: $EMAIL"
echo "Name: $NAME"
echo "Group: $GROUP"
echo ""

# Create user
echo "1️⃣  Creating user..."
aws cognito-idp admin-create-user \
    --user-pool-id "$COGNITO_USER_POOL_ID" \
    --username "$EMAIL" \
    --user-attributes \
        Name=email,Value="$EMAIL" \
        Name=name,Value="$NAME" \
        Name=email_verified,Value=true \
    --temporary-password "$PASSWORD" \
    --message-action SUPPRESS \
    --region "$AWS_REGION"

echo "✅ User created"

# Set permanent password
echo "2️⃣  Setting permanent password..."
aws cognito-idp admin-set-user-password \
    --user-pool-id "$COGNITO_USER_POOL_ID" \
    --username "$EMAIL" \
    --password "$PASSWORD" \
    --permanent \
    --region "$AWS_REGION"

echo "✅ Password set"

# Add to group
echo "3️⃣  Adding user to group: $GROUP..."
aws cognito-idp admin-add-user-to-group \
    --user-pool-id "$COGNITO_USER_POOL_ID" \
    --username "$EMAIL" \
    --group-name "$GROUP" \
    --region "$AWS_REGION"

echo "✅ User added to group"

echo ""
echo "=========================================="
echo "✅ User created successfully!"
echo "=========================================="
echo ""
echo "📝 Login Credentials:"
echo "   Email: $EMAIL"
echo "   Password: $PASSWORD"
echo "   Group: $GROUP"
echo ""
echo "🔐 User can now login to the application"
echo ""
