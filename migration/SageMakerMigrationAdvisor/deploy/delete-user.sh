#!/bin/bash
set -e

# Script to delete a Cognito user

if [ $# -lt 1 ]; then
    echo "Usage: $0 <email>"
    echo ""
    echo "Example:"
    echo "  $0 john@example.com"
    exit 1
fi

EMAIL=$1

# Load configuration
if [ -f ../.env ]; then
    source ../.env
else
    echo "❌ .env file not found. Please run setup-cognito.sh first."
    exit 1
fi

echo "🗑️  Deleting Cognito User"
echo "========================="
echo "Email: $EMAIL"
echo ""

read -p "Are you sure you want to delete this user? (yes/no): " CONFIRM

if [ "$CONFIRM" != "yes" ]; then
    echo "❌ Deletion cancelled"
    exit 0
fi

# Delete user
echo "Deleting user..."
aws cognito-idp admin-delete-user \
    --user-pool-id "$COGNITO_USER_POOL_ID" \
    --username "$EMAIL" \
    --region "$AWS_REGION"

echo "✅ User deleted successfully"
echo ""
