#!/bin/bash
set -e

# Script to list all Cognito users

# Load configuration
if [ -f ../.env ]; then
    source ../.env
else
    echo "❌ .env file not found. Please run setup-cognito.sh first."
    exit 1
fi

echo "👥 Listing Cognito Users"
echo "========================"
echo "User Pool: $COGNITO_USER_POOL_ID"
echo ""

# List users
aws cognito-idp list-users \
    --user-pool-id "$COGNITO_USER_POOL_ID" \
    --region "$AWS_REGION" \
    --query 'Users[*].[Username, UserStatus, Enabled, UserCreateDate]' \
    --output table

echo ""
echo "📊 User Groups:"
echo ""

# List groups
aws cognito-idp list-groups \
    --user-pool-id "$COGNITO_USER_POOL_ID" \
    --region "$AWS_REGION" \
    --query 'Groups[*].[GroupName, Description]' \
    --output table

echo ""
