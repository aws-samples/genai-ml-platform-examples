#!/usr/bin/env bash
#
# deploy-workshop.sh
#
# Deploy the GenAI/ML Standardization workshop as SIX INDEPENDENT CloudFormation
# stacks, in dependency order, runnable from AWS CloudShell:
#
#   <prefix>-networking         1-networking.yaml
#   <prefix>-iam                2-iam.yaml
#   <prefix>-sagemaker          3-sagemaker.yaml
#   <prefix>-inference-capture  4-inference-capture.yaml
#   <prefix>-data-prep          5-data-prep.yaml
#   <prefix>-okta-federation    6-okta-federation.yaml   (opt-in, Lab 1D)
#
# This script is the ONLY supported way to deploy the workshop.
#
# templates/main.yaml is DEPRECATED
# ---------------------------------
# The workshop used to deploy as one parent stack (main.yaml) with the above as
# nested stacks. main.yaml is retained only so an existing parent stack can
# still be torn down with the template that created it; it is no longer
# deployed, updated, or tested. Do not add resources to it.
#
# Why the change:
#   * Nested stacks required child templates in S3 under URLs the PARENT built,
#     and child edits were invisible to CloudFormation unless the object key
#     changed -- so the script hashed the whole template set into the S3 key
#     prefix to force updates. That hand-rolled upload-and-hash plumbing is
#     gone. Templates are still STAGED in S3 (see TEMPLATE_BUCKET: the CLI
#     requires it above 51,200 bytes, and 2-iam.yaml is ~87 KB), but the CLI
#     does the upload and content-addressed keying itself.
#   * A failure in one nested stack rolled back the whole parent. Independent
#     stacks fail and retry in isolation.
#   * Nested stacks get generated names, so their Fn::ImportValue exports
#     (${AWS::StackName}-...) were unpredictable. Fixed stack names make them
#     usable.
#
# MIGRATING AN EXISTING DEPLOYMENT
# --------------------------------
# There is no in-place migration. Resources in a legacy parent stack are owned
# by its nested stacks, and CloudFormation has no knowledge of them here, so a
# fresh deploy collides on every fixed-name resource (IAM roles, the data
# bucket, the SageMaker domain, the 'bank_marketing' Glue database) with
# AlreadyExists. Tear the old deployment down first:
#
#   scripts/teardown-workshop.sh          # thorough: unblocks the VpcOnly VPC
#
# That DESTROYS the data bucket and its contents, including participant work.
# Export anything you need first. This script detects a legacy parent stack and
# refuses to deploy over it.
#
# What it does:
#   1. Locates the templates (local dir, or clones a public git repo).
#   2. Deploys the stacks above in order, waiting for each to finish.
#   3. Threads outputs between them: the SageMaker stack's data bucket and the
#      IAM stack's execution-role names become parameters of later stacks --
#      the job main.yaml used to do with !GetAtt.
#   4. Prints the aggregated outputs.
#
# Usage (CloudShell):
#   # Option A - run from a clone of the repo:
#   git clone <REPO_URL> && cd genai-ml-standardization
#   ./scripts/deploy-workshop.sh
#
#   # Option B - run standalone, let the script clone:
#   REPO_URL=https://github.com/<org>/<repo>.git ./scripts/deploy-workshop.sh
#
# Requires AWS CLI v2 (CloudShell default): stack parameters are passed as a
# JSON file, so values containing commas, spaces, or XML survive intact.
#
# Common overrides (environment variables):
#   REPO_URL        Public git URL to clone (default: use local ./templates if present)
#   REPO_BRANCH     Branch to clone (default: main)
#   TEMPLATE_DIR    Path to a local templates dir (skips git clone)
#   PROJECT_NAME    Workshop project name, lowercase (default: bank-marketing-prediction)
#                   Must match ^[a-z0-9-]+$ (lowercase letters, digits, hyphens).
#   STACK_PREFIX    Prefix for the six stack names (default: <PROJECT_NAME>)
#   TEMPLATE_BUCKET S3 bucket used to stage templates for deployment
#                   (default: <PROJECT_NAME>-cfn-<acct>-<region>). Required
#                   because `aws cloudformation deploy` only accepts templates
#                   under 51,200 bytes inline, and 2-iam.yaml is ~87 KB. The CLI
#                   uploads and keys the objects itself; nothing is built by hand.
#   S3_PREFIX       Key prefix inside TEMPLATE_BUCKET (default: genai-ml-std-assets)
#   AWS_REGION      Target region (default: CloudShell's region)
#   ONLY_STACKS     Space/comma list limiting which stacks to deploy, by short
#                   name: networking iam sagemaker inference-capture data-prep
#                   okta-federation. Default: all (okta only when enabled).
#                   Dependency outputs are read from already-deployed stacks, so
#                   a partial deploy requires its prerequisites to exist.
#   VPC_CIDR             VPC CIDR (default: 10.1.0.0/16)              -> VpcCIDR
#   PRIVATE_SUBNET_CIDR  Private subnet 1 CIDR (default: 10.1.1.0/24) -> PrivateSubnetCIDR
#   PRIVATE_SUBNET2_CIDR Private subnet 2 CIDR (default: 10.1.2.0/24) -> PrivateSubnet2CIDR
#   PUBLIC_SUBNET_CIDR   Public subnet CIDR (default: 10.1.3.0/24)    -> PublicSubnetCIDR
#   JUPYTERLAB_APP_INSTANCE JupyterLab instance type (default: ml.m5.2xlarge)
#   USER_A_PROFILE_NAME  First user profile name (default: userA)
#   USER_B_PROFILE_NAME  Second user profile name (default: userB)
#   SEED_CODE_TYPE       llm-fine-tuning | classification
#                        (default: classification)
#   EMR_RELEASE_LABEL    EMR release for Lab 2 data prep (default: emr-7.5.0)
#   CREATE_SC_ROLES 'auto', 'true', or 'false' - create the AWS SageMaker
#                   Service Catalog / Projects product roles. These have fixed,
#                   account-global names and can be owned by only ONE stack per
#                   account. 'auto' (default) checks whether they already exist
#                   and passes 'false' if so (reuse) or 'true' if not (create),
#                   avoiding "Validation failed" AlreadyExists collisions.
#   ENABLE_OKTA_FEDERATION
#                   'false' (default) or 'true' - deploy 6-okta-federation.yaml
#                   (Lab 1D: SAML provider, federation role, tag-gated Studio
#                   access policy). Requires OKTA_METADATA_FILE.
#   OKTA_METADATA_FILE
#                   Path to the SAML 2.0 metadata XML downloaded from your Okta
#                   tenant (Sign On tab -> View IdP metadata). Read from a FILE
#                   rather than an inline variable: the XML is multi-line, and
#                   an inline value would also land in your shell history.
#   OKTA_PROVIDER_NAME
#                   IAM SAML provider name (default: okta). The provider name is
#                   account-global, so change it if one named 'okta' already
#                   exists and is owned by something else.
#   ENSURE_LF_IAM_DEFAULT
#                   'true' (default) or 'false' - before deploying, ensure Lake
#                   Formation's CreateDatabase/CreateTable default permissions
#                   include IAM_ALLOWED_PRINCIPALS so IAM-based Glue access works
#                   for the inference-capture Iceberg table. Best-effort: warns
#                   (does not fail) if the caller lacks LF admin rights.
#   SUBSCRIBE_QUICKSIGHT
#                   'false' (default) or 'true' - sign the account up for
#                   QuickSight, which Lab 5E's governance dashboard requires.
#                   OFF by default because it creates a BILLABLE subscription
#                   and fixes the QuickSight account name and identity region
#                   permanently. Requires QUICKSIGHT_NOTIFICATION_EMAIL.
#                   Already-subscribed accounts are detected and left alone.
#   QUICKSIGHT_NOTIFICATION_EMAIL
#                   Email for QuickSight service notifications. Required only
#                   when SUBSCRIBE_QUICKSIGHT=true.
#   QUICKSIGHT_IDENTITY_REGION
#                   Region QuickSight is subscribed in (default: us-east-1).
#                   QuickSight allows ONE per account and it cannot be changed
#                   later; it must match lab5-monitoring's config of the same
#                   name. All QuickSight admin/user API calls go to this region.
#                   If the default is wrong, the script DETECTS the real region
#                   (AWS names it in the error) and uses it for this run, then
#                   tells you to set it for Lab 5E, which reads its own config.
#   QUICKSIGHT_EDITION
#                   ENTERPRISE (default) or STANDARD. Lab 5E builds its
#                   dashboard with the Definition API, which needs ENTERPRISE.
#   QUICKSIGHT_ACCOUNT_NAME
#                   QuickSight account name (default: <PROJECT_NAME>-<acct>).
#   VERIFY_QUICKSIGHT_IAM
#                   'true' (default) or 'false' - after deploying, confirm the
#                   execution roles really carry the QuickSightGovernanceDashboard
#                   actions Lab 5E needs (2-iam.yaml). Best-effort: warns only.
#   SKIP_QS_POLICY  'false' (default) or 'true' - force
#                   AttachQuickSightServiceRolePolicy=false even when the
#                   QuickSight service role exists, skipping the workshop's
#                   QuickSight service-role policies. The policy names are now
#                   project-scoped (${PROJECT_NAME}-QuickSightS3DataLakeAccess /
#                   -QuickSightAthenaAccess), so cross-project collisions on the
#                   account-global role should no longer occur; keep this as a
#                   manual escape hatch (e.g. two deploys sharing a ProjectName).
#   ALLOW_LEGACY_STACK
#                   'false' (default) or 'true' - proceed even when a legacy
#                   main.yaml parent stack is detected. Only set this if you
#                   know the parent no longer owns the colliding resources.
#   TEARDOWN        If 'true', delete the six stacks in reverse order. For a
#                   thorough teardown that also empties buckets and unblocks the
#                   VpcOnly VPC, use scripts/teardown-workshop.sh instead.
#
set -euo pipefail

