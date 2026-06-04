#!/bin/bash
set -euo pipefail

###############################################################################
# Self-Deployment Script for SageMaker Unified Studio Workshop
#
# This script deploys the workshop infrastructure into your own AWS account
# without requiring AWS Workshop Studio.
#
# Prerequisites:
#   - AWS CLI v2 configured with credentials that have AdministratorAccess
#   - The AWS account must NOT already have an IAM Identity Center instance
#     named 'workshop-identity-center' (or set SKIP_IDENTITY_CENTER=true)
#   - Sufficient service quotas for VPC, NAT Gateway, EC2, Lambda, DynamoDB
#
# Usage:
#   chmod +x deploy.sh
#   ./deploy.sh                          # Deploy all stacks (creates new VPC)
#   ./deploy.sh --vpc-id vpc-abc --private-subnets subnet-1,subnet-2,subnet-3
#                                        # Use an existing VPC
#   ./deploy.sh --vpc-cidr 10.50.0.0/16  # Create new VPC with custom CIDR
#   ./deploy.sh --skip-code-editor       # Skip the Code Editor IDE stack
#   ./deploy.sh --skip-identity-center   # Skip Identity Center creation
#   ./deploy.sh --region us-west-2       # Deploy to a specific region
#   ./deploy.sh --teardown               # Delete all stacks
#
###############################################################################

# ─── Configuration ───────────────────────────────────────────────────────────

STACK_PREFIX="${STACK_PREFIX:-smus-workshop-v1}"
AWS_REGION="${AWS_REGION:-us-east-1}"
SKIP_CODE_EDITOR=false
SKIP_IDENTITY_CENTER=false
TEARDOWN=false
DOMAIN_NAME="${DOMAIN_NAME:-smus-domain-orchestrated-v1}"
EXISTING_VPC_ID=""
EXISTING_PRIVATE_SUBNET_1=""
EXISTING_PRIVATE_SUBNET_2=""
EXISTING_PRIVATE_SUBNET_3=""
VPC_CIDR="10.38.0.0/16"

# ─── Parse Arguments ─────────────────────────────────────────────────────────

while [[ $# -gt 0 ]]; do
  case $1 in
    --skip-code-editor)
      SKIP_CODE_EDITOR=true
      shift
      ;;
    --skip-identity-center)
      SKIP_IDENTITY_CENTER=true
      shift
      ;;
    --region)
      AWS_REGION="$2"
      shift 2
      ;;
    --stack-prefix)
      STACK_PREFIX="$2"
      shift 2
      ;;
    --domain-name)
      DOMAIN_NAME="$2"
      shift 2
      ;;
    --vpc-id)
      EXISTING_VPC_ID="$2"
      shift 2
      ;;
    --private-subnets)
      IFS=',' read -r EXISTING_PRIVATE_SUBNET_1 EXISTING_PRIVATE_SUBNET_2 EXISTING_PRIVATE_SUBNET_3 <<< "$2"
      shift 2
      ;;
    --vpc-cidr)
      VPC_CIDR="$2"
      shift 2
      ;;
    --teardown)
      TEARDOWN=true
      shift
      ;;
    --help|-h)
      echo "Usage: $0 [OPTIONS]"
      echo ""
      echo "Options:"
      echo "  --region REGION            AWS region (default: us-east-1)"
      echo "  --stack-prefix PREFIX      Stack name prefix (default: smus-workshop)"
      echo "  --domain-name NAME         DataZone domain name (default: smus-domain-orchestrated)"
      echo "  --vpc-id VPC_ID            Use an existing VPC instead of creating a new one"
      echo "  --private-subnets S1,S2,S3 Comma-separated private subnet IDs (required with --vpc-id)"
      echo "  --vpc-cidr CIDR            VPC CIDR block when creating new VPC (default: 10.38.0.0/16)"
      echo "  --skip-code-editor         Skip deploying the Code Editor IDE"
      echo "  --skip-identity-center     Skip Identity Center creation"
      echo "  --teardown                 Delete all deployed stacks"
      echo "  -h, --help                 Show this help message"
      exit 0
      ;;
    *)
      echo "Unknown option: $1"
      exit 1
      ;;
  esac
done

# ─── Derived Names ───────────────────────────────────────────────────────────

ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text --region "$AWS_REGION")
ASSETS_BUCKET="${STACK_PREFIX}-assets-${ACCOUNT_ID}-${AWS_REGION}"
ASSETS_PREFIX="workshop/"

