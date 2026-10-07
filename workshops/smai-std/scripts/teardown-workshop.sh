#!/usr/bin/env bash
#
# teardown-workshop.sh
#
# Delete everything deploy-workshop.sh created:
#   * the CloudFormation parent stack and all its nested stacks
#     (networking, IAM, SageMaker domain/profiles/space, inference-capture)
#   * the S3 template bucket the deploy script uploaded child templates to
#
# It also clears the two things that normally BLOCK a workshop stack delete:
#   * running SageMaker Studio apps in the domain
#   * objects in the stack's grants/data/mlflow buckets (default Delete policy,
#     so a non-empty bucket makes stack deletion fail)
# If the stack delete still fails (the classic VpcOnly case), it auto-unblocks
# the VPC by deleting the domain's orphaned EFS mount targets + filesystem and
# the inbound/outbound NFS security groups, then retries the delete once.
#
# DESTRUCTIVE: this permanently removes the domain, buckets, and their contents.
# It requires a typed confirmation unless FORCE=true.
#
# SCOPE / WHAT IT DOES NOT DELETE:
#   Artifacts created by the LAB NOTEBOOKS (not by deploy-workshop.sh) are out of
#   scope and are left in place, e.g. real-time endpoints, models, model package
#   groups, MLflow experiments/registered models, training jobs. Running
#   endpoints keep incurring cost -- delete those separately if you want them gone.
#
# Credentials/region (this workstation): set the workshop profile/region via env,
# which the AWS CLI honors natively, e.g.:
#   export AWS_PROFILE=tfc AWS_REGION=us-east-1
# (In CloudShell, leave AWS_PROFILE unset -- it uses the console identity.)
#
# Config (environment variables):
#   PROJECT_NAME          default 'smai-std-project'
#   STACK_NAME            default '<PROJECT_NAME>-workshop'
#   TEMPLATE_BUCKET       default '<PROJECT_NAME>-cfn-<acct>-<region>'
#   KEEP_TEMPLATE_BUCKET  'true' to keep the template bucket (default false)
#   KEEP_DATA            'true' to NOT empty the grants/data/mlflow buckets
#                         (default false; note: leaving them non-empty will make
#                          the stack delete fail)
#   DELETE_STUDIO_APPS    'true' to delete running Studio apps first (default true)
#   FORCE                 'true' to skip the typed confirmation prompt
#
set -euo pipefail

log()  { printf '\033[1;34m[teardown]\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m[warn]\033[0m %s\n'  "$*" >&2; }
die()  { printf '\033[1;31m[error]\033[0m %s\n' "$*" >&2; exit 1; }

# --------------------------------------------------- VPC unblock helpers -----
# The SageMaker VpcOnly domain leaves an EFS (with mount targets) and two NFS
# security groups behind. When the domain is deleted during stack teardown,
# these can linger and block subnet/VPC deletion. These helpers remove them.

# Resolve the VPC id from the (possibly DELETE_FAILED) NetworkingStack.
get_networking_vpc() {
  local net vpc
  net="$(aws cloudformation describe-stack-resources --stack-name "${STACK_NAME}" \
    --query "StackResources[?LogicalResourceId=='NetworkingStack'].PhysicalResourceId" \
    --output text 2>/dev/null || true)"
  [ -z "${net}" ] || [ "${net}" = "None" ] && return 1
  vpc="$(aws cloudformation describe-stack-resources --stack-name "${net}" \
    --query "StackResources[?ResourceType=='AWS::EC2::VPC'].PhysicalResourceId" \
    --output text 2>/dev/null || true)"
  [ -z "${vpc}" ] || [ "${vpc}" = "None" ] && return 1
  echo "${vpc}"
}

