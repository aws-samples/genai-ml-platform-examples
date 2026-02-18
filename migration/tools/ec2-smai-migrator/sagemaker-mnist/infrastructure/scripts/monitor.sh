#!/bin/bash
set -e

# SageMaker Monitoring Script
# Project: sagemigrator-project

REGION="us-east-1"
PROJECT_NAME="sagemigrator-project"

log() {
    echo -e "\033[0;32m[$(date +'%Y-%m-%d %H:%M:%S')] $1\033[0m"
}

# Monitor training jobs
monitor_training_jobs() {
    log "Monitoring training jobs..."
    
    aws sagemaker list-training-jobs \
        --name-contains "$PROJECT_NAME" \
        --region "$REGION" \
        --query 'TrainingJobSummaries[?TrainingJobStatus==`InProgress`].[TrainingJobName,TrainingJobStatus,CreationTime]' \
        --output table
}

# Monitor endpoints
monitor_endpoints() {
    log "Monitoring endpoints..."
    
    aws sagemaker list-endpoints \
        --name-contains "$PROJECT_NAME" \
        --region "$REGION" \
        --query 'Endpoints[].[EndpointName,EndpointStatus,CreationTime]' \
        --output table
}

# Check CloudWatch logs
check_logs() {
    LOG_GROUP="/aws/sagemaker/$PROJECT_NAME"
    
    log "Recent log events from $LOG_GROUP:"
    
    aws logs describe-log-streams \
        --log-group-name "$LOG_GROUP" \
        --region "$REGION" \
        --order-by LastEventTime \
        --descending \
        --max-items 5 \
        --query 'logStreams[0].logStreamName' \
        --output text | while read -r stream; do
        if [[ -n "$stream" ]]; then
            aws logs get-log-events \
                --log-group-name "$LOG_GROUP" \
                --log-stream-name "$stream" \
                --region "$REGION" \
                --limit 10 \
                --query 'events[].[timestamp,message]' \
                --output text
        fi
    done
}

# Main monitoring function
main() {
    log "Starting monitoring check..."
    
    monitor_training_jobs
    monitor_endpoints
    check_logs
    
    log "Monitoring check completed"
}

main "$@"