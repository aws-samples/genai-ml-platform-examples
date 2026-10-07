#!/usr/bin/env bash
#
# deploy-workshop.sh
#
# Deploy the GenAI/ML Standardization workshop main stack (main.yaml) and its
# nested stacks (1-networking, 2-iam, 3-sagemaker, 4-inference-capture,
# 5-data-prep) from a public git repo, runnable from AWS CloudShell.
#
# What it does:
#   1. Clones the public git repo (or uses a local template dir).
#   2. Ensures a private S3 bucket exists in the target region for the templates.
#   3. Uploads the nested child templates to that bucket.
#   4. Deploys the parent stack, passing the bucket/prefix as parameters so
#      main.yaml resolves its child TemplateURLs, and waits for completion.
#   5. Prints the stack outputs.
#
# Nested stacks require child templates to live in S3 (not git), which is why
# steps 2-3 exist. main.yaml takes S3TemplateBucket / S3TemplateKeyPrefix
# parameters and builds the child URLs from them.
#
# Usage (CloudShell):
#   # Option A - run from a clone of the repo:
#   git clone <REPO_URL> && cd genai-ml-standardization
#   ./scripts/deploy-workshop.sh
#
#   # Option B - run standalone, let the script clone:
#   REPO_URL=https://github.com/<org>/<repo>.git ./scripts/deploy-workshop.sh
#
# Common overrides (environment variables):
#   REPO_URL        Public git URL to clone (default: use local ./templates if present)
#   REPO_BRANCH     Branch to clone (default: main)
#   TEMPLATE_DIR    Path to a local templates dir (skips git clone)
#   PROJECT_NAME    Workshop project name, lowercase (default: bank-marketing-prediction)
#                   Must match ^[a-z0-9-]+$ (lowercase letters, digits, hyphens).
#   STACK_NAME      CloudFormation stack name (default: <PROJECT_NAME>-workshop)
#   AWS_REGION      Target region (default: CloudShell's region)
#   TEMPLATE_BUCKET S3 bucket for templates (default: <PROJECT_NAME>-cfn-<acct>-<region>)
#   VPC_CIDR             VPC CIDR (default: 10.1.0.0/16)              -> VpcCIDR
#   PRIVATE_SUBNET_CIDR  Private subnet 1 CIDR (default: 10.1.1.0/24) -> PrivateSubnetCIDR
#   PRIVATE_SUBNET2_CIDR Private subnet 2 CIDR (default: 10.1.2.0/24) -> PrivateSubnet2CIDR
#   PUBLIC_SUBNET_CIDR   Public subnet CIDR (default: 10.1.3.0/24)    -> PublicSubnetCIDR
#   JUPYTERLAB_APP_INSTANCE JupyterLab instance type (default: ml.m5.2xlarge)
#   USER_A_PROFILE_NAME  First user profile name (default: userA)
#   USER_B_PROFILE_NAME  Second user profile name (default: userB)
#   SEED_CODE_TYPE       regression | llm-fine-tuning | classification
#                        (default: classification)
#   EMR_RELEASE_LABEL    EMR release for Lab 2 data prep (default: emr-7.5.0)
#   CREATE_SC_ROLES 'auto', 'true', or 'false' - create the AWS SageMaker
#                   Service Catalog / Projects product roles. These have fixed,
#                   account-global names and can be owned by only ONE stack per
#                   account. 'auto' (default) checks whether they already exist
#                   and passes 'false' if so (reuse) or 'true' if not (create),
#                   avoiding "Validation failed" AlreadyExists collisions.
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
#   TEARDOWN        If 'true', delete the stack instead of deploying.
#
# Note on template versioning: the child templates are uploaded under
# <S3_PREFIX>/<hash-of-templates>/ and that versioned prefix is passed to
# main.yaml. See the "version the template key prefix" section below for why a
# fixed prefix makes child-template edits invisible to CloudFormation.
#
set -euo pipefail

# Directory this script lives in, so it can locate ../templates regardless of
# the current working directory it is invoked from.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# ------------------------------------------------------------------ config ---
REPO_URL="${REPO_URL:-}"
REPO_BRANCH="${REPO_BRANCH:-main}"
TEMPLATE_DIR="${TEMPLATE_DIR:-}"
PROJECT_NAME="${PROJECT_NAME:-bank-marketing-prediction}"
STACK_NAME="${STACK_NAME:-${PROJECT_NAME}-workshop}"
CREATE_SC_ROLES="${CREATE_SC_ROLES:-auto}"
ENSURE_LF_IAM_DEFAULT="${ENSURE_LF_IAM_DEFAULT:-true}"
VERIFY_QUICKSIGHT_IAM="${VERIFY_QUICKSIGHT_IAM:-true}"
SUBSCRIBE_QUICKSIGHT="${SUBSCRIBE_QUICKSIGHT:-false}"
QUICKSIGHT_NOTIFICATION_EMAIL="${QUICKSIGHT_NOTIFICATION_EMAIL:-}"
QUICKSIGHT_IDENTITY_REGION="${QUICKSIGHT_IDENTITY_REGION:-us-east-1}"
QUICKSIGHT_EDITION="${QUICKSIGHT_EDITION:-ENTERPRISE}"
TEARDOWN="${TEARDOWN:-false}"
# Base prefix; the per-deploy template hash is appended to it further down.
S3_PREFIX="${S3_PREFIX:-genai-ml-std-assets}"

