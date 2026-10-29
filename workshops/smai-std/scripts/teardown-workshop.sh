#!/usr/bin/env bash
#
# teardown-workshop.sh
#
# Delete everything deploy-workshop.sh created:
#   * the six workshop CloudFormation stacks, in reverse dependency order:
#       <prefix>-okta-federation      (if deployed)
#       <prefix>-data-prep
#       <prefix>-inference-capture
#       <prefix>-sagemaker            (domain, user profiles, spaces, buckets)
#       <prefix>-iam
#       <prefix>-networking
#   * a legacy main.yaml parent stack, if one is still present (pre-split
#     deployments; main.yaml is deprecated)
#   * the S3 template staging bucket deploy-workshop.sh uses to upload templates
#     larger than CloudFormation's 51,200-byte inline limit
#
# It also clears the two things that normally BLOCK a workshop stack delete:
#   * running SageMaker Studio apps in the domain
#   * objects in the stack's grants/data/mlflow buckets (default Delete policy,
#     so a non-empty bucket makes stack deletion fail)
# If the networking stack delete fails (the classic VpcOnly case), it auto-
# unblocks the VPC by deleting the domain's orphaned EFS mount targets +
# filesystem and the inbound/outbound NFS security groups, then retries once.
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
#   ONE EXCEPTION, because it is a hard blocker rather than a preference: a lab
#   endpoint deployed with a VpcConfig holds ENIs in the workshop's private
#   subnets, and the networking stack cannot delete those subnets while they
#   exist. The EFS/NFS unblock above cannot help -- the ENIs belong to a running
#   endpoint, not to orphaned infrastructure. This script detects those endpoints
#   up front and names them. It still will not delete them unless you pass
#   DELETE_LAB_ENDPOINTS=true, because deleting a model endpoint is a different
#   decision from deleting the workshop that hosted it.
#
# Credentials/region (this workstation): set the workshop profile/region via env,
# which the AWS CLI honors natively, e.g.:
#   export AWS_PROFILE=tfc AWS_REGION=us-east-1
# (In CloudShell, leave AWS_PROFILE unset -- it uses the console identity.)
#
# Config (environment variables):
#   PROJECT_NAME          default 'bank-marketing-prediction' (matches deploy-workshop.sh)
#   STACK_PREFIX          default '<PROJECT_NAME>' - prefix of the six stack names
#   STACK_NAME            legacy main.yaml parent stack to also delete
#                         (default '<PROJECT_NAME>-workshop')
#   TEMPLATE_BUCKET       template staging bucket (default '<PROJECT_NAME>-cfn-<acct>-<region>')
#   KEEP_TEMPLATE_BUCKET  'true' to keep the template staging bucket (default false)
#   KEEP_DATA             'true' to NOT empty the grants/data/mlflow buckets
#                         (default false; note: leaving them non-empty will make
#                          the stack delete fail)
#   DELETE_STUDIO_APPS    'true' to delete running Studio apps first (default true)
#   DELETE_LAB_ENDPOINTS  'true' to delete lab endpoints that are VPC-attached to
#                         the workshop VPC and would block subnet deletion
#                         (default false: they are reported, not deleted)
#   FORCE                 'true' to skip the typed confirmation prompt
#
set -euo pipefail

log()  { printf '\033[1;34m[teardown]\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m[warn]\033[0m %s\n'  "$*" >&2; }
die()  { printf '\033[1;31m[error]\033[0m %s\n' "$*" >&2; exit 1; }

# ------------------------------------------------------------------ config ---
PROJECT_NAME="${PROJECT_NAME:-smai-genai-ml-std}"
STACK_PREFIX="${STACK_PREFIX:-${PROJECT_NAME}}"
LEGACY_STACK_NAME="${STACK_NAME:-${PROJECT_NAME}-workshop}"
KEEP_TEMPLATE_BUCKET="${KEEP_TEMPLATE_BUCKET:-false}"
KEEP_DATA="${KEEP_DATA:-false}"
DELETE_STUDIO_APPS="${DELETE_STUDIO_APPS:-true}"
DELETE_LAB_ENDPOINTS="${DELETE_LAB_ENDPOINTS:-false}"
FORCE="${FORCE:-false}"

NETWORKING_STACK="${STACK_PREFIX}-networking"
IAM_STACK="${STACK_PREFIX}-iam"
SAGEMAKER_STACK="${STACK_PREFIX}-sagemaker"
INFERENCE_STACK="${STACK_PREFIX}-inference-capture"
DATA_PREP_STACK="${STACK_PREFIX}-data-prep"
OKTA_STACK="${STACK_PREFIX}-okta-federation"

