#!/bin/bash
set -e

# Script to reset a user's password

if [ $# -lt 2 ]; then
    echo "Usage: $0 <email> <new-password>"
    echo ""
    echo "Example:"
    echo "  $0 john@example.com 'NewSecurePass123!'"
    exit 1
fi

EMAIL=$1
NEW_PASSWORD=$2

# Load configuration
if [ -f ../.env ]; then
    source ../.env
else
    echo "❌ .env file not found. Please run setup-cognito.sh first."
    exit 1
fi

echo "🔑 Resetting User Password"
echo "=========================="
echo "Email: $EMAIL"
echo ""

# Reset password
echo "Setting new password..."
aws cognito-idp admin-set-user-password \
    --user-pool-id "$COGNITO_USER_POOL_ID" \
    --username "$EMAIL" \
    --password "$NEW_PASSWORD" \
    --permanent \
    --region "$AWS_REGION"

echo "✅ Password reset successfully"
echo ""
echo "📝 New credentials:"
echo "   Email: $EMAIL"
echo "   Password: $NEW_PASSWORD"
echo ""