# Directory this script lives in, so it can locate ../templates regardless of
# the current working directory it is invoked from.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# ------------------------------------------------------------------ config ---
REPO_URL="${REPO_URL:-}"
REPO_BRANCH="${REPO_BRANCH:-main}"
TEMPLATE_DIR="${TEMPLATE_DIR:-}"
PROJECT_NAME="${PROJECT_NAME:-smai-genai-ml-std}"
STACK_PREFIX="${STACK_PREFIX:-${PROJECT_NAME}}"
ONLY_STACKS="${ONLY_STACKS:-}"
# Key prefix for the staged templates. No content hash needed: `aws
# cloudformation deploy` names each uploaded object after the template's own
# hash, so an edited template lands on a new key automatically.
S3_PREFIX="${S3_PREFIX:-genai-ml-std-assets}"
CREATE_SC_ROLES="${CREATE_SC_ROLES:-auto}"
ENABLE_OKTA_FEDERATION="${ENABLE_OKTA_FEDERATION:-false}"
OKTA_METADATA_FILE="${OKTA_METADATA_FILE:-}"
OKTA_PROVIDER_NAME="${OKTA_PROVIDER_NAME:-okta}"
ENSURE_LF_IAM_DEFAULT="${ENSURE_LF_IAM_DEFAULT:-true}"
VERIFY_QUICKSIGHT_IAM="${VERIFY_QUICKSIGHT_IAM:-true}"
SUBSCRIBE_QUICKSIGHT="${SUBSCRIBE_QUICKSIGHT:-false}"
QUICKSIGHT_NOTIFICATION_EMAIL="${QUICKSIGHT_NOTIFICATION_EMAIL:-}"
QUICKSIGHT_IDENTITY_REGION="${QUICKSIGHT_IDENTITY_REGION:-}"
QUICKSIGHT_EDITION="${QUICKSIGHT_EDITION:-ENTERPRISE}"
ALLOW_LEGACY_STACK="${ALLOW_LEGACY_STACK:-false}"
TEARDOWN="${TEARDOWN:-false}"

# Legacy main.yaml parent stack. Only used for detection and teardown; nothing
# is deployed to it. STACK_NAME was this script's parent-stack variable before
# the split, so it is still honored for that purpose.
LEGACY_STACK_NAME="${STACK_NAME:-${PROJECT_NAME}-workshop}"

# ---- Pass-through stack parameters -----------------------------------------
VPC_CIDR="${VPC_CIDR:-10.1.0.0/16}"
PRIVATE_SUBNET_CIDR="${PRIVATE_SUBNET_CIDR:-10.1.1.0/24}"
PRIVATE_SUBNET2_CIDR="${PRIVATE_SUBNET2_CIDR:-10.1.2.0/24}"
PUBLIC_SUBNET_CIDR="${PUBLIC_SUBNET_CIDR:-10.1.3.0/24}"
JUPYTERLAB_APP_INSTANCE="${JUPYTERLAB_APP_INSTANCE:-ml.m5.2xlarge}"
USER_A_PROFILE_NAME="${USER_A_PROFILE_NAME:-userA}"
USER_B_PROFILE_NAME="${USER_B_PROFILE_NAME:-userB}"
# 3-sagemaker.yaml SeedCodeType AllowedValues: llm-fine-tuning | classification
SEED_CODE_TYPE="${SEED_CODE_TYPE:-classification}"
# EMR release for the Lab 2 data-prep EMR Serverless app / EMR on EC2 clusters.
EMR_RELEASE_LABEL="${EMR_RELEASE_LABEL:-emr-7.5.0}"

