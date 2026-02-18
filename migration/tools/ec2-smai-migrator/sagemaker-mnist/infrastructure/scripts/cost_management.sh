#!/bin/bash
set -e

# SageMaker Cost Management Script
# Project: sagemigrator-project

REGION="us-east-1"
PROJECT_NAME="sagemigrator-project"

log() {
    echo -e "\033[0;32m[$(date +'%Y-%m-%d %H:%M:%S')] $1\033[0m"
}

warn() {
    echo -e "\033[1;33m[WARNING] $1\033[0m"
}

# Check running resources that incur costs
check_running_resources() {
    log "Checking running resources..."
    
    # Check training jobs
    TRAINING_JOBS=$(aws sagemaker list-training-jobs \
        --name-contains "$PROJECT_NAME" \
        --status-equals InProgress \
        --region "$REGION" \
        --query 'TrainingJobSummaries[].TrainingJobName' \
        --output text)
    
    if [[ -n "$TRAINING_JOBS" ]]; then
        warn "Running training jobs found:"
        echo "$TRAINING_JOBS"
    fi
    
    # Check endpoints
    ENDPOINTS=$(aws sagemaker list-endpoints \
        --name-contains "$PROJECT_NAME" \
        --status-equals InService \
        --region "$REGION" \
        --query 'Endpoints[].[EndpointName,InstanceType]' \
        --output text)
    
    if [[ -n "$ENDPOINTS" ]]; then
        warn "Running endpoints found:"
        echo "$ENDPOINTS"
    fi
    
    # Check notebook instances
    NOTEBOOKS=$(aws sagemaker list-notebook-instances \
        --name-contains "$PROJECT_NAME" \
        --status-equals InService \
        --region "$REGION" \
        --query 'NotebookInstances[].[NotebookInstanceName,InstanceType]' \
        --output text)
    
    if [[ -n "$NOTEBOOKS" ]]; then
        warn "Running notebook instances found:"
        echo "$NOTEBOOKS"
    fi
}

# Generate cost report
generate_cost_report() {
    log "Generating cost report for the last 30 days..."
    
    START_DATE=$(date -d "30 days ago" +%Y-%m-%d)
    END_DATE=$(date +%Y-%m-%d)
    
    aws ce get-cost-and-usage \
        --time-period Start="$START_DATE",End="$END_DATE" \
        --granularity DAILY \
        --metrics BlendedCost \
        --group-by Type=DIMENSION,Key=SERVICE \
        --filter file://<(cat <<EOF
{
    "Dimensions": {
        "Key": "SERVICE",
        "Values": ["Amazon SageMaker"]
    }
}
EOF
) \
        --region "$REGION" \
        --query 'ResultsByTime[].Groups[?Keys[0]==`Amazon SageMaker`].Metrics.BlendedCost.Amount' \
        --output text | awk '{sum += $1} END {printf "Total SageMaker cost (last 30 days): $%.2f\n", sum}'
}

# Stop non-essential resources
stop_resources() {
    log "Stopping non-essential resources to save costs..."
    
    # Stop notebook instances
    NOTEBOOKS=$(aws sagemaker list-notebook-instances \
        --name-contains "$PROJECT_NAME" \
        --status-equals InService \
        --region "$REGION" \
        --query 'NotebookInstances[].NotebookInstanceName' \
        --output text)
    
    for notebook in $NOTEBOOKS; do
        if [[ -n "$notebook" ]]; then
            log "Stopping notebook instance: $notebook"
            aws sagemaker stop-notebook-instance \
                --notebook-instance-name "$notebook" \
                --region "$REGION"
        fi
    done
    
    # Note: Endpoints and training jobs require manual decision
    warn "Manual review required for endpoints and training jobs"
}

# Main function
main() {
    case "${1:-check}" in
        "check")
            check_running_resources
            ;;
        "report")
            generate_cost_report
            ;;
        "stop")
            stop_resources
            ;;
        *)
            echo "Usage: $0 {check|report|stop}"
            exit 1
            ;;
    esac
}

main "$@"