# ---- Pass-through stack parameters (map to main.yaml Parameters) ------------
# All optional; each falls back to main.yaml's own default if left unset here.
VPC_CIDR="${VPC_CIDR:-10.1.0.0/16}"
PRIVATE_SUBNET_CIDR="${PRIVATE_SUBNET_CIDR:-10.1.1.0/24}"
PRIVATE_SUBNET2_CIDR="${PRIVATE_SUBNET2_CIDR:-10.1.2.0/24}"
PUBLIC_SUBNET_CIDR="${PUBLIC_SUBNET_CIDR:-10.1.3.0/24}"
JUPYTERLAB_APP_INSTANCE="${JUPYTERLAB_APP_INSTANCE:-ml.m5.2xlarge}"
USER_A_PROFILE_NAME="${USER_A_PROFILE_NAME:-userA}"
USER_B_PROFILE_NAME="${USER_B_PROFILE_NAME:-userB}"
# main.yaml SeedCodeType AllowedValues: regression | llm-fine-tuning | classification
SEED_CODE_TYPE="${SEED_CODE_TYPE:-classification}"
# EMR release for the Lab 2 data-prep EMR Serverless app / EMR on EC2 clusters.
EMR_RELEASE_LABEL="${EMR_RELEASE_LABEL:-emr-7.5.0}"

# Child templates referenced by main.yaml (order-independent).
CHILD_TEMPLATES=(1-networking.yaml 2-iam.yaml 3-sagemaker.yaml 4-inference-capture.yaml 5-data-prep.yaml)

log()  { printf '\033[1;34m[deploy]\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m[warn]\033[0m %s\n'  "$*" >&2; }
die()  { printf '\033[1;31m[error]\033[0m %s\n' "$*" >&2; exit 1; }

# ------------------------------------------------------------- prereqs -------
command -v aws >/dev/null 2>&1 || die "aws CLI not found (CloudShell has it by default)."

# Resolve region: explicit AWS_REGION, else CLI default, else CloudShell env.
REGION="${AWS_REGION:-${AWS_DEFAULT_REGION:-$(aws configure get region 2>/dev/null || true)}}"
[ -n "${REGION}" ] || die "Could not determine AWS region. Set AWS_REGION."
export AWS_DEFAULT_REGION="${REGION}"

ACCOUNT_ID="$(aws sts get-caller-identity --query Account --output text)" \
  || die "Unable to call STS. Are credentials configured?"

TEMPLATE_BUCKET="${TEMPLATE_BUCKET:-${PROJECT_NAME}-cfn-${ACCOUNT_ID}-${REGION}}"
# Defaults that need ACCOUNT_ID, so they are resolved after the STS call.
QUICKSIGHT_ACCOUNT_NAME="${QUICKSIGHT_ACCOUNT_NAME:-${PROJECT_NAME}-${ACCOUNT_ID}}"

log "Account:        ${ACCOUNT_ID}"
log "Region:         ${REGION}"
log "Project name:   ${PROJECT_NAME}"
log "Stack name:     ${STACK_NAME}"
log "Template bucket: ${TEMPLATE_BUCKET}"
log "Seed code type: ${SEED_CODE_TYPE}"
log "JupyterLab:     ${JUPYTERLAB_APP_INSTANCE}"
log "VPC CIDR:       ${VPC_CIDR} (priv ${PRIVATE_SUBNET_CIDR}, priv2 ${PRIVATE_SUBNET2_CIDR}, pub ${PUBLIC_SUBNET_CIDR})"
log "User profiles:  ${USER_A_PROFILE_NAME}, ${USER_B_PROFILE_NAME}"

# ProjectName must be lowercase letters, digits, and hyphens (main.yaml pattern).
if ! printf '%s' "${PROJECT_NAME}" | grep -Eq '^[a-z0-9-]+$'; then
  die "PROJECT_NAME='${PROJECT_NAME}' is invalid. Use lowercase letters, digits, and hyphens only (e.g. bank-marketing-mlops-project)."
fi

