#!/bin/bash
#
# Package the classification seed code into the two zips the workshop deploy
# pulls when a SageMaker Project is created.
#
# These zips are the ARTIFACT THAT SHIPS. The tracked source trees under
# seed-code/classification/{model_build,model_deploy} are the source of truth,
# and this script is the only thing that should ever produce the zips -- both had
# previously been hand-repacked, which left them carrying files that no longer
# existed in the tree and missing fixes that did.
#
# Two layout rules are load-bearing, and are asserted below:
#
#   1. Everything must nest under model_build/ or model_deploy/. The
#      CodeConnection GitHub App ("AWS Connector for GitHub", AWS-owned) refuses
#      to push a workflow file that lands at the repository ROOT, and the push is
#      atomic, so a flat zip leaves the seeded repo completely EMPTY. The
#      walkthrough's setup_workflow.sh moves the workflow to the root later,
#      using the participant's PAT, which does have workflow scope.
#
#   2. The vendored dataset schema must match the canonical one. Feature order is
#      a positional contract; drift there produces wrong predictions rather than
#      an error.
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
SEED_CODE_DIR="$SCRIPT_DIR/classification"

# Excluded from the zips: build noise, macOS cruft, and the design doc, which
# documents a superseded Glue/CSV design and would mislead a participant reading
# it inside their own repo. It stays in the workshop repo as history.
PRUNE_DIRS=(docs __pycache__ .pytest_cache .ipynb_checkpoints)

# ---------------------------------------------------------------------------
# Guard: the vendored dataset schema must not have drifted
# ---------------------------------------------------------------------------
echo "==> Checking the vendored dataset schema"
python3 "$REPO_ROOT/scripts/check-vendored-schema.py"

# ---------------------------------------------------------------------------
# Package
# ---------------------------------------------------------------------------
package() {
  local name="$1"                       # model_build | model_deploy
  local zip_path="$SEED_CODE_DIR/${name//_/-}-repo.zip"
  local staging
  staging="$(mktemp -d "${TMPDIR:-/tmp}/seedpkg.XXXXXXXX")"

  echo "==> Packaging $name"
  cp -R "$SEED_CODE_DIR/$name" "$staging/"

  for dir in "${PRUNE_DIRS[@]}"; do
    find "$staging/$name" -name "$dir" -type d -prune -exec rm -rf {} + 2>/dev/null || true
  done
  find "$staging/$name" -name '*.pyc' -delete 2>/dev/null || true
  find "$staging/$name" -name '.DS_Store' -delete 2>/dev/null || true

  # zip APPENDS to an existing archive, so a stale target silently survives
  # repackaging. This is how the shipped zips drifted from the tree before.
  rm -f "$zip_path"
  ( cd "$staging" && zip -q -r -X "$zip_path" "$name" )

  rm -rf "$staging"
  echo "    $(basename "$zip_path") ($(wc -c <"$zip_path" | tr -d ' ') bytes)"
}

package model_build
package model_deploy

# ---------------------------------------------------------------------------
# Verify
# ---------------------------------------------------------------------------
fail() { echo "ERROR: $1" >&2; exit 1; }

# Capture each archive's listing ONCE, then grep the captured string. Piping
# `unzip -Z1 | grep -q` is a trap under `set -o pipefail`: grep -q exits the
# instant it matches, unzip gets SIGPIPE, and the pipeline's exit status is
# unzip's failure -- so a *successful* early match reads as an error. It only
# bites patterns that match near the top of the listing, which is exactly what
# require_present looks for. Grepping a variable sidesteps the pipe entirely
# (and is faster: one unzip per archive, not one per pattern).
listing() {
  local zip_path="$1"
  unzip -Z1 "$zip_path"
}

verify_nesting() {
  local zip_path="$1" expected="$2"
  local roots
  roots="$(listing "$zip_path" | awk -F/ '{print $1}' | sort -u)"
  [ "$roots" = "$expected" ] \
    || fail "$(basename "$zip_path") top-level is '$roots', expected '$expected'. A flat zip makes the GitHub App reject the seed push and leaves the repo empty."
}

require_absent() {
  local zip_path="$1"; shift
  local list
  list="$(listing "$zip_path")"
  for pattern in "$@"; do
    if printf '%s\n' "$list" | grep -q -- "$pattern"; then
      fail "$(basename "$zip_path") still contains '$pattern'"
    fi
  done
}

require_present() {
  local zip_path="$1"; shift
  local list
  list="$(listing "$zip_path")"
  for pattern in "$@"; do
    printf '%s\n' "$list" | grep -q -- "$pattern" \
      || fail "$(basename "$zip_path") is missing '$pattern'"
  done
}

echo "==> Verifying archives"
BUILD_ZIP="$SEED_CODE_DIR/model-build-repo.zip"
DEPLOY_ZIP="$SEED_CODE_DIR/model-deploy-repo.zip"

verify_nesting "$BUILD_ZIP" model_build
verify_nesting "$DEPLOY_ZIP" model_deploy

# The workflow must sit at a NON-root path inside the archive (rule 1 above).
require_present "$BUILD_ZIP" "model_build/.github/workflows/build.yml"
require_present "$DEPLOY_ZIP" "model_deploy/.github/workflows/deploy.yml"

# The pipeline's own contract: handler, packaging step and feature schema.
require_present "$BUILD_ZIP" \
  "model_build/source_scripts/inference/inference.py" \
  "model_build/source_scripts/inference/repack.py" \
  "model_build/config/dataset_schema.yaml" \
  "model_build/ml_pipelines/_dataset_schema.py"

# Removed by the Iceberg rewiring; must not reappear via a stale archive.
require_absent "$BUILD_ZIP" \
  "bank-marketing-dataset.csv" \
  "upload_s3_util.py" \
  "getting_started.ipynb" \
  "model_build/docs/" \
  "__pycache__"

# ml_pipelines/schema.py would shadow the PyPI 'schema' package that
# sagemaker.clarify imports, breaking 'import sagemaker' in CI.
if printf '%s\n' "$(listing "$BUILD_ZIP")" | grep -qx "model_build/ml_pipelines/schema.py"; then
  fail "model-build-repo.zip contains ml_pipelines/schema.py, which shadows the PyPI 'schema' package and breaks 'import sagemaker'"
fi

require_absent "$DEPLOY_ZIP" "__pycache__" ".DS_Store"

echo
echo "Created model-build-repo.zip and model-deploy-repo.zip in $SEED_CODE_DIR"
