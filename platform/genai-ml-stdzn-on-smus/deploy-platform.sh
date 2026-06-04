#!/bin/bash
set -euo pipefail

###############################################################################
# Self-Deployment Script for SMUS AIOps Platform (Lab 2-3)
#
# This script deploys the MLOps platform stack into your own AWS account by:
#   1. Pulling lambda source code from a public GitHub repository
#   2. Packaging (zipping) the lambdas locally
#   3. Uploading zips + CloudFormation templates to your own S3 bucket
#   4. Deploying the main-stack.yaml via CloudFormation
#
# This approach removes the dependency on pre-built zips in the workshop
# assets folder, making self-deployment reliable and reproducible.
#
# Prerequisites:
#   - AWS CLI v2 configured with credentials (AdministratorAccess recommended)
#   - git installed
#   - zip installed
#   - A GitHub Personal Access Token stored in AWS Secrets Manager
#     (the stack creates the secret shell; you populate it after deployment)
#
# Usage:
#   chmod +x deploy-platform.sh
#   ./deploy-platform.sh
#   ./deploy-platform.sh --region us-west-2
#   ./deploy-platform.sh --github-org my-org
#   ./deploy-platform.sh --teardown
#
###############################################################################

# ─── Configuration ───────────────────────────────────────────────────────────

AWS_REGION="${AWS_REGION:-us-east-1}"
STACK_NAME="${STACK_NAME:-smus-aiops-platform}"
PROJECT_PREFIX="${PROJECT_PREFIX:-smus-aiops}"
TEARDOWN=false

# Public GitHub repo containing lambda source code
PUBLIC_LAMBDA_REPO_ORG="${PUBLIC_LAMBDA_REPO_ORG:-aws-samples}"
PUBLIC_LAMBDA_REPO_NAME="${PUBLIC_LAMBDA_REPO_NAME:-genai-ml-platform-examples}"
PUBLIC_LAMBDA_REPO_BRANCH="${PUBLIC_LAMBDA_REPO_BRANCH:-main}"
PUBLIC_LAMBDA_REPO_PATH="${PUBLIC_LAMBDA_REPO_PATH:-platform/genai-ml-stdzn-on-smus/lambdas}"

# Private GitHub org (where deployment repos will be created by the platform)
PRIVATE_GITHUB_ORG="${PRIVATE_GITHUB_ORG:-}"

# Source seed code configuration
PUBLIC_SEED_ORG="${PUBLIC_SEED_ORG:-aws-samples}"
PUBLIC_SEED_REPO="${PUBLIC_SEED_REPO:-genai-ml-platform-examples}"
PUBLIC_SEED_FOLDER="${PUBLIC_SEED_FOLDER:-platform/genai-ml-stdzn-on-smus/seed-code}"

# OIDC configuration
CREATE_OIDC_PROVIDER="${CREATE_OIDC_PROVIDER:-true}"
EXISTING_OIDC_PROVIDER_ARN="${EXISTING_OIDC_PROVIDER_ARN:-}"

# ─── Parse Arguments ─────────────────────────────────────────────────────────

while [[ $# -gt 0 ]]; do
  case $1 in
    --region)
      AWS_REGION="$2"
      shift 2
      ;;
    --stack-name)
      STACK_NAME="$2"
      shift 2
      ;;
    --project-prefix)
      PROJECT_PREFIX="$2"
      shift 2
      ;;
    --github-org)
      PRIVATE_GITHUB_ORG="$2"
      shift 2
      ;;
    --lambda-repo-org)
      PUBLIC_LAMBDA_REPO_ORG="$2"
      shift 2
      ;;
    --lambda-repo-name)
      PUBLIC_LAMBDA_REPO_NAME="$2"
      shift 2
      ;;
    --lambda-repo-branch)
      PUBLIC_LAMBDA_REPO_BRANCH="$2"
      shift 2
      ;;
    --no-oidc)
      CREATE_OIDC_PROVIDER="false"
      shift
      ;;
    --existing-oidc-arn)
      EXISTING_OIDC_PROVIDER_ARN="$2"
      CREATE_OIDC_PROVIDER="false"
      shift 2
      ;;
    --teardown)
      TEARDOWN=true
      shift
      ;;
    --help|-h)
      echo "Usage: $0 [OPTIONS]"
      echo ""
      echo "Deploys the SMUS AIOps MLOps platform stack by pulling lambda"
      echo "source from a public GitHub repo, packaging, and deploying."
      echo ""
      echo "Options:"
      echo "  --region REGION              AWS region (default: us-east-1)"
      echo "  --stack-name NAME            CloudFormation stack name (default: smus-aiops-platform)"
      echo "  --project-prefix PREFIX      Resource name prefix (default: smus-aiops)"
      echo "  --github-org ORG             Private GitHub org for deployment repos (required)"
      echo "  --lambda-repo-org ORG        Public repo org for lambda source (default: aws-samples)"
      echo "  --lambda-repo-name NAME      Public repo name for lambda source (default: genai-ml-platform-examples)"
      echo "  --lambda-repo-branch BRANCH  Branch to pull from (default: main)"
      echo "  --no-oidc                    Skip creating GitHub OIDC provider"
      echo "  --existing-oidc-arn ARN      Use existing OIDC provider ARN"
      echo "  --teardown                   Delete the stack and clean up"
      echo "  -h, --help                   Show this help message"
      exit 0
      ;;
    *)
      echo "Unknown option: $1"
      exit 1
      ;;
  esac