# Delete EFS mount targets whose ENIs are in this VPC, then the EFS itself.
delete_efs_in_vpc() {
  local vpc="$1" fsmt fs fslist=""
  while IFS=$'\t' read -r fsmt fs; do
    [ -z "${fsmt}" ] && continue
    log "  deleting EFS mount target ${fsmt} (fs ${fs})"
    aws efs delete-mount-target --mount-target-id "${fsmt}" 2>/dev/null || warn "   (mount target already gone?)"
    case " ${fslist} " in *" ${fs} "*) : ;; *) fslist="${fslist}${fs} " ;; esac
  done < <(aws ec2 describe-network-interfaces \
             --filters Name=vpc-id,Values="${vpc}" Name=interface-type,Values=efs \
             --query "NetworkInterfaces[].Description" --output text 2>/dev/null \
           | tr '\t' '\n' \
           | sed -nE 's/.*for (fs-[0-9a-f]+) \((fsmt-[0-9a-f]+)\).*/\2\t\1/p')

  if [ -n "${fslist}" ]; then
    log "  waiting for EFS mount targets to clear..."
    for _ in $(seq 1 30); do
      local remaining=0 n
      for fs in ${fslist}; do
        n="$(aws efs describe-file-systems --file-system-id "${fs}" \
             --query "FileSystems[0].NumberOfMountTargets" --output text 2>/dev/null || echo 0)"
        [ "${n}" != "0" ] && remaining=$((remaining + 1))
      done
      [ "${remaining}" = "0" ] && break
      sleep 10
    done
    for fs in ${fslist}; do
      log "  deleting EFS filesystem ${fs}"
      aws efs delete-file-system --file-system-id "${fs}" 2>/dev/null || warn "   (could not delete ${fs})"
    done
  fi
}