# ---- Stack names, in dependency order --------------------------------------
NETWORKING_STACK="${STACK_PREFIX}-networking"
IAM_STACK="${STACK_PREFIX}-iam"
SAGEMAKER_STACK="${STACK_PREFIX}-sagemaker"
INFERENCE_STACK="${STACK_PREFIX}-inference-capture"
DATA_PREP_STACK="${STACK_PREFIX}-data-prep"
OKTA_STACK="${STACK_PREFIX}-okta-federation"

# Short name -> template file. Deploy order is the array order below.
STACK_ORDER=(networking iam sagemaker inference-capture data-prep okta-federation)
template_for() {
  case "$1" in
    networking)        echo 1-networking.yaml ;;
    iam)               echo 2-iam.yaml ;;
    sagemaker)         echo 3-sagemaker.yaml ;;
    inference-capture) echo 4-inference-capture.yaml ;;
    data-prep)         echo 5-data-prep.yaml ;;
    okta-federation)   echo 6-okta-federation.yaml ;;
    *) return 1 ;;
  esac
}
stack_name_for() {
  case "$1" in
    networking)        echo "${NETWORKING_STACK}" ;;
    iam)               echo "${IAM_STACK}" ;;
    sagemaker)         echo "${SAGEMAKER_STACK}" ;;
    inference-capture) echo "${INFERENCE_STACK}" ;;
    data-prep)         echo "${DATA_PREP_STACK}" ;;
    okta-federation)   echo "${OKTA_STACK}" ;;
    *) return 1 ;;
  esac
}

log()  { printf '\033[1;34m[deploy]\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m[warn]\033[0m %s\n'  "$*" >&2; }
die()  { printf '\033[1;31m[error]\033[0m %s\n' "$*" >&2; exit 1; }

# ------------------------------------------------------------- prereqs -------
command -v aws >/dev/null 2>&1 || die "aws CLI not found (CloudShell has it by default)."
command -v python3 >/dev/null 2>&1 || die "python3 not found (used to build stack parameter files)."

# Resolve region: explicit AWS_REGION, else CLI default, else CloudShell env.
REGION="${AWS_REGION:-${AWS_DEFAULT_REGION:-$(aws configure get region 2>/dev/null || true)}}"
[ -n "${REGION}" ] || die "Could not determine AWS region. Set AWS_REGION."
export AWS_DEFAULT_REGION="${REGION}"

ACCOUNT_ID="$(aws sts get-caller-identity --query Account --output text)" \
  || die "Unable to call STS. Are credentials configured?"

QUICKSIGHT_ACCOUNT_NAME="${QUICKSIGHT_ACCOUNT_NAME:-${PROJECT_NAME}-${ACCOUNT_ID}}"
# Defaults that need ACCOUNT_ID, so they are resolved after the STS call.
TEMPLATE_BUCKET="${TEMPLATE_BUCKET:-${PROJECT_NAME}-cfn-${ACCOUNT_ID}-${REGION}}"

# ProjectName must be lowercase letters, digits, and hyphens.
if ! printf '%s' "${PROJECT_NAME}" | grep -Eq '^[a-z0-9-]+$'; then
  die "PROJECT_NAME='${PROJECT_NAME}' is invalid. Use lowercase letters, digits, and hyphens only (e.g. bank-marketing-mlops-project)."
fi

# ------------------------------------------------- which stacks to deploy ----
# Normalize ONLY_STACKS (commas or spaces) and validate each entry.
SELECTED=()
if [ -n "${ONLY_STACKS}" ]; then
  for s in $(printf '%s' "${ONLY_STACKS}" | tr ',' ' '); do
    template_for "${s}" >/dev/null 2>&1 || die "ONLY_STACKS: unknown stack '${s}'. Valid: ${STACK_ORDER[*]}"
    SELECTED+=("${s}")
  done
else
  for s in "${STACK_ORDER[@]}"; do
    # Okta is opt-in: skip it unless explicitly enabled.
    if [ "${s}" = "okta-federation" ] && [ "${ENABLE_OKTA_FEDERATION}" != "true" ]; then
      continue
    fi
    SELECTED+=("${s}")
  done
fi

is_selected() {
  local want="$1" s
  for s in "${SELECTED[@]}"; do [ "${s}" = "${want}" ] && return 0; done
  return 1
}

log "Account:        ${ACCOUNT_ID}"
log "Region:         ${REGION}"
log "Project name:   ${PROJECT_NAME}"
log "Stack prefix:   ${STACK_PREFIX}"
log "Stacks:         ${SELECTED[*]}"
log "Template stage: s3://${TEMPLATE_BUCKET}/${S3_PREFIX}/"
log "Seed code type: ${SEED_CODE_TYPE}"
log "JupyterLab:     ${JUPYTERLAB_APP_INSTANCE}"
log "VPC CIDR:       ${VPC_CIDR} (priv ${PRIVATE_SUBNET_CIDR}, priv2 ${PRIVATE_SUBNET2_CIDR}, pub ${PUBLIC_SUBNET_CIDR})"
log "User profiles:  ${USER_A_PROFILE_NAME}, ${USER_B_PROFILE_NAME}"

# ------------------------------------------------------- stack helpers -------
stack_exists() {
  aws cloudformation describe-stacks --stack-name "$1" >/dev/null 2>&1
}

# Read one output value from a deployed stack. Empty string when absent.
stack_output() {
  local value
  value="$(aws cloudformation describe-stacks --stack-name "$1" \
    --query "Stacks[0].Outputs[?OutputKey=='$2'].OutputValue" \
    --output text 2>/dev/null || true)"
  [ "${value}" = "None" ] && value=""
  printf '%s' "${value}"
}

# Same, but fail loudly: a missing output means a later stack would be deployed
# with a wrong or derived default, which is how the pre-split deployments ended
# up pointing at a nonexistent sagemaker-<region>-<account> bucket.
require_output() {
  local stack="$1" key="$2" value
  value="$(stack_output "${stack}" "${key}")"
  if [ -z "${value}" ]; then
    stack_exists "${stack}" \
      || die "Stack ${stack} does not exist, so its output ${key} cannot be read. Deploy it first (ONLY_STACKS can target a subset)."
    die "Stack ${stack} has no output '${key}'. Cannot continue safely."
  fi
  printf '%s' "${value}"
}

# Build a CloudFormation parameters JSON file from Key=Value arguments.
# A JSON file (rather than Key=Value shorthand) keeps commas, spaces, and
# multi-line XML intact -- EndpointExecutionRoleNames is comma-delimited and
# OktaMetadataDocument is a multi-line document.
PARAM_FILE=""
write_param_file() {
  PARAM_FILE="$(mktemp)"
  python3 - "${PARAM_FILE}" "$@" <<'PY'
import json
import sys

out_path = sys.argv[1]
params = []
for pair in sys.argv[2:]:
    key, sep, value = pair.partition("=")
    if not sep:
        raise SystemExit(f"parameter override is not Key=Value: {pair!r}")
    if value.startswith("@"):          # @/path/to/file -> file contents
        with open(value[1:], encoding="utf-8") as handle:
            value = handle.read()
    params.append({"ParameterKey": key, "ParameterValue": value})
with open(out_path, "w", encoding="utf-8") as handle:
    json.dump(params, handle)
PY
}