done

# ─── Validation ──────────────────────────────────────────────────────────────

if [[ "$TEARDOWN" == "false" && -z "$PRIVATE_GITHUB_ORG" ]]; then
  echo "ERROR: --github-org is required. This is the GitHub organization where"
  echo "       deployment repositories will be created by the platform."
  echo ""
  echo "Example: ./deploy-platform.sh --github-org my-org"
  exit 1
fi

# ─── Derived Names ───────────────────────────────────────────────────────────

ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text --region "$AWS_REGION")
ASSETS_BUCKET="${STACK_NAME}-assets-${ACCOUNT_ID}-${AWS_REGION}"
TEMPLATES_PREFIX="templates"
LAMBDA_ASSETS_PREFIX="lambda-assets"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TEMPLATES_DIR="${SCRIPT_DIR}/templates"
WORK_DIR=$(mktemp -d)

# ─── Helper Functions ────────────────────────────────────────────────────────

log() {
  echo "[$(date '+%H:%M:%S')] $*"
}

cleanup() {
  log "Cleaning up temporary directory: $WORK_DIR"
  rm -rf "$WORK_DIR"
}
trap cleanup EXIT

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
  log "=== Tearing down platform stack ==="

  if aws cloudformation describe-stacks --stack-name "$STACK_NAME" --region "$AWS_REGION" &>/dev/null; then
    log "Deleting stack: $STACK_NAME"
    aws cloudformation delete-stack --stack-name "$STACK_NAME" --region "$AWS_REGION"
    aws cloudformation wait stack-delete-complete --stack-name "$STACK_NAME" --region "$AWS_REGION"
    log "Deleted: $STACK_NAME"
  else
    log "Stack not found (skipping): $STACK_NAME"
  fi

  log "Emptying and deleting assets bucket: $ASSETS_BUCKET"
  aws s3 rb "s3://${ASSETS_BUCKET}" --force --region "$AWS_REGION" 2>/dev/null || true

  log "=== Teardown complete ==="
  exit 0
fi

# ─── Pre-flight Checks ──────────────────────────────────────────────────────

log "=== Pre-flight Checks ==="
log "Account ID:       $ACCOUNT_ID"
log "Region:           $AWS_REGION"
log "Stack Name:       $STACK_NAME"
log "Assets Bucket:    $ASSETS_BUCKET"
log "Project Prefix:   $PROJECT_PREFIX"
log "GitHub Org:       $PRIVATE_GITHUB_ORG"
log "Lambda Source:    https://github.com/${PUBLIC_LAMBDA_REPO_ORG}/${PUBLIC_LAMBDA_REPO_NAME} (branch: ${PUBLIC_LAMBDA_REPO_BRANCH})"
log "Create OIDC:      $CREATE_OIDC_PROVIDER"
echo ""

# Verify prerequisites
for cmd in aws git zip; do
  if ! command -v "$cmd" &>/dev/null; then
    log "ERROR: '$cmd' is required but not installed."
    exit 1
  fi
done

if ! aws sts get-caller-identity --region "$AWS_REGION" &>/dev/null; then
  log "ERROR: AWS CLI is not configured or credentials are invalid."
  exit 1
fi

# ─── Step 1: Pull Lambda Source from Public GitHub Repo ──────────────────────

log "=== Step 1: Pulling lambda source from public GitHub repo ==="

REPO_URL="https://github.com/${PUBLIC_LAMBDA_REPO_ORG}/${PUBLIC_LAMBDA_REPO_NAME}.git"
CLONE_DIR="${WORK_DIR}/source"

log "Cloning ${REPO_URL} (branch: ${PUBLIC_LAMBDA_REPO_BRANCH})..."
git clone --depth 1 --branch "$PUBLIC_LAMBDA_REPO_BRANCH" "$REPO_URL" "$CLONE_DIR"

LAMBDA_SRC_DIR="${CLONE_DIR}/${PUBLIC_LAMBDA_REPO_PATH}"

