#!/bin/bash

# Get the directory where the script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SEED_CODE_DIR="$SCRIPT_DIR/classification"

# ---------------------------------------------------------------------------
# LLM fine-tuning seed code:  ./create_zips.sh llm
# ---------------------------------------------------------------------------
# Packages llm-fine-tuning/{model-build-repo,model-deploy-repo} into the zips
# next to them. Running the script with no argument packages classification
# only, exactly as before.
#
# The LLM zips are FLAT (files at the zip root): the SageMaker Project template
# resolves codebuild-buildspec.yml and buildspec.yml at the repository root.
# Neither LLM repo has a .github/ workflow, so the GitHub App nesting rule for
# classification does not apply to them.
LLM_DIR="$SCRIPT_DIR/llm-fine-tuning"

package_llm() {
  local name="$1"                       # model-build-repo | model-deploy-repo
  local root_file="$2"                  # buildspec that must sit at the zip root
  local zip_path="$LLM_DIR/$name.zip"
  local staging list
  staging="$(mktemp -d "${TMPDIR:-/tmp}/llmpkg.XXXXXXXX")"
  echo "==> Packaging llm-fine-tuning/$name"
  cp -R "$LLM_DIR/$name/." "$staging/"
  find "$staging" \( -name __pycache__ -o -name .pytest_cache -o -name .ipynb_checkpoints \) \
    -type d -prune -exec rm -rf {} + 2>/dev/null || true
  find "$staging" \( -name '*.pyc' -o -name '.DS_Store' \) -delete 2>/dev/null || true
  # zip APPENDS to an existing archive, so remove the old one first.
  rm -f "$zip_path"
  ( cd "$staging" && zip -q -r -X "$zip_path" . )
  rm -rf "$staging"
  list="$(unzip -Z1 "$zip_path")"
  printf '%s\n' "$list" | grep -qx -- "$root_file" \
    || { echo "ERROR: $name.zip has no $root_file at the root" >&2; exit 1; }
  if printf '%s\n' "$list" | grep -qE '(^|/)(__pycache__|\.DS_Store|\.ipynb_checkpoints)(/|$)'; then
    echo "ERROR: $name.zip contains build or OS cruft" >&2; exit 1
  fi
  echo "    $name.zip ($(wc -c <"$zip_path" | tr -d ' ') bytes)"
}

if [ "${1:-}" = "llm" ]; then
  set -euo pipefail
  package_llm model-build-repo codebuild-buildspec.yml
  package_llm model-deploy-repo buildspec.yml
  echo
  echo "Created model-build-repo.zip and model-deploy-repo.zip in $LLM_DIR"
  exit 0
fi

cd "$SEED_CODE_DIR"

# Create model-build-repo.zip with model_build folder structure
rm -rf /tmp/build-pkg
mkdir -p /tmp/build-pkg
cp -r model_build /tmp/build-pkg/
cd /tmp/build-pkg
zip -r "$SEED_CODE_DIR/model-build-repo.zip" model_build -x "*__pycache__/*" -x "*.pyc"
cd "$SEED_CODE_DIR"
rm -rf /tmp/build-pkg

# Create model-deploy-repo.zip with model_deploy folder structure
rm -rf /tmp/deploy-pkg
mkdir -p /tmp/deploy-pkg
cp -r model_deploy /tmp/deploy-pkg/
cd /tmp/deploy-pkg
zip -r "$SEED_CODE_DIR/model-deploy-repo.zip" model_deploy -x "*__pycache__/*" -x "*.pyc"
cd "$SEED_CODE_DIR"
rm -rf /tmp/deploy-pkg

echo "Created model-build-repo.zip and model-deploy-repo.zip in $SEED_CODE_DIR"