TMP_FILES=()
cleanup_tmp() {
  local f
  for f in "${TMP_FILES[@]:-}"; do [ -n "${f}" ] && rm -f "${f}"; done
}

# `aws cloudformation deploy` sends the template inline unless --s3-bucket is
# given, and inline templates are capped at 51,200 bytes. 2-iam.yaml is ~87 KB,
# so staging is mandatory, not an optimization. Passing --s3-bucket for every
# stack keeps one code path and means a template crossing the limit later (5-
# data-prep is already at ~35 KB) does not suddenly break the deploy.
ensure_template_bucket() {
  if aws s3api head-bucket --bucket "${TEMPLATE_BUCKET}" >/dev/null 2>&1; then
    log "Reusing template staging bucket ${TEMPLATE_BUCKET}"
    return 0
  fi
  log "Creating template staging bucket ${TEMPLATE_BUCKET} in ${REGION}"
  # 'aws s3 mb' handles the us-east-1 vs other-region LocationConstraint quirk.
  aws s3 mb "s3://${TEMPLATE_BUCKET}" --region "${REGION}" \
    || die "Could not create the template staging bucket ${TEMPLATE_BUCKET}.
  Templates over 51,200 bytes (2-iam.yaml is ~87 KB) cannot be deployed without
  it. Set TEMPLATE_BUCKET to a bucket you can write to in ${REGION}."
  aws s3api put-public-access-block --bucket "${TEMPLATE_BUCKET}" \
    --public-access-block-configuration \
    BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true \
    || warn "Could not set the public-access block on ${TEMPLATE_BUCKET}; check it manually."
}

deploy_stack() {
  local short="$1"; shift
  local name template
  name="$(stack_name_for "${short}")"
  template="$(template_for "${short}")"

  write_param_file "$@"
  TMP_FILES+=("${PARAM_FILE}")

  log "  -> ${name}  (${template})"
  # CAPABILITY_NAMED_IAM: the templates create fixed-name IAM roles.
  # CAPABILITY_AUTO_EXPAND is no longer needed -- it was for nested stacks.
  aws cloudformation deploy \
    --stack-name "${name}" \
    --template-file "${TEMPLATE_DIR}/${template}" \
    --s3-bucket "${TEMPLATE_BUCKET}" \
    --s3-prefix "${S3_PREFIX}" \
    --capabilities CAPABILITY_NAMED_IAM \
    --parameter-overrides "file://${PARAM_FILE}" \
    --tags "WorkshopProject=${PROJECT_NAME}" "deployed-by=deploy-workshop.sh" \
    --no-fail-on-empty-changeset \
    || die "Stack ${name} failed. Inspect it with:
    aws cloudformation describe-stack-events --stack-name ${name} \\
      --query \"StackEvents[?ResourceStatus=='CREATE_FAILED' || ResourceStatus=='UPDATE_FAILED'].[LogicalResourceId,ResourceStatusReason]\" --output table
  Fix the cause and re-run; stacks already deployed are left untouched."

  rm -f "${PARAM_FILE}"
}