if [[ ! -d "$LAMBDA_SRC_DIR" ]]; then
  log "ERROR: Lambda source directory not found at '${PUBLIC_LAMBDA_REPO_PATH}' in the repo."
  log "Expected structure:"
  log "  ${PUBLIC_LAMBDA_REPO_PATH}/check-project-status/index.py"
  log "  ${PUBLIC_LAMBDA_REPO_PATH}/create-deploy-repository/index.py"
  log "  ${PUBLIC_LAMBDA_REPO_PATH}/sync-repositories/index.py"
  log "  ${PUBLIC_LAMBDA_REPO_PATH}/model-approval/deploy_on_model_approval.py"
  log "  ${PUBLIC_LAMBDA_REPO_PATH}/layers/dependency-layer.zip"
  log "  ${PUBLIC_LAMBDA_REPO_PATH}/layers/git-layer.zip"
  exit 1
fi

log "Lambda source pulled successfully."

# ─── Step 2: Package Lambda Functions ────────────────────────────────────────

log "=== Step 2: Packaging lambda functions ==="

PACKAGE_DIR="${WORK_DIR}/packages"
mkdir -p "$PACKAGE_DIR"

# Package each lambda function
package_lambda() {
  local src_dir="$1"
  local zip_name="$2"

  if [[ ! -d "$src_dir" ]]; then
    log "ERROR: Source directory not found: $src_dir"
    exit 1
  fi

  log "  Packaging: $zip_name"
  (cd "$src_dir" && zip -r "${PACKAGE_DIR}/${zip_name}" . -x '*.pyc' '__pycache__/*' '.git/*')
}

package_lambda "${LAMBDA_SRC_DIR}/check-project-status" "check-project-status-function.zip"
package_lambda "${LAMBDA_SRC_DIR}/create-deploy-repository" "create-deploy-repository-function.zip"
package_lambda "${LAMBDA_SRC_DIR}/sync-repositories" "sync-repositories-function.zip"
package_lambda "${LAMBDA_SRC_DIR}/model-approval" "model-approval-function.zip"

# Copy pre-built layers
LAYERS_DIR="${LAMBDA_SRC_DIR}/layers"

# Dependency layer (pre-built zip containing boto3, requests, s3transfer, etc.)
if [[ -f "${LAYERS_DIR}/dependency-layer.zip" ]]; then
  log "  Copying pre-built dependency-layer.zip..."
  cp "${LAYERS_DIR}/dependency-layer.zip" "${PACKAGE_DIR}/"
elif [[ -f "${LAYERS_DIR}/dependency-layer/dependency-layer.zip" ]]; then
  log "  Copying pre-built dependency-layer.zip..."
  cp "${LAYERS_DIR}/dependency-layer/dependency-layer.zip" "${PACKAGE_DIR}/"
else
  log "ERROR: dependency-layer.zip not found in the public repo."
  log "Expected at: ${LAYERS_DIR}/dependency-layer.zip"
  log "         or: ${LAYERS_DIR}/dependency-layer/dependency-layer.zip"
  exit 1
fi

# Git layer (pre-built binary — provides git for Lambda)
if [[ -f "${LAYERS_DIR}/git-layer.zip" ]]; then
  log "  Copying pre-built git-layer.zip..."
  cp "${LAYERS_DIR}/git-layer.zip" "${PACKAGE_DIR}/"
elif [[ -f "${LAYERS_DIR}/git-layer/git-layer.zip" ]]; then
  log "  Copying pre-built git-layer.zip..."
  cp "${LAYERS_DIR}/git-layer/git-layer.zip" "${PACKAGE_DIR}/"
else
  log "ERROR: git-layer.zip not found in the public repo."
  log "Expected at: ${LAYERS_DIR}/git-layer.zip"
  log "         or: ${LAYERS_DIR}/git-layer/git-layer.zip"
  exit 1
fi

log "All lambda packages created:"
ls -lh "$PACKAGE_DIR"

# ─── Step 3: Create S3 Bucket and Upload Assets ─────────────────────────────

log "=== Step 3: Setting up S3 assets bucket and uploading ==="

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

# Upload lambda packages
log "Uploading lambda packages..."
aws s3 sync "$PACKAGE_DIR/" "s3://${ASSETS_BUCKET}/${LAMBDA_ASSETS_PREFIX}/" --region "$AWS_REGION"

# Upload CloudFormation templates
log "Uploading CloudFormation templates..."
aws s3 sync "$TEMPLATES_DIR/" "s3://${ASSETS_BUCKET}/${TEMPLATES_PREFIX}/" \
  --region "$AWS_REGION" \
  --include "*.yaml"