# Reverse dependency order: dependents first, networking last.
DELETE_ORDER=(
  "${OKTA_STACK}"
  "${DATA_PREP_STACK}"
  "${INFERENCE_STACK}"
  "${SAGEMAKER_STACK}"
  "${IAM_STACK}"
  "${NETWORKING_STACK}"
)

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

# ------------------------------------------------------------- helpers -------
stack_exists() {
  aws cloudformation describe-stacks --stack-name "$1" >/dev/null 2>&1
}

stack_output() {
  local value
  value="$(aws cloudformation describe-stacks --stack-name "$1" \
    --query "Stacks[0].Outputs[?OutputKey=='$2'].OutputValue" \
    --output text 2>/dev/null || true)"
  [ "${value}" = "None" ] && value=""
  printf '%s' "${value}"
}

# --------------------------------------------------- VPC unblock helpers -----
# The SageMaker VpcOnly domain leaves an EFS (with mount targets) and two NFS
# security groups behind. When the domain is deleted during stack teardown,
# these can linger and block subnet/VPC deletion. These helpers remove them.

# Resolve the VPC id. Preferred source is the networking stack's VPCId output;
# falls back to its EC2::VPC resource (works even when the stack is
# DELETE_FAILED), then to the legacy parent's nested NetworkingStack.
get_networking_vpc() {
  local vpc net

  vpc="$(stack_output "${NETWORKING_STACK}" VPCId)"
  if [ -n "${vpc}" ]; then printf '%s' "${vpc}"; return 0; fi

  vpc="$(aws cloudformation describe-stack-resources --stack-name "${NETWORKING_STACK}" \
    --query "StackResources[?ResourceType=='AWS::EC2::VPC'].PhysicalResourceId" \
    --output text 2>/dev/null || true)"
  if [ -n "${vpc}" ] && [ "${vpc}" != "None" ]; then printf '%s' "${vpc}"; return 0; fi

  # Legacy parent stack layout.
  net="$(aws cloudformation describe-stack-resources --stack-name "${LEGACY_STACK_NAME}" \
    --query "StackResources[?LogicalResourceId=='NetworkingStack'].PhysicalResourceId" \
    --output text 2>/dev/null || true)"
  if [ -n "${net}" ] && [ "${net}" != "None" ]; then
    vpc="$(aws cloudformation describe-stack-resources --stack-name "${net}" \
      --query "StackResources[?ResourceType=='AWS::EC2::VPC'].PhysicalResourceId" \
      --output text 2>/dev/null || true)"
    if [ -n "${vpc}" ] && [ "${vpc}" != "None" ]; then printf '%s' "${vpc}"; return 0; fi
  fi

  return 1
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

# ------------------------------------------- VPC-attached endpoint blockers ---
# "The subnet 'subnet-...' has dependencies and cannot be deleted" is almost
# always an ENI still in the subnet. Two very different causes:
#
#   * Orphaned infrastructure (EFS mount targets, NFS security groups) left by
#     the deleted Studio domain -- unblock_vpc clears these, and a retry works.
#   * A RUNNING SageMaker endpoint deployed with a VpcConfig -- unblock_vpc
#     cannot touch these, and retrying forever will not help. The endpoint has
#     to go first, and lab endpoints are outside this script's default scope.
#
# Detecting the second case up front turns an opaque subnet error 30 minutes
# into the teardown into a named resource and a decision before anything starts.

# NOTE: `--output text` separates list values with TABS, not spaces. The
# membership test below pads with spaces and matches on space boundaries, so the
# tabs have to be normalized first -- otherwise every lookup silently misses.
vpc_subnet_ids() {
  aws ec2 describe-subnets --filters Name=vpc-id,Values="$1" \
    --query "Subnets[].SubnetId" --output text 2>/dev/null | tr '\t\n' '  ' || true
}

# Echo the names of endpoints whose model VpcConfig lands in this VPC.
vpc_attached_endpoints() {
  local vpc="$1" subnets endpoint config model model_subnets subnet
  subnets=" $(vpc_subnet_ids "${vpc}") "
  # Only whitespace means no subnets resolved.
  case "${subnets}" in *[![:space:]]*) : ;; *) return 0 ;; esac

  for endpoint in $(aws sagemaker list-endpoints \
      --query "Endpoints[?EndpointStatus!='Deleting'].EndpointName" \
      --output text 2>/dev/null); do
    config="$(aws sagemaker describe-endpoint --endpoint-name "${endpoint}" \
      --query "EndpointConfigName" --output text 2>/dev/null || true)"
    if [ -z "${config}" ] || [ "${config}" = "None" ]; then
      continue
    fi
    # An endpoint config can carry several production variants, each with its
    # own model; any one of them being VPC-attached is enough to block.
    for model in $(aws sagemaker describe-endpoint-config \
        --endpoint-config-name "${config}" \
        --query "ProductionVariants[].ModelName" --output text 2>/dev/null); do
      if [ -z "${model}" ] || [ "${model}" = "None" ]; then
        continue
      fi
      model_subnets="$(aws sagemaker describe-model --model-name "${model}" \
        --query "VpcConfig.Subnets" --output text 2>/dev/null || true)"
      if [ -z "${model_subnets}" ] || [ "${model_subnets}" = "None" ]; then
        continue
      fi
      # Unquoted expansion word-splits on IFS (space, tab, newline), so the
      # tab-separated subnet list from --output text iterates correctly here.
      for subnet in ${model_subnets}; do
        case "${subnets}" in
          *" ${subnet} "*) echo "${endpoint}"; break 2 ;;
        esac
      done
    done
  done
}