# -------------------------------------------------------------- teardown -----
if [ "${TEARDOWN}" = "true" ]; then
  log "Deleting the workshop stacks in reverse dependency order ..."
  log "(For a thorough teardown -- empties buckets, deletes Studio apps, unblocks"
  log " the VpcOnly VPC -- use scripts/teardown-workshop.sh instead.)"

  # Reverse of STACK_ORDER.
  for (( idx=${#STACK_ORDER[@]}-1; idx>=0; idx-- )); do
    short="${STACK_ORDER[idx]}"
    name="$(stack_name_for "${short}")"
    if stack_exists "${name}"; then
      log "  deleting ${name} ..."
      aws cloudformation delete-stack --stack-name "${name}"
      aws cloudformation wait stack-delete-complete --stack-name "${name}" 2>/dev/null \
        || warn "  ${name} did not delete cleanly; check its events."
    else
      log "  ${name} not present, skipping"
    fi
  done

  if stack_exists "${LEGACY_STACK_NAME}"; then
    warn "A legacy main.yaml parent stack '${LEGACY_STACK_NAME}' still exists and was NOT deleted."
    warn "It owns its own copies of the workshop resources. Delete it with:"
    warn "  scripts/teardown-workshop.sh      # handles the VpcOnly EFS/SG blockers"
  fi

  log "Teardown complete."
  exit 0
fi

# ---------------------------------------------------- obtain templates -------
WORKDIR=""
cleanup() { cleanup_tmp; [ -n "${WORKDIR}" ] && rm -rf "${WORKDIR}" || true; }
trap cleanup EXIT

if [ -z "${TEMPLATE_DIR}" ]; then
  if [ -f "templates/1-networking.yaml" ]; then
    TEMPLATE_DIR="templates"
    log "Using local templates directory: ${TEMPLATE_DIR}"
  elif [ -f "${SCRIPT_DIR}/../templates/1-networking.yaml" ]; then
    TEMPLATE_DIR="$(cd "${SCRIPT_DIR}/../templates" && pwd)"
    log "Using templates directory relative to script: ${TEMPLATE_DIR}"
  elif [ -n "${REPO_URL}" ]; then
    command -v git >/dev/null 2>&1 || die "git not found and no local templates dir."
    WORKDIR="$(mktemp -d)"
    log "Cloning ${REPO_URL} (branch ${REPO_BRANCH}) ..."
    git clone --depth 1 --branch "${REPO_BRANCH}" "${REPO_URL}" "${WORKDIR}/repo"
    TEMPLATE_DIR="${WORKDIR}/repo/templates"
  else
    die "No templates found. Run from the repo root, or set REPO_URL or TEMPLATE_DIR."
  fi
fi

# Only the templates actually being deployed need to be present.
for s in "${SELECTED[@]}"; do
  t="$(template_for "${s}")"
  [ -f "${TEMPLATE_DIR}/${t}" ] || die "Template missing: ${TEMPLATE_DIR}/${t}"
done

# --------------------------------------------- refuse to deploy over legacy --
# A legacy parent stack still owns fixed-name resources (IAM roles, the data
# bucket, the SageMaker domain, the Glue database). Deploying standalone stacks
# alongside it fails on AlreadyExists partway through, leaving a half-built
# deployment, so stop before touching anything.
if stack_exists "${LEGACY_STACK_NAME}"; then
  if [ "${ALLOW_LEGACY_STACK}" = "true" ]; then
    warn "Legacy parent stack '${LEGACY_STACK_NAME}' exists; continuing because ALLOW_LEGACY_STACK=true."
    warn "Expect AlreadyExists failures on any resource it still owns."
  else
    die "Legacy parent stack '${LEGACY_STACK_NAME}' exists (deployed from the now-deprecated
  templates/main.yaml). Its nested stacks own the IAM roles, data bucket,
  SageMaker domain, and Glue database this deploy would create, so deploying
  now would fail partway through on AlreadyExists.

  Tear the old deployment down first:
      scripts/teardown-workshop.sh
  That DESTROYS the data bucket and its contents -- export anything you need.

  To proceed anyway (only if the parent no longer owns the colliding
  resources), re-run with ALLOW_LEGACY_STACK=true."
  fi
fi

# --------------------------------------------- resolve CreateServiceCatalogRoles
# 2-iam.yaml optionally creates the AWS SageMaker Service Catalog / Projects
# product roles. These are fixed-name, account-global roles, so if they already
# exist the stack fails with a validation/AlreadyExists error. In 'auto' mode we
# detect their presence and only create them when missing.
if [ "${CREATE_SC_ROLES}" = "auto" ]; then
  if aws iam get-role --role-name AmazonSageMakerServiceCatalogProductsLaunchRole >/dev/null 2>&1; then
    CREATE_SC_ROLES="false"
    log "Service Catalog product roles already exist -> CreateServiceCatalogRoles=false (reuse)"
  else
    CREATE_SC_ROLES="true"
    log "Service Catalog product roles not found -> CreateServiceCatalogRoles=true (create)"
  fi
else
  log "CreateServiceCatalogRoles=${CREATE_SC_ROLES} (explicit)"
fi

# ------------------------------------ ensure Lake Formation IAM default access
# If the account governs the Glue Data Catalog with Lake Formation and the
# CreateDatabase/CreateTable default permissions do NOT include
# IAM_ALLOWED_PRINCIPALS, the inference-capture Iceberg table (created by an
# Athena DDL Lambda) fails with "Insufficient Lake Formation permission(s)".
# Restore IAM_ALLOWED_PRINCIPALS as the create-default so IAM Glue permissions
# govern new databases/tables. Best-effort: warn but do not fail if the caller
# is not a Lake Formation admin.
if [ "${ENSURE_LF_IAM_DEFAULT}" = "true" ]; then
  lf_settings="$(aws lakeformation get-data-lake-settings --output json 2>/dev/null || true)"
  if [ -z "${lf_settings}" ]; then
    warn "Could not read Lake Formation settings (no access or LF not in use); skipping LF default check."
  else
    needs_fix="$(printf '%s' "${lf_settings}" | python3 -c '
import json,sys
try:
    s=json.load(sys.stdin)["DataLakeSettings"]
except Exception:
    print("skip"); sys.exit()
def has_iam(perms):
    return any((p.get("Principal") or {}).get("DataLakePrincipalIdentifier")=="IAM_ALLOWED_PRINCIPALS" for p in (perms or []))
db=has_iam(s.get("CreateDatabaseDefaultPermissions"))
tb=has_iam(s.get("CreateTableDefaultPermissions"))
print("ok" if (db and tb) else "fix")
')"
    if [ "${needs_fix}" = "fix" ]; then
      log "Lake Formation create-default permissions lack IAM_ALLOWED_PRINCIPALS; setting them (keeps existing admins)."
      new_settings="$(printf '%s' "${lf_settings}" | python3 -c '
import json,sys
s=json.load(sys.stdin)["DataLakeSettings"]
iam_all=[{"Principal":{"DataLakePrincipalIdentifier":"IAM_ALLOWED_PRINCIPALS"},"Permissions":["ALL"]}]
out={"DataLakeAdmins":s.get("DataLakeAdmins",[]),
     "CreateDatabaseDefaultPermissions":iam_all,
     "CreateTableDefaultPermissions":iam_all}
print(json.dumps(out))
')"
      if aws lakeformation put-data-lake-settings --data-lake-settings "${new_settings}" >/dev/null 2>&1; then
        log "Lake Formation IAM_ALLOWED_PRINCIPALS default set."
      else
        warn "Could not update Lake Formation settings (need LF admin). If the"
        warn "inference-capture stack fails on 'Insufficient Lake Formation"
        warn "permission(s)', ask an LF admin to add IAM_ALLOWED_PRINCIPALS to"
        warn "the CreateDatabase/CreateTable default permissions, then redeploy."
      fi
    else
      log "Lake Formation create-default permissions already include IAM_ALLOWED_PRINCIPALS."
    fi
  fi
fi

# ------------------------------------------------ QuickSight subscription -----
# Lab 5E's governance dashboard needs the account subscribed to QuickSight.
# There is no CloudFormation resource for the subscription (AWS::QuickSight::*
# covers data sources, datasets, analyses and dashboards, never the account), so
# it is done here via the API instead. Run before the long CloudFormation deploy
# so a bad email or a missing permission fails in seconds rather than 30 min in.
#
# The subscription is account-global and one-time: it survives teardown, so
# redeploys into the same account skip straight past this.
# Mirrors Lab 5E's own gate (describe_account_settings against the identity
# region) rather than comparing subscription-status enums.
#
# The error output is CAPTURED rather than discarded, because it is the only
# thing that separates the three ways this call fails, and they need different
# fixes:
#   * wrong identity region  -> AWS names the correct region in the message
#   * caller lacks the IAM action
#   * account genuinely not subscribed
# Throwing stderr away reported all three as "not subscribed (or cannot read
# settings)", which sent people to sign up for a subscription they already had.
QUICKSIGHT_PROBE_ERROR=""
quicksight_ready() {
  local output rc=0
  # `|| rc=$?` keeps `set -e` from aborting on the expected failure.
  output="$(aws quicksight describe-account-settings \
    --aws-account-id "${ACCOUNT_ID}" \
    --region "${QUICKSIGHT_IDENTITY_REGION}" 2>&1)" || rc=$?
  if [ "${rc}" -eq 0 ]; then
    QUICKSIGHT_PROBE_ERROR=""
    return 0
  fi
  QUICKSIGHT_PROBE_ERROR="${output}"
  return 1
}

# QuickSight has ONE identity endpoint per account, fixed when the account was
# first activated. Calling any other region returns an AccessDeniedException
# that names the right one, e.g.
#   "Operation is being called from endpoint us-east-1, but your identity
#    region is us-west-2. Please use the us-west-2 endpoint."
# Pure parameter expansion rather than sed/grep: no regex quoting to get wrong,
# no BSD-vs-GNU differences, and no dependence on trailing newlines.
quicksight_identity_region_hint() {
  local hint
  case "${QUICKSIGHT_PROBE_ERROR}" in
    *"identity region is "*)
      hint="${QUICKSIGHT_PROBE_ERROR##*identity region is }"  # drop everything before
      hint="${hint%%[^a-z0-9-]*}"                             # keep the region token
      printf '%s' "${hint}"
      ;;
  esac
}

# ---- resolve the identity region before judging the subscription ------------
# Done first so the branches below see an accurate answer rather than a
# misdirected probe.
if ! quicksight_ready; then
  qs_region_hint="$(quicksight_identity_region_hint)"
  if [ -n "${qs_region_hint}" ] && [ "${qs_region_hint}" != "${QUICKSIGHT_IDENTITY_REGION}" ]; then
    warn "QuickSight IS subscribed, but its identity region is '${qs_region_hint}',"
    warn "not '${QUICKSIGHT_IDENTITY_REGION}' (this script's default). Every QuickSight"
    warn "admin API call has to hit that one endpoint."
    log "Using ${qs_region_hint} as the QuickSight identity region for this run."
    QUICKSIGHT_IDENTITY_REGION="${qs_region_hint}"
    echo
    warn "ACTION NEEDED for Lab 5E: it reads the identity region from its OWN"
    warn "config, not from this script, and will fail the same way until you set it:"
    warn "    echo 'QUICKSIGHT_IDENTITY_REGION=${qs_region_hint}' >> .env"
    warn "  (or edit lab5-monitoring/src/config/config.yaml -> aws.quicksight_identity_region)"
    warn "To skip this detection on later runs, pass it in directly:"
    warn "    QUICKSIGHT_IDENTITY_REGION=${qs_region_hint} $0"
    echo
  fi
fi

if quicksight_ready; then
  qs_edition="$(aws quicksight describe-account-settings \
    --aws-account-id "${ACCOUNT_ID}" --region "${QUICKSIGHT_IDENTITY_REGION}" \
    --query 'AccountSettings.Edition' --output text 2>/dev/null || echo Unknown)"
  log "QuickSight already subscribed in ${QUICKSIGHT_IDENTITY_REGION} (edition ${qs_edition})."
  if [ "${qs_edition}" = "STANDARD" ]; then
    warn "Lab 5E builds its dashboard with the Definition API, which needs ENTERPRISE."
    warn "Upgrade in the QuickSight console before running lab5e."
  fi
elif printf '%s' "${QUICKSIGHT_PROBE_ERROR}" | grep -q "not authorized to perform"; then
  # Distinct from "not subscribed": the account may well be subscribed, this
  # caller just cannot see it. Telling someone to sign up here is wrong, and
  # signing up a second time is not possible anyway.
  warn "This caller is not authorized to call quicksight:DescribeAccountSettings,"
  warn "so the subscription state cannot be determined. The account may already be"
  warn "subscribed. The failing call was:"
  warn "  aws quicksight describe-account-settings --aws-account-id ${ACCOUNT_ID} \\"
  warn "    --region ${QUICKSIGHT_IDENTITY_REGION}"
  warn "Grant the action, or have someone who has it confirm the subscription and"
  warn "its identity region. Deploying continues: only Lab 5E depends on this."
  warn "Raw error: ${QUICKSIGHT_PROBE_ERROR}"
elif [ "${SUBSCRIBE_QUICKSIGHT}" != "true" ]; then
  warn "QuickSight is NOT subscribed in ${QUICKSIGHT_IDENTITY_REGION}."
  warn "Lab 5E will stop at its subscription check. Every other lab is unaffected."
  warn "Raw error from the probe: ${QUICKSIGHT_PROBE_ERROR}"
  warn "Sign up once per account. The workshop's default path is the console, during"
  warn "Lab 5E, so participants see the subscription and the data-access grant as the"
  warn "two separate steps they are: search the console for 'quick' and sign up. That"
  warn "form has no edition selector, so verify afterwards with:"
  warn "  aws quicksight describe-account-settings --aws-account-id ${ACCOUNT_ID} \\"
  warn "    --region ${QUICKSIGHT_IDENTITY_REGION} --query AccountSettings.Edition"
  warn "For bulk provisioning, this script can do it instead:"
  warn "  SUBSCRIBE_QUICKSIGHT=true QUICKSIGHT_NOTIFICATION_EMAIL=you@example.com $0"
  warn "Whichever route, re-run $0 afterwards (no flag needed) so the data-access"
  warn "policies get attached to aws-quicksight-service-role-v0 once it exists."
else
  [ -n "${QUICKSIGHT_NOTIFICATION_EMAIL}" ] \
    || die "SUBSCRIBE_QUICKSIGHT=true also needs QUICKSIGHT_NOTIFICATION_EMAIL=<address>."
  log "Subscribing the account to QuickSight ${QUICKSIGHT_EDITION} in ${QUICKSIGHT_IDENTITY_REGION} ..."
  log "  Account name: ${QUICKSIGHT_ACCOUNT_NAME}   Notifications: ${QUICKSIGHT_NOTIFICATION_EMAIL}"
  warn "This creates a BILLABLE QuickSight subscription. The identity region and"
  warn "account name cannot be changed afterwards."
  if subscribe_out="$(aws quicksight create-account-subscription \
        --aws-account-id "${ACCOUNT_ID}" \
        --region "${QUICKSIGHT_IDENTITY_REGION}" \
        --edition "${QUICKSIGHT_EDITION}" \
        --authentication-method IAM_AND_QUICKSIGHT \
        --account-name "${QUICKSIGHT_ACCOUNT_NAME}" \
        --notification-email "${QUICKSIGHT_NOTIFICATION_EMAIL}" 2>&1)"; then
    log "Subscription requested; waiting for QuickSight to finish provisioning ..."
    # Provisioning is asynchronous and usually takes a couple of minutes.
    qs_provisioned="false"
    for _ in $(seq 1 40); do
      if quicksight_ready; then qs_provisioned="true"; break; fi
      sleep 15
    done
    if [ "${qs_provisioned}" = "true" ]; then
      log "QuickSight subscription active."
      log "Add yourself as an Author/Admin in the QuickSight console if you want to"
      log "open the Lab 5E dashboard interactively (the notebook does not need it)."
    else
      warn "QuickSight did not report ready within 10 min. It may still be provisioning;"
      warn "check https://quicksight.aws.amazon.com/ before running lab5e."
    fi
  else
    # Deliberately non-fatal: every lab except 5E works without QuickSight, and
    # the common failures here (already subscribed under a different identity
    # region, no CreateAccountSubscription permission) are all account-level
    # conditions the rest of the deploy does not depend on.
    warn "create-account-subscription failed; continuing without QuickSight."
    warn "  ${subscribe_out}"
    warn "Common causes: the caller lacks quicksight:CreateAccountSubscription /"
    warn "quicksight:Subscribe (plus the ds:* actions QuickSight uses for its"
    warn "user directory); the account is already subscribed in a DIFFERENT"
    warn "region (set QUICKSIGHT_IDENTITY_REGION to it); or the account name is"
    warn "already taken (set QUICKSIGHT_ACCOUNT_NAME)."
  fi
fi

# ------------------------------- QuickSight service-role policy toggle -------
# QuickSight reads the workshop's data as its OWN service role, so 2-iam.yaml
# attaches the Lab 5E data-access policies to aws-quicksight-service-role-v0.
# CloudFormation can attach to a role it does not own, but not to one that does
# not exist yet -- and that role only appears when QuickSight is subscribed. So
# gate the template's condition on the role actually being there; otherwise the
# IAM stack would roll back on a non-QuickSight account.
ATTACH_QS_POLICY="false"
if [ "${SKIP_QS_POLICY:-false}" = "true" ]; then
  log "SKIP_QS_POLICY=true -> AttachQuickSightServiceRolePolicy=false."
  log "  Not attaching the workshop's QuickSight service-role policies"
  log "  (${PROJECT_NAME}-QuickSightS3DataLakeAccess / -QuickSightAthenaAccess)."
  log "  Policy names are project-scoped so they should not collide with other"
  log "  projects on aws-quicksight-service-role-v0. Lab 5E's dashboard panels"
  log "  will not load workshop data until these policies are attached."
elif aws iam get-role --role-name aws-quicksight-service-role-v0 >/dev/null 2>&1; then
  ATTACH_QS_POLICY="true"
  log "QuickSight service role found -> AttachQuickSightServiceRolePolicy=true"
else
  warn "QuickSight service role aws-quicksight-service-role-v0 not found ->"
  warn "AttachQuickSightServiceRolePolicy=false. Lab 5E can still build the"
  warn "dashboard, but its panels will not load data until you subscribe to"
  warn "QuickSight and re-run this script (the deploy is what grants QuickSight"
  warn "access to the data bucket and Athena)."
fi

# --------------------------------------------- validate Okta inputs early ----
# Checked before the 20-40 min SageMaker deploy so a missing metadata file fails
# in seconds rather than at the last step.
if is_selected okta-federation; then
  [ -n "${OKTA_METADATA_FILE}" ] \
    || die "Deploying ${OKTA_STACK} needs OKTA_METADATA_FILE=<path to Okta SAML metadata XML>.
  Download it from your Okta app's Sign On tab -> View IdP metadata."
  [ -f "${OKTA_METADATA_FILE}" ] \
    || die "OKTA_METADATA_FILE '${OKTA_METADATA_FILE}' not found."
  grep -qi 'EntityDescriptor' "${OKTA_METADATA_FILE}" \
    || die "OKTA_METADATA_FILE '${OKTA_METADATA_FILE}' does not look like SAML metadata
  (no EntityDescriptor element found). Make sure you saved the IdP metadata XML,
  not the Okta app settings page."
  log "Okta federation: enabled (metadata ${OKTA_METADATA_FILE}, provider ${OKTA_PROVIDER_NAME})"
fi

# ------------------------------------------------------------- deploy --------
# Each stack is deployed independently and waited on. Outputs are threaded
# forward as parameters -- the job main.yaml used to do with !GetAtt.
ensure_template_bucket

log "Deploying ${#SELECTED[@]} stack(s). The SageMaker domain alone takes 20-40 min."

# Running counter, so a partial deploy reads [1/1] rather than [2/1].
STEP=0
step() { STEP=$((STEP + 1)); log "[${STEP}/${#SELECTED[@]}] $*"; }

if is_selected networking; then
  step "networking"
  deploy_stack networking \
    "ProjectName=${PROJECT_NAME}" \
    "VpcCIDR=${VPC_CIDR}" \
    "PrivateSubnetCIDR=${PRIVATE_SUBNET_CIDR}" \
    "PrivateSubnet2CIDR=${PRIVATE_SUBNET2_CIDR}" \
    "PublicSubnetCIDR=${PUBLIC_SUBNET_CIDR}"
fi

if is_selected iam; then
  step "iam"
  deploy_stack iam \
    "ProjectName=${PROJECT_NAME}" \
    "CreateServiceCatalogRoles=${CREATE_SC_ROLES}" \
    "AttachQuickSightServiceRolePolicy=${ATTACH_QS_POLICY}"
fi

if is_selected sagemaker; then
  step "sagemaker (domain, user profiles, buckets, MLflow)"
  deploy_stack sagemaker \
    "ProjectName=${PROJECT_NAME}" \
    "JupyterLabAppInstance=${JUPYTERLAB_APP_INSTANCE}" \
    "UserAProfileName=${USER_A_PROFILE_NAME}" \
    "UserBProfileName=${USER_B_PROFILE_NAME}" \
    "SeedCodeType=${SEED_CODE_TYPE}"
fi

if is_selected inference-capture || is_selected data-prep; then
  # The real workshop data bucket, created by the SageMaker stack. Both later
  # stacks must be told explicitly: their own fallback derives the SageMaker
  # default bucket sagemaker-<region>-<account>, which does not exist in a fresh
  # account, and Athena then fails with "Unable to verify/create output bucket".
  DATA_BUCKET="$(require_output "${SAGEMAKER_STACK}" DataBucketName)"
  log "Data bucket: ${DATA_BUCKET}"
fi

if is_selected inference-capture; then
  step "inference-capture (SQS + Lambda -> Athena Iceberg)"
  # Grant sqs:SendMessage on the capture queue to the three execution roles.
  ENDPOINT_ROLE_NAMES="$(require_output "${IAM_STACK}" ProductSageMakerExecutionRoleName)"
  ENDPOINT_ROLE_NAMES="${ENDPOINT_ROLE_NAMES},$(require_output "${IAM_STACK}" UserASageMakerExecutionRoleName)"
  ENDPOINT_ROLE_NAMES="${ENDPOINT_ROLE_NAMES},$(require_output "${IAM_STACK}" UserBSageMakerExecutionRoleName)"
  log "Endpoint execution roles: ${ENDPOINT_ROLE_NAMES}"

  deploy_stack inference-capture \
    "ProjectName=${PROJECT_NAME}" \
    "DataBucketName=${DATA_BUCKET}" \
    "EndpointExecutionRoleNames=${ENDPOINT_ROLE_NAMES}"
fi

if is_selected data-prep; then
  step "data-prep (Glue/Athena + S3 Tables Iceberg, EMR roles)"
  # CreateGlueDatabase=false: the inference-capture stack creates the shared
  # 'bank_marketing' Glue database, and a Glue database name is unique per
  # account/region, so only one stack may own it.
  # EnableLakeFormationGrants=false: the deploy is not an LF admin, so it relies
  # on the account's IAM_ALLOWED_PRINCIPALS default (ensured above).
  deploy_stack data-prep \
    "ProjectName=${PROJECT_NAME}" \
    "DataBucketName=${DATA_BUCKET}" \
    "CreateGlueDatabase=false" \
    "EnableLakeFormationGrants=false" \
    "EMRReleaseLabel=${EMR_RELEASE_LABEL}"
fi

if is_selected okta-federation; then
  step "okta-federation (SAML provider, federation role)"
  # @path passes the file CONTENTS as the parameter value, so the multi-line
  # metadata XML is not mangled by shell quoting.
  deploy_stack okta-federation \
    "ProjectName=${PROJECT_NAME}" \
    "OktaMetadataDocument=@${OKTA_METADATA_FILE}" \
    "OktaProviderName=${OKTA_PROVIDER_NAME}"
fi

# ------------------------------------------- verify Lab 5E QuickSight grant ---
# Lab 5E (governance dashboard) is the one lab whose failure mode looks like a
# QuickSight sign-up problem but is actually an IAM gap:
#   "Cannot check QuickSight: this role lacks quicksight:DescribeAccountSettings"
# Confirm the grant landed on the execution roles instead of trusting that the
# IAM stack updated. Purely advisory: never fails the deploy.
#
# This reads the IAM stack's OUTPUTS. The previous version looked up exports
# named <project>-UserARoleArn / -UserBRoleArn / -ProductRoleArn, which
# 2-iam.yaml has never defined -- so the check silently skipped every run.
if [ "${VERIFY_QUICKSIGHT_IAM}" = "true" ] && is_selected iam; then
  log "Verifying the Lab 5E QuickSight grant on the execution roles ..."
  QS_ACTIONS=(quicksight:DescribeAccountSettings quicksight:CreateDataSet quicksight:CreateDashboard)
  for output_key in UserASageMakerExecutionRoleArn UserBSageMakerExecutionRoleArn ProductSageMakerExecutionRoleArn; do
    role_arn="$(stack_output "${IAM_STACK}" "${output_key}")"
    if [ -z "${role_arn}" ]; then
      warn "${IAM_STACK} has no output ${output_key}; skipping its QuickSight check."
      continue
    fi
    denied="$(aws iam simulate-principal-policy \
      --policy-source-arn "${role_arn}" \
      --action-names "${QS_ACTIONS[@]}" \
      --query "EvaluationResults[?EvalDecision!='allowed'].EvalActionName" \
      --output text 2>/dev/null)" || denied="__ERROR__"
    if [ "${denied}" = "__ERROR__" ]; then
      warn "Could not simulate policies for ${role_arn} (needs iam:SimulatePrincipalPolicy); skipping."
    elif [ -n "${denied}" ]; then
      warn "${role_arn##*/} is MISSING QuickSight actions: ${denied}"
      warn "  Lab 5E will report 'Cannot check QuickSight'. The grant is the"
      warn "  QuickSightGovernanceDashboard statement in templates/2-iam.yaml."
      warn "  Re-run this script from a checkout that contains it."
    else
      log "  QuickSight grant present on ${role_arn##*/}"
    fi
  done

  # Second half of Lab 5E's permissions: what QuickSight itself may read. These
  # are the conditional AWS::IAM::Policy resources in 2-iam.yaml, so this only
  # confirms the condition was satisfied at deploy time.
  if [ "${ATTACH_QS_POLICY}" = "true" ]; then
    qs_role_policies="$(aws iam list-role-policies \
      --role-name aws-quicksight-service-role-v0 \
      --query 'PolicyNames' --output text 2>/dev/null || echo "__ERROR__")"
    if [ "${qs_role_policies}" = "__ERROR__" ]; then
      warn "Could not list policies on aws-quicksight-service-role-v0; skipping."
    else
      for policy in "${PROJECT_NAME}-QuickSightS3DataLakeAccess" "${PROJECT_NAME}-QuickSightAthenaAccess"; do
        case " ${qs_role_policies} " in
          *" ${policy} "*) log "  ${policy} attached to the QuickSight service role" ;;
          *) warn "${policy} is MISSING from aws-quicksight-service-role-v0 -- Lab 5E's"
             warn "  dashboard will render but its panels will fail to load data." ;;
        esac
      done
    fi
  fi