ORCHESTRATOR_STACK="${STACK_PREFIX}-platform"
AIREGISTRY_STACK="${STACK_PREFIX}-airegistry"
CODEEDITOR_STACK="${STACK_PREFIX}-code-editor"

# ─── Helper Functions ────────────────────────────────────────────────────────

log() {
  echo "[$(date '+%H:%M:%S')] $*"
}

wait_for_stack() {
  local stack_name="$1"
  local desired_status="$2"
  log "Waiting for stack '$stack_name' to reach $desired_status..."

  aws cloudformation wait "stack-${desired_status}" \
    --stack-name "$stack_name" \
    --region "$AWS_REGION" 2>/dev/null

  local status
  status=$(aws cloudformation describe-stacks \
    --stack-name "$stack_name" \
    --region "$AWS_REGION" \
    --query "Stacks[0].StackStatus" \
    --output text 2>/dev/null || echo "UNKNOWN")

  if [[ "$status" == *"FAILED"* ]] || [[ "$status" == *"ROLLBACK"* ]]; then
    log "ERROR: Stack '$stack_name' ended in status: $status"
    log "Check the CloudFormation console for failure details."
    exit 1
  fi

  log "Stack '$stack_name' status: $status"
}

# ─── Teardown ────────────────────────────────────────────────────────────────

if [[ "$TEARDOWN" == "true" ]]; then
  log "=== Tearing down all stacks ==="

  for stack in "$CODEEDITOR_STACK" "$AIREGISTRY_STACK" "$ORCHESTRATOR_STACK"; do
    if aws cloudformation describe-stacks --stack-name "$stack" --region "$AWS_REGION" &>/dev/null; then
      log "Deleting stack: $stack"
      aws cloudformation delete-stack --stack-name "$stack" --region "$AWS_REGION"
      aws cloudformation wait stack-delete-complete --stack-name "$stack" --region "$AWS_REGION"
      log "Deleted: $stack"
    else
      log "Stack not found (skipping): $stack"
    fi
  done

  log "Emptying and deleting assets bucket: $ASSETS_BUCKET"
  aws s3 rb "s3://${ASSETS_BUCKET}" --force --region "$AWS_REGION" 2>/dev/null || true

  log "=== Teardown complete ==="
  exit 0
fi

# ─── Pre-flight Checks ──────────────────────────────────────────────────────

log "=== Pre-flight Checks ==="
log "Account ID:    $ACCOUNT_ID"
log "Region:        $AWS_REGION"
log "Assets Bucket: $ASSETS_BUCKET"
log "Stack Prefix:  $STACK_PREFIX"
log "Domain Name:   $DOMAIN_NAME"
if [[ -n "$EXISTING_VPC_ID" ]]; then
  log "Using VPC:     $EXISTING_VPC_ID (existing)"
  log "  Subnet 1:    $EXISTING_PRIVATE_SUBNET_1"
  log "  Subnet 2:    $EXISTING_PRIVATE_SUBNET_2"
  log "  Subnet 3:    $EXISTING_PRIVATE_SUBNET_3"
else
  log "VPC:           Creating new (CIDR: $VPC_CIDR)"
fi
echo ""

# Validate VPC parameters
if [[ -n "$EXISTING_VPC_ID" ]]; then
  if [[ -z "$EXISTING_PRIVATE_SUBNET_1" || -z "$EXISTING_PRIVATE_SUBNET_2" || -z "$EXISTING_PRIVATE_SUBNET_3" ]]; then
    log "ERROR: --private-subnets must provide 3 comma-separated subnet IDs when using --vpc-id"
    log "Example: --vpc-id vpc-abc123 --private-subnets subnet-1,subnet-2,subnet-3"
    exit 1
  fi
fi

# Verify AWS CLI access
if ! aws sts get-caller-identity --region "$AWS_REGION" &>/dev/null; then
  log "ERROR: AWS CLI is not configured or credentials are invalid."
  exit 1
fi

# ─── Step 1: Create and Populate S3 Assets Bucket ────────────────────────────

log "=== Step 1: Setting up S3 assets bucket ==="

if aws s3api head-bucket --bucket "$ASSETS_BUCKET" --region "$AWS_REGION" 2>/dev/null; then
  log "Bucket already exists: $ASSETS_BUCKET"
