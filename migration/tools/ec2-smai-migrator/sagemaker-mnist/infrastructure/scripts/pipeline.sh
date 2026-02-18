#!/bin/bash
set -e

# SageMaker Pipeline Execution Script
# Project: sagemigrator-project

REGION="us-east-1"
PROJECT_NAME="sagemigrator-project"
PIPELINE_NAME="${PROJECT_NAME}-pipeline"

log() {
    echo -e "\033[0;32m[$(date +'%Y-%m-%d %H:%M:%S')] $1\033[0m"
}

error() {
    echo -e "\033[0;31m[ERROR] $1\033[0m" >&2
}

# Start pipeline execution
start_pipeline() {
    log "Starting pipeline execution: $PIPELINE_NAME"
    
    EXECUTION_ARN=$(aws sagemaker start-pipeline-execution \
        --pipeline-name "$PIPELINE_NAME" \
        --region "$REGION" \
        --query 'PipelineExecutionArn' \
        --output text)
    
    if [[ -n "$EXECUTION_ARN" ]]; then
        log "Pipeline execution started: $EXECUTION_ARN"
        echo "$EXECUTION_ARN" > pipeline_execution.arn
    else
        error "Failed to start pipeline execution"
        exit 1
    fi
}

# Monitor pipeline execution
monitor_pipeline() {
    if [[ -f "pipeline_execution.arn" ]]; then
        EXECUTION_ARN=$(cat pipeline_execution.arn)
    else
        error "No pipeline execution ARN found"
        exit 1
    fi
    
    log "Monitoring pipeline execution: $EXECUTION_ARN"
    
    while true; do
        STATUS=$(aws sagemaker describe-pipeline-execution \
            --pipeline-execution-arn "$EXECUTION_ARN" \
            --region "$REGION" \
            --query 'PipelineExecutionStatus' \
            --output text)
        
        log "Pipeline status: $STATUS"
        
        case "$STATUS" in
            "Succeeded")
                log "Pipeline execution completed successfully"
                break
                ;;
            "Failed"|"Stopped")
                error "Pipeline execution failed with status: $STATUS"
                exit 1
                ;;
            "Executing"|"Stopping")
                log "Pipeline still running, checking again in 30 seconds..."
                sleep 30
                ;;
            *)
                warn "Unknown status: $STATUS"
                sleep 30
                ;;
        esac
    done
}

# Restart failed pipeline
restart_pipeline() {
    log "Restarting pipeline: $PIPELINE_NAME"
    
    # Stop any running executions
    RUNNING_EXECUTIONS=$(aws sagemaker list-pipeline-executions \
        --pipeline-name "$PIPELINE_NAME" \
        --region "$REGION" \
        --query 'PipelineExecutionSummaries[?PipelineExecutionStatus==`Executing`].PipelineExecutionArn' \
        --output text)
    
    for execution in $RUNNING_EXECUTIONS; do
        if [[ -n "$execution" ]]; then
            log "Stopping execution: $execution"
            aws sagemaker stop-pipeline-execution \
                --pipeline-execution-arn "$execution" \
                --region "$REGION"
        fi
    done
    
    # Wait a bit for cleanup
    sleep 10
    
    # Start new execution
    start_pipeline
}

# Main function
main() {
    case "${1:-start}" in
        "start")
            start_pipeline
            ;;
        "monitor")
            monitor_pipeline
            ;;
        "restart")
            restart_pipeline
            ;;
        *)
            echo "Usage: $0 {start|monitor|restart}"
            exit 1
            ;;
    esac
}

main "$@"