# Report whatever ENIs are still in the VPC, with enough detail to identify the
# owner. Used when a delete fails, so the next step is a named resource rather
# than "inspect the remaining dependency".
report_vpc_enis() {
  local vpc="$1" enis
  enis="$(aws ec2 describe-network-interfaces --filters Name=vpc-id,Values="${vpc}" \
    --query "NetworkInterfaces[].[NetworkInterfaceId,InterfaceType,Status,RequesterId,Description]" \
    --output text 2>/dev/null || true)"
  if [ -z "${enis}" ]; then
    log "  No ENIs remain in ${vpc} -- the dependency has cleared, so a retry should succeed."
    return 0
  fi
  warn "  ENIs still in ${vpc}:"
  printf '%s\n' "${enis}" | while IFS=$'\t' read -r id itype status requester desc; do
    warn "    ${id}  type=${itype}  status=${status}  requester=${requester:-?}"
    [ -n "${desc}" ] && warn "      ${desc}"
  done
  warn "  Whatever owns these has to be deleted before the subnets can go."
}

# Delete the named endpoints and wait for their ENIs to be released.
delete_endpoints() {
  local endpoint
  for endpoint in "$@"; do
    log "  deleting endpoint ${endpoint} ..."
    if aws sagemaker delete-endpoint --endpoint-name "${endpoint}" 2>/dev/null; then
      aws sagemaker wait endpoint-deleted --endpoint-name "${endpoint}" 2>/dev/null \
        || warn "   (stopped waiting on ${endpoint}; check its status)"
    else
      warn "   (could not delete ${endpoint}; it may already be gone)"
    fi
  done
  # SageMaker releases the ENIs a little after the endpoint reports deleted.
  log "  waiting for endpoint ENIs to be released ..."
  sleep 30
}

show_delete_failures() {
  aws cloudformation describe-stack-events --stack-name "$1" \
    --query "StackEvents[?ResourceStatus=='DELETE_FAILED'].[LogicalResourceId,ResourceStatusReason]" \
    --output table 2>/dev/null || true
}

# Delete one stack and wait. On failure, try the VpcOnly unblock once, then retry.
delete_stack() {
  local name="$1"
  log "Deleting stack ${name} ..."
  if aws cloudformation delete-stack --stack-name "${name}" 2>/dev/null \
     && aws cloudformation wait stack-delete-complete --stack-name "${name}" 2>/dev/null; then
    log "  ${name} deleted."
    return 0
  fi

  warn "  ${name} did not delete cleanly -- checking for the classic SageMaker"
  warn "  VpcOnly blocker (orphaned EFS mount targets + NFS security groups)."
  if [ -n "${VPC_ID}" ]; then
    unblock_vpc "${VPC_ID}"
    log "  Retrying delete of ${name} ..."
    if aws cloudformation delete-stack --stack-name "${name}" 2>/dev/null \
       && aws cloudformation wait stack-delete-complete --stack-name "${name}" 2>/dev/null; then
      log "  ${name} deleted after unblocking the VPC."
      return 0
    fi
  else
    warn "  No VPC id available to unblock."
  fi

  warn "  ${name} still not deleted. Most recent failed events:"
  show_delete_failures "${name}"
  # Name the actual blocker instead of leaving the user to go hunting.
  if [ -n "${VPC_ID}" ]; then
    report_vpc_enis "${VPC_ID}"
  fi
  return 1
}