# -------------------------------------------------------------- teardown -----
if [ "${TEARDOWN}" = "true" ]; then
  log "Deleting stack ${STACK_NAME} ..."
  aws cloudformation delete-stack --stack-name "${STACK_NAME}"
  aws cloudformation wait stack-delete-complete --stack-name "${STACK_NAME}"
  log "Stack deleted. (The template bucket ${TEMPLATE_BUCKET} was left in place.)"
  exit 0
fi

# ---------------------------------------------------- obtain templates -------
WORKDIR=""
cleanup() { [ -n "${WORKDIR}" ] && rm -rf "${WORKDIR}" || true; }
trap cleanup EXIT

if [ -z "${TEMPLATE_DIR}" ]; then
  if [ -f "templates/main.yaml" ]; then
    TEMPLATE_DIR="templates"
    log "Using local templates directory: ${TEMPLATE_DIR}"
  elif [ -f "${SCRIPT_DIR}/../templates/main.yaml" ]; then
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

[ -f "${TEMPLATE_DIR}/main.yaml" ] || die "main.yaml not found in ${TEMPLATE_DIR}"
for t in "${CHILD_TEMPLATES[@]}"; do
  [ -f "${TEMPLATE_DIR}/${t}" ] || die "Child template missing: ${TEMPLATE_DIR}/${t}"
done

# ------------------------------------------- version the template key prefix --
# CloudFormation updates a nested stack only when something the PARENT stack
# sees changes. Overwriting a child template in place (same TemplateURL) is
# invisible to it: main.yaml and its parameters stay byte-identical, `deploy`
# produces an empty change set, --no-fail-on-empty-changeset reports success,
# and the child stack keeps running the template it was created with — so an
# edit to 2-iam.yaml never reaches the deployed roles.
#
# Hashing the template set into the key prefix makes every child TemplateURL
# change whenever any template changes, so the parent change set is non-empty
# and CloudFormation re-reads and updates each child. Identical templates hash
# identically, so a no-op redeploy stays a no-op.
TEMPLATE_HASH_INPUTS=("${TEMPLATE_DIR}/main.yaml")
for t in "${CHILD_TEMPLATES[@]}"; do
  TEMPLATE_HASH_INPUTS+=("${TEMPLATE_DIR}/${t}")
done
TEMPLATES_HASH="$(cat "${TEMPLATE_HASH_INPUTS[@]}" | sha256sum | cut -c1-12)"
S3_PREFIX="${S3_PREFIX}/${TEMPLATES_HASH}"
log "Template version: ${TEMPLATES_HASH}"

# --------------------------------------------------- ensure S3 bucket --------
if aws s3api head-bucket --bucket "${TEMPLATE_BUCKET}" >/dev/null 2>&1; then
  log "Reusing existing bucket ${TEMPLATE_BUCKET}"
else
  log "Creating bucket ${TEMPLATE_BUCKET} in ${REGION}"
  # 'aws s3 mb' handles the us-east-1 vs other-region LocationConstraint quirk.
  aws s3 mb "s3://${TEMPLATE_BUCKET}" --region "${REGION}"
  aws s3api put-public-access-block --bucket "${TEMPLATE_BUCKET}" \
    --public-access-block-configuration \
    BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true
fi

# ----------------------------------------------------- upload children -------
log "Uploading child templates to s3://${TEMPLATE_BUCKET}/${S3_PREFIX}/"
for t in "${CHILD_TEMPLATES[@]}"; do
  aws s3 cp "${TEMPLATE_DIR}/${t}" "s3://${TEMPLATE_BUCKET}/${S3_PREFIX}/${t}" --only-show-errors
done

# --------------------------------------------- resolve CreateServiceCatalogRoles
# The 2-iam.yaml stack optionally creates the AWS SageMaker Service Catalog /
# Projects product roles. These are fixed-name, account-global roles, so if they
# already exist the stack fails with a validation/AlreadyExists error. In 'auto'
# mode we detect their presence and only create them when missing.
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
  iam_all='[{"Principal":{"DataLakePrincipalIdentifier":"IAM_ALLOWED_PRINCIPALS"},"Permissions":["ALL"]}]'
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
quicksight_ready() {
  # Mirrors Lab 5E's own gate (describe_account_settings against the identity
  # region) rather than comparing subscription-status enums.
  aws quicksight describe-account-settings \
    --aws-account-id "${ACCOUNT_ID}" \
    --region "${QUICKSIGHT_IDENTITY_REGION}" \
    >/dev/null 2>&1
}

