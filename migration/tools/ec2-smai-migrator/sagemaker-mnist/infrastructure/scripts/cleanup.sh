#!/bin/bash
set -e

# SageMaker Infrastructure Cleanup Script
# Project: sagemigrator-project

STACK_NAME="sagemigrator-project-dev"
REGION="us-east-1"
PROJECT_NAME="sagemigrator-project"

log() {
    echo -e "\033[0;32m[$(date +'%Y-%m-%d %H:%M:%S')] $1\033[0m"
}

error() {
    echo -e "\033[0;31m[ERROR] $1\033[0m" >&2
}

# Function to cleanup SageMaker resources
cleanup_sagemaker_resources() {
    log "Cleaning up SageMaker resources..."
    
    # Stop and delete endpoints
    ENDPOINTS=$(aws sagemaker list-endpoints \
        --name-contains "$PROJECT_NAME" \
        --region "$REGION" \
        --query 'Endpoints[].EndpointName' \
        --output text)
    
    for endpoint in $ENDPOINTS; do
        if [[ -n "$endpoint" ]]; then
            log "Deleting endpoint: $endpoint"
            aws sagemaker delete-endpoint \
                --endpoint-name "$endpoint" \
                --region "$REGION" || true
        fi
    done
    
    # Delete models
    MODELS=$(aws sagemaker list-models \
        --name-contains "$PROJECT_NAME" \
        --region "$REGION" \
        --query 'Models[].ModelName' \
        --output text)
    
    for model in $MODELS; do
        if [[ -n "$model" ]]; then
            log "Deleting model: $model"
            aws sagemaker delete-model \
                --model-name "$model" \
                --region "$REGION" || true
        fi
    done
}

# Function to empty S3 bucket
empty_s3_bucket() {
    BUCKET_NAME=$(aws cloudformation describe-stacks \
        --stack-name "$STACK_NAME" \
        --region "$REGION" \
        --query 'Stacks[0].Outputs[?OutputKey==`S3BucketName`].OutputValue' \
        --output text 2>/dev/null || echo "")
    
    if [[ -n "$BUCKET_NAME" ]]; then
        log "Emptying S3 bucket: $BUCKET_NAME"
        aws s3 rm s3://"$BUCKET_NAME" --recursive || true
    fi
}

# Main cleanup process
main() {
    log "Starting cleanup process..."
    
    cleanup_sagemaker_resources
    empty_s3_bucket
    
    # Delete CloudFormation stack
    log "Deleting CloudFormation stack: $STACK_NAME"
    aws cloudformation delete-stack \
        --stack-name "$STACK_NAME" \
        --region "$REGION"
    
    log "Cleanup completed. Stack deletion in progress."
    log "Monitor progress: aws cloudformation describe-stacks --stack-name $STACK_NAME --region $REGION"
}

main "$@"