fi

# --------------------------------------------------------- outputs -----------
# Aggregated view of what main.yaml used to expose as parent-stack Outputs.
# Format: <label>|<stack>|<output key>
log "Workshop outputs:"
OUTPUT_MAP=(
  "VPCId|${NETWORKING_STACK}|VPCId"
  "SageMakerDomainId|${SAGEMAKER_STACK}|SageMakerDomainId"
  "DataBucketName|${SAGEMAKER_STACK}|DataBucketName"
  "GrantsBucketName|${SAGEMAKER_STACK}|GrantsBucketName"
  "MLflowAppArn|${SAGEMAKER_STACK}|MLflowAppArn"
  "UserAExecutionRoleArn|${IAM_STACK}|UserASageMakerExecutionRoleArn"
  "UserBExecutionRoleArn|${IAM_STACK}|UserBSageMakerExecutionRoleArn"
  "AthenaDatabase|${INFERENCE_STACK}|GlueDatabaseName"
  "InferenceCaptureQueueUrl|${INFERENCE_STACK}|InferenceCaptureQueueUrl"
  "InferenceCaptureTable|${INFERENCE_STACK}|InferenceTableName"
  "DataPrepTrainingTable|${DATA_PREP_STACK}|TrainingTableName"
  "DataPrepEvaluationTable|${DATA_PREP_STACK}|EvaluationTableName"
  "DataPrepTableBucketName|${DATA_PREP_STACK}|TableBucketName"
  "EMRServerlessApplicationId|${DATA_PREP_STACK}|EMRServerlessApplicationId"
  "OktaFederationRoleArn|${OKTA_STACK}|FederationRoleArn"
  "OktaSAMLProviderArn|${OKTA_STACK}|SAMLProviderArn"
)

printf '  %-28s %s\n' "ProjectName" "${PROJECT_NAME}"
for entry in "${OUTPUT_MAP[@]}"; do
  label="${entry%%|*}"
  rest="${entry#*|}"
  stack="${rest%%|*}"
  key="${rest#*|}"
  stack_exists "${stack}" || continue
  value="$(stack_output "${stack}" "${key}")"
  [ -n "${value}" ] && printf '  %-28s %s\n' "${label}" "${value}"
done

echo
log "Deployed stacks:"
for s in "${STACK_ORDER[@]}"; do
  name="$(stack_name_for "${s}")"
  if stack_exists "${name}"; then
    status="$(aws cloudformation describe-stacks --stack-name "${name}" \
      --query "Stacks[0].StackStatus" --output text 2>/dev/null || echo UNKNOWN)"
    printf '  %-44s %s\n' "${name}" "${status}"
  fi
done

echo
log "Done."
log "To tear down:  scripts/teardown-workshop.sh         (thorough)"
log "               TEARDOWN=true $0   (stacks only)"