log "All assets uploaded to s3://${ASSETS_BUCKET}/"

# ─── Step 4: Deploy CloudFormation Stack ─────────────────────────────────────

log "=== Step 4: Deploying CloudFormation stack ==="

CFN_PARAMS=(
  "ParameterKey=ProjectPrefix,ParameterValue=${PROJECT_PREFIX}"
  "ParameterKey=AssetsBucket,ParameterValue=${ASSETS_BUCKET}"
  "ParameterKey=TemplateS3KeyPrefix,ParameterValue=${TEMPLATES_PREFIX}"
  "ParameterKey=LambdaAssetsKeyPrefix,ParameterValue=${LAMBDA_ASSETS_PREFIX}"
  "ParameterKey=PrivateGitHubOrganization,ParameterValue=${PRIVATE_GITHUB_ORG}"
  "ParameterKey=PublicSmusAiopsOrg,ParameterValue=${PUBLIC_SEED_ORG}"
  "ParameterKey=PublicSmusAiopsOrgRepo,ParameterValue=${PUBLIC_SEED_REPO}"
  "ParameterKey=PublicSmusAiopsOrgRepoFolder,ParameterValue=${PUBLIC_SEED_FOLDER}"
  "ParameterKey=CreateOidcProvider,ParameterValue=${CREATE_OIDC_PROVIDER}"
)

if [[ -n "$EXISTING_OIDC_PROVIDER_ARN" ]]; then
  CFN_PARAMS+=("ParameterKey=ExistingOidcProviderArn,ParameterValue=${EXISTING_OIDC_PROVIDER_ARN}")
fi

# Check if stack already exists
if aws cloudformation describe-stacks --stack-name "$STACK_NAME" --region "$AWS_REGION" &>/dev/null; then
  log "Stack exists. Updating..."
  aws cloudformation update-stack \
    --stack-name "$STACK_NAME" \
    --template-url "https://${ASSETS_BUCKET}.s3.${AWS_REGION}.amazonaws.com/${TEMPLATES_PREFIX}/main-stack.yaml" \
    --parameters "${CFN_PARAMS[@]}" \
    --capabilities CAPABILITY_IAM CAPABILITY_NAMED_IAM CAPABILITY_AUTO_EXPAND \
    --region "$AWS_REGION" \
    --tags Key=Project,Value="$PROJECT_PREFIX" Key=ManagedBy,Value=deploy-platform-script

  wait_for_stack "$STACK_NAME" "update-complete"
else
  log "Creating new stack..."
  aws cloudformation create-stack \
    --stack-name "$STACK_NAME" \
    --template-url "https://${ASSETS_BUCKET}.s3.${AWS_REGION}.amazonaws.com/${TEMPLATES_PREFIX}/main-stack.yaml" \
    --parameters "${CFN_PARAMS[@]}" \
    --capabilities CAPABILITY_IAM CAPABILITY_NAMED_IAM CAPABILITY_AUTO_EXPAND \
    --region "$AWS_REGION" \
    --tags Key=Project,Value="$PROJECT_PREFIX" Key=ManagedBy,Value=deploy-platform-script

  wait_for_stack "$STACK_NAME" "create-complete"
fi

# ─── Summary ─────────────────────────────────────────────────────────────────

log ""
log "============================================================"
log "  PLATFORM DEPLOYMENT COMPLETE"
log "============================================================"
log ""
log "Region:              $AWS_REGION"
log "Stack Name:          $STACK_NAME"
log "Assets Bucket:       $ASSETS_BUCKET"
log "GitHub Org:          $PRIVATE_GITHUB_ORG"
log ""
log "IMPORTANT: Next Steps"
log "  1. Store your GitHub Personal Access Token in Secrets Manager."
log "     The secret name can be found in the stack outputs:"
log ""
log "     SECRET_NAME=\$(aws cloudformation describe-stacks \\"
log "       --stack-name $STACK_NAME --region $AWS_REGION \\"
log "       --query \"Stacks[0].Outputs[?OutputKey=='GitHubTokenSecretName'].OutputValue\" \\"
log "       --output text)"
log ""
log "     aws secretsmanager put-secret-value \\"
log "       --secret-id \$SECRET_NAME \\"
log "       --secret-string '{\"github_token\":\"ghp_YOUR_TOKEN_HERE\"}' \\"
log "       --region $AWS_REGION"
log ""
log "  2. Verify the stack outputs:"
log "     aws cloudformation describe-stacks --stack-name $STACK_NAME \\"
log "       --region $AWS_REGION --query 'Stacks[0].Outputs'"
log ""
log "To tear down:"
log "  ./deploy-platform.sh --teardown --region $AWS_REGION"
log "============================================================"
