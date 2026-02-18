#!/bin/bash
set -e

# SageMaker Infrastructure Deployment Script
# Project: sagemigrator-project
# Environment: dev

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_NAME="sagemigrator-project"
ENVIRONMENT="dev"
REGION="us-east-1"
STACK_NAME="sagemigrator-project-dev"
TEMPLATE_FILE="$SCRIPT_DIR/cloudformation.yaml"

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Logging function
log() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')] $1${NC}"
}

error() {
    echo -e "${RED}[ERROR] $1${NC}" >&2
}

warn() {
    echo -e "${YELLOW}[WARNING] $1${NC}"
}

# Check prerequisites
check_prerequisites() {
    log "Checking prerequisites..."
    
    # Check AWS CLI
    if ! command -v aws &> /dev/null; then
        error "AWS CLI is not installed"
        exit 1
    fi
    
    # Check AWS credentials
    if ! aws sts get-caller-identity &> /dev/null; then
        error "AWS credentials not configured"
        exit 1
    fi
    
    # Check CloudFormation template exists
    if [[ ! -f "$TEMPLATE_FILE" ]]; then
        error "CloudFormation template not found: $TEMPLATE_FILE"
        exit 1
    fi
    
    log "Prerequisites check passed"
}

# Validate CloudFormation template
validate_template() {
    log "Validating CloudFormation template..."
    
    if aws cloudformation validate-template \
        --template-body file://"$TEMPLATE_FILE" \
        --region "$REGION" &> /dev/null; then
        log "Template validation passed"
    else
        error "Template validation failed"
        exit 1
    fi
}