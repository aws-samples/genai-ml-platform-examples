#!/bin/bash

# Get the directory where the script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SEED_CODE_DIR="$SCRIPT_DIR/seed-code/bank-classification"

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