# ------------------------------------------------------------- discovery -----
log "Account:         ${ACCOUNT_ID}"
log "Region:          ${REGION}"
log "Profile:         ${AWS_PROFILE:-<default/instance>}"
log "Stack prefix:    ${STACK_PREFIX}"

PRESENT_STACKS=()
for s in "${DELETE_ORDER[@]}"; do
  stack_exists "${s}" && PRESENT_STACKS+=("${s}")
done

LEGACY_PRESENT=false
if stack_exists "${LEGACY_STACK_NAME}"; then
  LEGACY_PRESENT=true
  warn "Legacy main.yaml parent stack found: ${LEGACY_STACK_NAME} (will also be deleted)"
fi

if [ "${#PRESENT_STACKS[@]}" -eq 0 ]; then
  log "Stacks to delete: none found with prefix '${STACK_PREFIX}'"
else
  log "Stacks to delete: ${PRESENT_STACKS[*]}"
fi
log "Template stage:  ${TEMPLATE_BUCKET} (delete: $([ "${KEEP_TEMPLATE_BUCKET}" = true ] && echo no || echo yes))"
log "Stack buckets:   ${STACK_BUCKETS[*]} (empty: $([ "${KEEP_DATA}" = true ] && echo no || echo yes))"

if [ "${#PRESENT_STACKS[@]}" -eq 0 ] && [ "${LEGACY_PRESENT}" = false ]; then
  warn "No workshop stacks found in ${ACCOUNT_ID}/${REGION}."
  warn "Nothing to delete via CloudFormation. (Will still offer to remove the template bucket.)"
fi

# Capture the VPC id BEFORE anything is deleted -- the unblock path needs it
# after the networking stack is already in DELETE_FAILED.
VPC_ID="$(get_networking_vpc || true)"
[ -n "${VPC_ID}" ] && log "Networking VPC:  ${VPC_ID}"

# Domain id for the Studio app cleanup.
DOMAIN_ID="$(stack_output "${SAGEMAKER_STACK}" SageMakerDomainId)"
if [ -z "${DOMAIN_ID}" ] && [ "${LEGACY_PRESENT}" = true ]; then
  DOMAIN_ID="$(stack_output "${LEGACY_STACK_NAME}" SageMakerDomainId)"
fi
[ -n "${DOMAIN_ID}" ] && log "SageMaker domain: ${DOMAIN_ID}"

# Lab endpoints attached to the workshop VPC are a hard blocker on subnet
# deletion. Found now, before the confirmation prompt, so the choice is made
# before 20-40 minutes of deleting rather than after.
BLOCKING_ENDPOINTS=()
if [ -n "${VPC_ID}" ]; then
  while IFS= read -r line; do
    [ -n "${line}" ] && BLOCKING_ENDPOINTS+=("${line}")
  done < <(vpc_attached_endpoints "${VPC_ID}")
fi

if [ "${#BLOCKING_ENDPOINTS[@]}" -gt 0 ]; then
  echo
  warn "VPC-ATTACHED LAB ENDPOINTS DETECTED (${#BLOCKING_ENDPOINTS[@]}):"
  for e in "${BLOCKING_ENDPOINTS[@]}"; do warn "    ${e}"; done
  warn "These hold ENIs in the workshop's private subnets. The networking stack"
  warn "cannot delete those subnets while the endpoints are running, and the"
  warn "EFS/NFS unblock cannot clear them -- the ENIs belong to a live endpoint."
  if [ "${DELETE_LAB_ENDPOINTS}" = "true" ]; then
    warn "DELETE_LAB_ENDPOINTS=true -> they will be deleted before the stacks."
  else
    warn "They will NOT be deleted (DELETE_LAB_ENDPOINTS is false), so the"
    warn "networking stack delete is expected to FAIL. Either delete them first:"
    for e in "${BLOCKING_ENDPOINTS[@]}"; do
      warn "    aws sagemaker delete-endpoint --endpoint-name ${e}"
    done
    warn "or re-run with DELETE_LAB_ENDPOINTS=true to have this script do it."
  fi
fi

# --------------------------------------------------------- confirmation ------
echo
warn "This will PERMANENTLY delete the stacks above, the SageMaker domain, and"
warn "the contents of the listed buckets. This cannot be undone."
if [ "${DELETE_LAB_ENDPOINTS}" = "true" ] && [ "${#BLOCKING_ENDPOINTS[@]}" -gt 0 ]; then
  warn "It will ALSO delete these lab endpoints, which block subnet deletion:"
  for e in "${BLOCKING_ENDPOINTS[@]}"; do warn "    ${e}"; done
  warn "Other lab-created models/model-package-groups are NOT touched."