if quicksight_ready; then
  qs_edition="$(aws quicksight describe-account-settings \
    --aws-account-id "${ACCOUNT_ID}" --region "${QUICKSIGHT_IDENTITY_REGION}" \
    --query 'AccountSettings.Edition' --output text 2>/dev/null || echo Unknown)"
  log "QuickSight already subscribed in ${QUICKSIGHT_IDENTITY_REGION} (edition ${qs_edition})."
  if [ "${qs_edition}" = "STANDARD" ]; then
    warn "Lab 5E builds its dashboard with the Definition API, which needs ENTERPRISE."
    warn "Upgrade in the QuickSight console before running lab5e."
  fi
elif [ "${SUBSCRIBE_QUICKSIGHT}" != "true" ]; then
  warn "QuickSight is NOT subscribed in ${QUICKSIGHT_IDENTITY_REGION} (or this caller"
  warn "cannot read its settings). Lab 5E will stop at its subscription check."
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
# not exist yet — and that role only appears when QuickSight is subscribed. So
# gate the template's condition on the role actually being there; otherwise the
# whole deployment would roll back on a non-QuickSight account.
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

# ------------------------------------------------------- deploy --------------
# main.yaml builds its child TemplateURLs from the S3TemplateBucket /
# S3TemplateKeyPrefix parameters, so we deploy it directly and pass the bucket
# where the children were just uploaded -- no URL rewriting needed.
log "Deploying stack ${STACK_NAME} (this can take 20-40 min for the SageMaker domain)..."
aws cloudformation deploy \
  --stack-name "${STACK_NAME}" \
  --template-file "${TEMPLATE_DIR}/main.yaml" \
  --capabilities CAPABILITY_NAMED_IAM CAPABILITY_AUTO_EXPAND \
  --parameter-overrides \
      "ProjectName=${PROJECT_NAME}" \
      "S3TemplateBucket=${TEMPLATE_BUCKET}" \
      "S3TemplateKeyPrefix=${S3_PREFIX}" \
      "CreateServiceCatalogRoles=${CREATE_SC_ROLES}" \
      "AttachQuickSightServiceRolePolicy=${ATTACH_QS_POLICY}" \
      "VpcCIDR=${VPC_CIDR}" \
      "PrivateSubnetCIDR=${PRIVATE_SUBNET_CIDR}" \
      "PrivateSubnet2CIDR=${PRIVATE_SUBNET2_CIDR}" \
      "PublicSubnetCIDR=${PUBLIC_SUBNET_CIDR}" \
      "JupyterLabAppInstance=${JUPYTERLAB_APP_INSTANCE}" \
      "UserAProfileName=${USER_A_PROFILE_NAME}" \
      "UserBProfileName=${USER_B_PROFILE_NAME}" \
      "SeedCodeType=${SEED_CODE_TYPE}" \
      "EMRReleaseLabel=${EMR_RELEASE_LABEL}" \
  --tags "WorkshopProject=${PROJECT_NAME}" "deployed-by=deploy-workshop.sh" \
  --no-fail-on-empty-changeset

# ------------------------------------------- verify Lab 5E QuickSight grant ---
# Lab 5E (governance dashboard) is the one lab whose failure mode looks like a
# QuickSight sign-up problem but is actually an IAM gap:
#   "Cannot check QuickSight: this role lacks quicksight:DescribeAccountSettings"
# Confirm the grant landed on the execution roles instead of trusting that the
# nested IAM stack updated. Purely advisory: never fails the deploy.
if [ "${VERIFY_QUICKSIGHT_IAM}" = "true" ]; then
  log "Verifying the Lab 5E QuickSight grant on the execution roles ..."
  QS_ACTIONS=(quicksight:DescribeAccountSettings quicksight:CreateDataSet quicksight:CreateDashboard)
  for export_suffix in UserARoleArn UserBRoleArn ProductRoleArn; do
    role_arn="$(aws cloudformation list-exports \
      --query "Exports[?Name=='${PROJECT_NAME}-${export_suffix}'].Value" \
      --output text 2>/dev/null || true)"
    if [ -z "${role_arn}" ] || [ "${role_arn}" = "None" ]; then
      warn "Export ${PROJECT_NAME}-${export_suffix} not found; skipping its QuickSight check."
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
      warn "  Re-run this script from a checkout that contains it; the template"
      warn "  prefix is versioned, so the nested IAM stack will be updated."
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
          *) warn "${policy} is MISSING from aws-quicksight-service-role-v0 — Lab 5E's"
             warn "  dashboard will render but its panels will fail to load data." ;;
        esac
      done
    fi
  fi
fi

# --------------------------------------------------------- outputs -----------
log "Stack outputs:"
aws cloudformation describe-stacks --stack-name "${STACK_NAME}" \
  --query "Stacks[0].Outputs[].{Key:OutputKey,Value:OutputValue}" \
  --output table

log "Done. To tear down:  TEARDOWN=true STACK_NAME=${STACK_NAME} $0"