else
  log "Creating bucket: $ASSETS_BUCKET"
  if [[ "$AWS_REGION" == "us-east-1" ]]; then
    aws s3api create-bucket \
      --bucket "$ASSETS_BUCKET" \
      --region "$AWS_REGION"
  else
    aws s3api create-bucket \
      --bucket "$ASSETS_BUCKET" \
      --region "$AWS_REGION" \
      --create-bucket-configuration LocationConstraint="$AWS_REGION"
  fi
fi

# Block public access
aws s3api put-public-access-block \
  --bucket "$ASSETS_BUCKET" \
  --public-access-block-configuration \
    BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true \
  --region "$AWS_REGION"

log "Uploading nested CloudFormation templates..."
aws s3 cp assets/SageMakerUnifiedStudio-VPC.yaml \
  "s3://${ASSETS_BUCKET}/${ASSETS_PREFIX}SageMakerUnifiedStudio-VPC.yaml" --region "$AWS_REGION"
aws s3 cp assets/create-smus-iam-roles.yaml \
  "s3://${ASSETS_BUCKET}/${ASSETS_PREFIX}create-smus-iam-roles.yaml" --region "$AWS_REGION"
aws s3 cp assets/create_smus_domain.yaml \
  "s3://${ASSETS_BUCKET}/${ASSETS_PREFIX}create_smus_domain.yaml" --region "$AWS_REGION"
aws s3 cp assets/create_project_profiles.yaml \
  "s3://${ASSETS_BUCKET}/${ASSETS_PREFIX}create_project_profiles.yaml" --region "$AWS_REGION"
aws s3 cp assets/enable_all_blueprints.yaml \
  "s3://${ASSETS_BUCKET}/${ASSETS_PREFIX}enable_all_blueprints.yaml" --region "$AWS_REGION"
aws s3 cp assets/policy_grant.yaml \
  "s3://${ASSETS_BUCKET}/${ASSETS_PREFIX}policy_grant.yaml" --region "$AWS_REGION"

if [[ "$SKIP_IDENTITY_CENTER" == "true" ]]; then
  log "Skipping identity-center.yaml upload (--skip-identity-center)"
else
  aws s3 cp assets/identity-center.yaml \
    "s3://${ASSETS_BUCKET}/${ASSETS_PREFIX}identity-center.yaml" --region "$AWS_REGION"
fi

log "Uploading AI Registry Lambda assets..."
aws s3 sync assets/airegistry/lambda-assets/ \
  "s3://${ASSETS_BUCKET}/${ASSETS_PREFIX}airegistry/lambda-assets/" --region "$AWS_REGION"

log "Uploading AI Registry frontend..."
aws s3 cp assets/airegistry/frontend.zip \
  "s3://${ASSETS_BUCKET}/${ASSETS_PREFIX}airegistry/frontend.zip" --region "$AWS_REGION"

log "Assets upload complete."

# ─── Step 2: Deploy SMUS Platform Stack (Orchestrator) ───────────────────────

log "=== Step 2: Deploying SMUS Platform (VPC, IAM, Identity Center, Domain) ==="
log "This stack takes 15-30 minutes to complete."

DEPLOY_IDC="true"
if [[ "$SKIP_IDENTITY_CENTER" == "true" ]]; then
  DEPLOY_IDC="false"
  log "Identity Center deployment will be SKIPPED."
fi

# Build parameter list
CFN_PARAMS=(
  "ParameterKey=S3AssetsBucket,ParameterValue=$ASSETS_BUCKET"
  "ParameterKey=S3AssetsPrefix,ParameterValue=$ASSETS_PREFIX"
  "ParameterKey=DomainName,ParameterValue=$DOMAIN_NAME"
  "ParameterKey=DeployIdentityCenter,ParameterValue=$DEPLOY_IDC"
  "ParameterKey=VpcCidr,ParameterValue=$VPC_CIDR"
)

if [[ -n "$EXISTING_VPC_ID" ]]; then
  log "Using existing VPC: $EXISTING_VPC_ID"
  CFN_PARAMS+=(
    "ParameterKey=ExistingVpcId,ParameterValue=$EXISTING_VPC_ID"
    "ParameterKey=ExistingPrivateSubnet1Id,ParameterValue=$EXISTING_PRIVATE_SUBNET_1"
    "ParameterKey=ExistingPrivateSubnet2Id,ParameterValue=$EXISTING_PRIVATE_SUBNET_2"
    "ParameterKey=ExistingPrivateSubnet3Id,ParameterValue=$EXISTING_PRIVATE_SUBNET_3"
  )
fi