# Delete the SageMaker inbound/outbound NFS security groups in this VPC.
# They reference each other, so strip all rules first, then delete.
delete_nfs_sgs_in_vpc() {
  local vpc="$1" sgs sg ing egr
  sgs="$(aws ec2 describe-security-groups --filters Name=vpc-id,Values="${vpc}" \
    "Name=group-name,Values=security-group-for-inbound-nfs-*,security-group-for-outbound-nfs-*" \
    --query "SecurityGroups[].GroupId" --output text 2>/dev/null || true)"
  [ -z "${sgs}" ] && return 0
  for sg in ${sgs}; do
    ing="$(aws ec2 describe-security-group-rules --filters Name=group-id,Values="${sg}" \
      --query "SecurityGroupRules[?IsEgress==\`false\`].SecurityGroupRuleId" --output text 2>/dev/null || true)"
    egr="$(aws ec2 describe-security-group-rules --filters Name=group-id,Values="${sg}" \
      --query "SecurityGroupRules[?IsEgress==\`true\`].SecurityGroupRuleId" --output text 2>/dev/null || true)"
    [ -n "${ing}" ] && aws ec2 revoke-security-group-ingress --group-id "${sg}" --security-group-rule-ids ${ing} >/dev/null 2>&1 || true
    [ -n "${egr}" ] && aws ec2 revoke-security-group-egress  --group-id "${sg}" --security-group-rule-ids ${egr} >/dev/null 2>&1 || true
  done
  for sg in ${sgs}; do
    log "  deleting NFS security group ${sg}"
    aws ec2 delete-security-group --group-id "${sg}" 2>/dev/null || warn "   (could not delete ${sg})"
  done
}

unblock_vpc() {
  local vpc="$1"
  log "Unblocking VPC ${vpc} (orphaned EFS mount targets, then NFS security groups)..."
  delete_efs_in_vpc "${vpc}"
  delete_nfs_sgs_in_vpc "${vpc}"
}

# ------------------------------------------------------------------ config ---
PROJECT_NAME="${PROJECT_NAME:-smai-std-project}"
STACK_NAME="${STACK_NAME:-${PROJECT_NAME}-workshop}"
KEEP_TEMPLATE_BUCKET="${KEEP_TEMPLATE_BUCKET:-false}"
KEEP_DATA="${KEEP_DATA:-false}"
DELETE_STUDIO_APPS="${DELETE_STUDIO_APPS:-true}"
FORCE="${FORCE:-false}"

command -v aws >/dev/null 2>&1 || die "aws CLI not found."

REGION="${AWS_REGION:-${AWS_DEFAULT_REGION:-$(aws configure get region 2>/dev/null || true)}}"
[ -n "${REGION}" ] || die "Could not determine AWS region. Set AWS_REGION."
export AWS_DEFAULT_REGION="${REGION}"

ACCOUNT_ID="$(aws sts get-caller-identity --query Account --output text)" \
  || die "Unable to call STS. Are credentials configured (AWS_PROFILE)?"

TEMPLATE_BUCKET="${TEMPLATE_BUCKET:-${PROJECT_NAME}-cfn-${ACCOUNT_ID}-${REGION}}"

# Stack-created buckets (BucketName is derived, so we can compute them).
STACK_BUCKETS=(
  "${PROJECT_NAME}-grants-${ACCOUNT_ID}-${REGION}"
  "${PROJECT_NAME}-data-${ACCOUNT_ID}-${REGION}"
  "${PROJECT_NAME}-mlflow-${ACCOUNT_ID}-${REGION}"
)

log "Account:         ${ACCOUNT_ID}"
log "Region:          ${REGION}"
log "Profile:         ${AWS_PROFILE:-<default/instance>}"
log "Stack to delete: ${STACK_NAME}"
log "Template bucket: ${TEMPLATE_BUCKET} (delete: $([ "${KEEP_TEMPLATE_BUCKET}" = true ] && echo no || echo yes))"
log "Stack buckets:   ${STACK_BUCKETS[*]} (empty: $([ "${KEEP_DATA}" = true ] && echo no || echo yes))"

# Confirm the stack actually exists before proceeding.
if ! aws cloudformation describe-stacks --stack-name "${STACK_NAME}" >/dev/null 2>&1; then
  warn "Stack '${STACK_NAME}' not found in ${ACCOUNT_ID}/${REGION}."
  warn "Nothing to delete via CloudFormation. (Will still offer to remove the template bucket.)"
  STACK_EXISTS=false
else
  STACK_EXISTS=true
fi

# Try to read the real domain id from the stack outputs (fallback: discover).
DOMAIN_ID="$(aws cloudformation describe-stacks --stack-name "${STACK_NAME}" \
  --query "Stacks[0].Outputs[?OutputKey=='SageMakerDomainId'].OutputValue" \
  --output text 2>/dev/null || true)"

# --------------------------------------------------------- confirmation ------
echo
warn "This will PERMANENTLY delete the stack above, its SageMaker domain, and"
warn "the contents of the listed buckets. This cannot be undone."
warn "Lab-created endpoints/models/model-package-groups are NOT touched."
echo
if [ "${FORCE}" != "true" ]; then
  read -r -p "Type 'delete ${PROJECT_NAME}' to proceed: " CONFIRM
  [ "${CONFIRM}" = "delete ${PROJECT_NAME}" ] || die "Confirmation did not match. Aborting."
fi

# --------------------------------------------- step 1: Studio app cleanup ----
if [ "${STACK_EXISTS}" = true ] && [ "${DELETE_STUDIO_APPS}" = true ] && [ -n "${DOMAIN_ID}" ] && [ "${DOMAIN_ID}" != "None" ]; then
  log "Deleting running Studio apps in domain ${DOMAIN_ID} ..."
  # Fields: AppType  AppName  UserProfileName  SpaceName
  APPS="$(aws sagemaker list-apps --domain-id-equals "${DOMAIN_ID}" \
    --query "Apps[?Status!='Deleted' && Status!='Deleting'].[AppType,AppName,UserProfileName,SpaceName]" \
    --output text 2>/dev/null || true)"
  if [ -n "${APPS}" ]; then
    while IFS=$'\t' read -r APP_TYPE APP_NAME UP SP; do
      [ -z "${APP_TYPE}" ] && continue
      if [ -n "${SP}" ] && [ "${SP}" != "None" ]; then
        log "  delete-app space=${SP} ${APP_TYPE}/${APP_NAME}"
        aws sagemaker delete-app --domain-id "${DOMAIN_ID}" --space-name "${SP}" \
          --app-type "${APP_TYPE}" --app-name "${APP_NAME}" 2>/dev/null || warn "  (already gone?)"
      elif [ -n "${UP}" ] && [ "${UP}" != "None" ]; then
        log "  delete-app user=${UP} ${APP_TYPE}/${APP_NAME}"
        aws sagemaker delete-app --domain-id "${DOMAIN_ID}" --user-profile-name "${UP}" \
          --app-type "${APP_TYPE}" --app-name "${APP_NAME}" 2>/dev/null || warn "  (already gone?)"
      fi
    done <<< "${APPS}"

    log "Waiting for apps to finish deleting (up to ~10 min)..."
    for _ in $(seq 1 60); do
      REMAINING="$(aws sagemaker list-apps --domain-id-equals "${DOMAIN_ID}" \
        --query "length(Apps[?Status!='Deleted'])" --output text 2>/dev/null || echo 0)"
      [ "${REMAINING}" = "0" ] && break
      sleep 10
    done
  else
    log "  No running apps found."
  fi
fi

# ----------------------------------------- step 2: empty stack buckets -------
if [ "${KEEP_DATA}" != "true" ]; then
  for b in "${STACK_BUCKETS[@]}"; do
    if aws s3api head-bucket --bucket "${b}" >/dev/null 2>&1; then
      log "Emptying s3://${b} ..."
      aws s3 rm "s3://${b}" --recursive --only-show-errors || warn "  (could not fully empty ${b})"
    fi
  done
fi

# --------------------------------------------- step 3: delete the stack ------
delete_and_wait() {
  aws cloudformation delete-stack --stack-name "${STACK_NAME}"
  aws cloudformation wait stack-delete-complete --stack-name "${STACK_NAME}" 2>/dev/null
}

if [ "${STACK_EXISTS}" = true ]; then
  log "Deleting stack ${STACK_NAME} (this can take 20-40 min)..."
  if delete_and_wait; then
    log "Stack deleted."
  else
    warn "First delete attempt did not complete -- checking for the classic"
    warn "SageMaker VpcOnly blocker (orphaned EFS mount targets + NFS security groups)."
    VPC_ID="$(get_networking_vpc || true)"
    if [ -n "${VPC_ID}" ] && [ "${VPC_ID}" != "None" ]; then
      log "Networking VPC: ${VPC_ID}"
      unblock_vpc "${VPC_ID}"
      log "Retrying stack delete..."
      if delete_and_wait; then
        log "Stack deleted after unblocking the VPC."
      else
        warn "Stack still not deleted. Most recent failed events:"
        aws cloudformation describe-stack-events --stack-name "${STACK_NAME}" \
          --query "StackEvents[?ResourceStatus=='DELETE_FAILED'].[LogicalResourceId,ResourceStatusReason]" \
          --output table 2>/dev/null || true
        warn "Inspect the remaining dependency in VPC ${VPC_ID} and re-run this script."
      fi
    else
      warn "Could not determine the networking VPC to unblock. Most recent failed events:"
      aws cloudformation describe-stack-events --stack-name "${STACK_NAME}" \
        --query "StackEvents[?ResourceStatus=='DELETE_FAILED'].[LogicalResourceId,ResourceStatusReason]" \
        --output table 2>/dev/null || true
    fi
  fi
fi

# ------------------------------------ step 4: delete template bucket ---------
if [ "${KEEP_TEMPLATE_BUCKET}" != "true" ]; then
  if aws s3api head-bucket --bucket "${TEMPLATE_BUCKET}" >/dev/null 2>&1; then
    log "Emptying and deleting template bucket s3://${TEMPLATE_BUCKET} ..."
    aws s3 rm "s3://${TEMPLATE_BUCKET}" --recursive --only-show-errors || true
    aws s3 rb "s3://${TEMPLATE_BUCKET}" || warn "  (could not delete ${TEMPLATE_BUCKET})"
  fi
fi

# ------------------------------------------------- leftovers to verify -------
echo
log "Teardown finished. Verify these manually (not removed automatically):"
log "  * Lab endpoints:      aws sagemaker list-endpoints --query \"Endpoints[].EndpointName\""
log "  * Model pkg groups:   aws sagemaker list-model-package-groups --query \"ModelPackageGroupSummaryList[].ModelPackageGroupName\""
log "  * Leftover ENIs:      aws ec2 describe-network-interfaces --filters Name=description,Values='*SageMaker*' --query \"NetworkInterfaces[].NetworkInterfaceId\""
log "  * Retained/orphan buckets in ${ACCOUNT_ID}/${REGION}"
