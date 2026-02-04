#!/bin/bash

# Script to publish mlp_sdk to PyPI
# Usage: ./publish_to_pypi.sh [test|prod]

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Default to test environment
ENVIRONMENT=${1:-test}

echo -e "${GREEN}=== mlp_sdk PyPI Publishing Script ===${NC}\n"

# Check if required tools are installed
echo "Checking required tools..."
if ! command -v python &> /dev/null; then
    echo -e "${RED}Error: Python is not installed${NC}"
    exit 1
fi

if ! python -c "import build" &> /dev/null; then
    echo -e "${YELLOW}Installing build tool...${NC}"
    pip install --upgrade build
fi

if ! python -c "import twine" &> /dev/null; then
    echo -e "${YELLOW}Installing twine...${NC}"
    pip install --upgrade twine
fi

echo -e "${GREEN}✓ All required tools are installed${NC}\n"

# Clean previous builds
echo "Cleaning previous builds..."
rm -rf dist/ build/ *.egg-info mlp_sdk.egg-info
echo -e "${GREEN}✓ Cleaned${NC}\n"

# Run tests (optional)
read -p "Do you want to run tests before building? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "Running tests..."
    if command -v pytest &> /dev/null; then
        pytest tests/ || {
            echo -e "${RED}Tests failed! Aborting.${NC}"
            exit 1
        }
        echo -e "${GREEN}✓ Tests passed${NC}\n"
    else
        echo -e "${YELLOW}pytest not found, skipping tests${NC}\n"
    fi
fi

# Build the package
echo "Building package..."
python -m build
echo -e "${GREEN}✓ Package built successfully${NC}\n"

# Check the package
echo "Checking package..."
python -m twine check dist/*
echo -e "${GREEN}✓ Package check passed${NC}\n"

# List built files
echo "Built files:"
ls -lh dist/
echo

# Upload based on environment
if [ "$ENVIRONMENT" = "test" ]; then
    echo -e "${YELLOW}Uploading to TestPyPI...${NC}"
    echo "You can test the package with:"
    echo "  pip install --index-url https://test.pypi.org/simple/ --no-deps mlp_sdk"
    echo
    python -m twine upload --repository testpypi dist/*
    echo -e "${GREEN}✓ Successfully uploaded to TestPyPI${NC}"
    echo "View at: https://test.pypi.org/project/mlp-sdk/"
elif [ "$ENVIRONMENT" = "prod" ]; then
    echo -e "${RED}WARNING: You are about to upload to PRODUCTION PyPI!${NC}"
    read -p "Are you sure? This cannot be undone. (yes/no) " -r
    echo
    if [[ $REPLY = "yes" ]]; then
        echo -e "${YELLOW}Uploading to PyPI...${NC}"
        python -m twine upload dist/*
        echo -e "${GREEN}✓ Successfully uploaded to PyPI${NC}"
        echo "View at: https://pypi.org/project/mlp-sdk/"
        echo "Install with: pip install mlp_sdk"
    else
        echo "Upload cancelled."
        exit 0
    fi
else
    echo -e "${RED}Invalid environment: $ENVIRONMENT${NC}"
    echo "Usage: $0 [test|prod]"
    exit 1
fi

echo -e "\n${GREEN}=== Publishing Complete ===${NC}"