else
  warn "Lab-created endpoints/models/model-package-groups are NOT touched."
fi
echo
if [ "${FORCE}" != "true" ]; then
  read -r -p "Type 'delete ${PROJECT_NAME}' to proceed: " CONFIRM
  [ "${CONFIRM}" = "delete ${PROJECT_NAME}" ] || die "Confirmation did not match. Aborting."
fi

# --------------------------------------------- step 1: Studio app cleanup ----
if [ "${DELETE_STUDIO_APPS}" = true ] && [ -n "${DOMAIN_ID}" ]; then
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

# ------------------- step 1b: VPC-attached endpoints (opt-in deletion) -------
# Must happen before the stacks go: once the networking stack starts deleting,
# a live endpoint in its subnets fails the delete rather than queueing behind it.
if [ "${#BLOCKING_ENDPOINTS[@]}" -gt 0 ] && [ "${DELETE_LAB_ENDPOINTS}" = "true" ]; then
  log "Deleting ${#BLOCKING_ENDPOINTS[@]} VPC-attached lab endpoint(s) ..."
  delete_endpoints "${BLOCKING_ENDPOINTS[@]}"
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

# ------------------------- step 3: delete the stacks, dependents first -------
# Order matters: data-prep and inference-capture share the Glue database,
# the SageMaker stack owns the domain and buckets, and networking owns the VPC
# that the domain's leftover EFS/ENIs block.
FAILED_STACKS=()
for s in "${DELETE_ORDER[@]}"; do
  if stack_exists "${s}"; then
    delete_stack "${s}" || FAILED_STACKS+=("${s}")
  else
    log "Stack ${s} not present, skipping."
  fi
done

# Legacy parent last: its nested children own their own copies of everything.
if [ "${LEGACY_PRESENT}" = true ]; then
  log "Deleting the legacy main.yaml parent stack (this can take 20-40 min)..."
  delete_stack "${LEGACY_STACK_NAME}" || FAILED_STACKS+=("${LEGACY_STACK_NAME}")
fi

# ------------------------------------ step 4: delete template bucket ---------
# deploy-workshop.sh creates this to stage templates over CloudFormation's
# 51,200-byte inline limit (2-iam.yaml is ~87 KB). Safe to delete: it holds only
# uploaded copies of the templates, which the next deploy re-uploads.
if [ "${KEEP_TEMPLATE_BUCKET}" != "true" ]; then
  if aws s3api head-bucket --bucket "${TEMPLATE_BUCKET}" >/dev/null 2>&1; then
    log "Emptying and deleting template staging bucket s3://${TEMPLATE_BUCKET} ..."
    aws s3 rm "s3://${TEMPLATE_BUCKET}" --recursive --only-show-errors || true
    aws s3 rb "s3://${TEMPLATE_BUCKET}" || warn "  (could not delete ${TEMPLATE_BUCKET})"
  fi
fi

# ------------------------------------------------- leftovers to verify -------
echo
if [ "${#FAILED_STACKS[@]}" -gt 0 ]; then
  warn "These stacks did not delete cleanly: ${FAILED_STACKS[*]}"
  warn "The ENI listing above names what is still holding VPC ${VPC_ID:-<unknown>}."
  if [ "${#BLOCKING_ENDPOINTS[@]}" -gt 0 ] && [ "${DELETE_LAB_ENDPOINTS}" != "true" ]; then
    warn "Most likely cause here: the VPC-attached lab endpoint(s) reported at the"
    warn "start were left running. Re-run with DELETE_LAB_ENDPOINTS=true."
  else
    warn "A subnet dependency is often transient -- the Studio domain releases its"
    warn "EFS mount targets and ENIs a few minutes after the domain itself is gone."
    warn "If the listing above shows no ENIs, just re-run this script."
  fi
fi

log "Teardown finished. Verify these manually (not removed automatically):"
log "  * Lab endpoints:      aws sagemaker list-endpoints --query \"Endpoints[].EndpointName\""
log "  * Model pkg groups:   aws sagemaker list-model-package-groups --query \"ModelPackageGroupSummaryList[].ModelPackageGroupName\""
log "  * Leftover ENIs:      aws ec2 describe-network-interfaces --filters Name=description,Values='*SageMaker*' --query \"NetworkInterfaces[].NetworkInterfaceId\""
log "  * Retained/orphan buckets in ${ACCOUNT_ID}/${REGION}"