aws cloudformation create-stack \
  --stack-name "$ORCHESTRATOR_STACK" \
  --template-body file://static/aiops-orchestrator.yaml \
  --parameters "${CFN_PARAMS[@]}" \
  --capabilities CAPABILITY_IAM CAPABILITY_NAMED_IAM CAPABILITY_AUTO_EXPAND \
  --region "$AWS_REGION" \
  --tags Key=Project,Value="$STACK_PREFIX" Key=ManagedBy,Value=deploy-script

wait_for_stack "$ORCHESTRATOR_STACK" "create-complete"
log "SMUS Platform stack deployed successfully."

# Retrieve outputs for reference
DOMAIN_PORTAL_URL=$(aws cloudformation describe-stacks \
  --stack-name "$ORCHESTRATOR_STACK" \
  --region "$AWS_REGION" \
  --query "Stacks[0].Outputs[?OutputKey=='DomainPortalUrl'].OutputValue" \
  --output text 2>/dev/null || echo "N/A")

log "Domain Portal URL: $DOMAIN_PORTAL_URL"

# ─── Step 3: Deploy AI Registry Stack ────────────────────────────────────────

log "=== Step 3: Deploying AI Registry ==="

aws cloudformation create-stack \
  --stack-name "$AIREGISTRY_STACK" \
  --template-body file://static/airegistry.yaml \
  --parameters \
    ParameterKey=S3AssetsBucket,ParameterValue="$ASSETS_BUCKET" \
    ParameterKey=S3AssetsPrefix,ParameterValue="$ASSETS_PREFIX" \
  --capabilities CAPABILITY_IAM CAPABILITY_NAMED_IAM \
  --region "$AWS_REGION" \
  --tags Key=Project,Value="$STACK_PREFIX" Key=ManagedBy,Value=deploy-script

wait_for_stack "$AIREGISTRY_STACK" "create-complete"
log "AI Registry stack deployed successfully."

# ─── Step 4: Deploy Code Editor Stack (Optional) ─────────────────────────────

if [[ "$SKIP_CODE_EDITOR" == "true" ]]; then
  log "=== Step 4: Skipping Code Editor (--skip-code-editor) ==="
else
  log "=== Step 4: Deploying Code Editor IDE ==="
  log "This creates an EC2 instance with CloudFront distribution (~10 min)."

  aws cloudformation create-stack \
    --stack-name "$CODEEDITOR_STACK" \
    --template-body file://static/cfn/code-editor-full.yaml \
    --parameters \
      ParameterKey=HomeFolder,ParameterValue=/project \
      ParameterKey=AssetZipS3Path,ParameterValue="${ASSETS_BUCKET}/${ASSETS_PREFIX}airegistry/frontend.zip" \
    --capabilities CAPABILITY_IAM CAPABILITY_NAMED_IAM \
    --region "$AWS_REGION" \
    --tags Key=Project,Value="$STACK_PREFIX" Key=ManagedBy,Value=deploy-script

  wait_for_stack "$CODEEDITOR_STACK" "create-complete"

  CODE_EDITOR_URL=$(aws cloudformation describe-stacks \
    --stack-name "$CODEEDITOR_STACK" \
    --region "$AWS_REGION" \
    --query "Stacks[0].Outputs[?OutputKey=='URL'].OutputValue" \
    --output text 2>/dev/null || echo "N/A")

  log "Code Editor URL: $CODE_EDITOR_URL"
fi

# ─── Summary ─────────────────────────────────────────────────────────────────

echo ""
log "============================================================"
log "  DEPLOYMENT COMPLETE"
log "============================================================"
echo ""
log "Region:            $AWS_REGION"
log "Domain Portal:     $DOMAIN_PORTAL_URL"
if [[ "$SKIP_CODE_EDITOR" != "true" ]]; then
  log "Code Editor:       ${CODE_EDITOR_URL:-N/A}"
fi
echo ""
log "Stacks deployed:"
log "  - $ORCHESTRATOR_STACK"
log "  - $AIREGISTRY_STACK"
if [[ "$SKIP_CODE_EDITOR" != "true" ]]; then
  log "  - $CODEEDITOR_STACK"
fi
echo ""
log "To tear down all resources:"
log "  ./deploy.sh --teardown --region $AWS_REGION"
echo ""
log "NOTE: The ManageAccessRole in the IAM stack has placeholder values"
log "in its trust policy (REPLACE-REGION-CODE-HERE, etc.). After the domain"
log "is created, you may need to update this role's trust policy with the"
log "actual domain ARN for full functionality. See README for details."
log "============================================================"
