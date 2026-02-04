#!/bin/bash
# Test script to verify all files are syntactically correct

echo "=========================================="
echo "  Testing All Migration Advisor Files"
echo "=========================================="
echo ""

# Color codes
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Test counter
PASSED=0
FAILED=0

# Function to test Python file
test_python() {
    local file=$1
    echo -n "Testing $file... "
    if python3 -m py_compile "$file" 2>/dev/null; then
        echo -e "${GREEN}✓ PASS${NC}"
        ((PASSED++))
    else
        echo -e "${RED}✗ FAIL${NC}"
        python3 -m py_compile "$file"
        ((FAILED++))
    fi
}

# Function to test shell script
test_shell() {
    local file=$1
    echo -n "Testing $file... "
    if bash -n "$file" 2>/dev/null; then
        echo -e "${GREEN}✓ PASS${NC}"
        ((PASSED++))
    else
        echo -e "${RED}✗ FAIL${NC}"
        bash -n "$file"
        ((FAILED++))
    fi
}

echo "Testing Python Files:"
echo "--------------------"
test_python "sagemaker_migration_advisor_lite.py"
test_python "sagemaker_migration_advisor.py"
test_python "launch_advisor.py"
test_python "run_sagemaker_migration_advisor_main.py"
test_python "pdf_report_generator.py"
test_python "diagram_generator.py"
test_python "prompts.py"
test_python "prompts_lite.py"

echo ""
echo "Testing Shell Scripts:"
echo "---------------------"
test_shell "launch_lite.sh"
test_shell "launch_regular.sh"

echo ""
echo "Testing Batch Files:"
echo "-------------------"
if [ -f "launch_lite.bat" ]; then
    echo -n "Testing launch_lite.bat... "
    echo -e "${GREEN}✓ EXISTS${NC}"
    ((PASSED++))
else
    echo -n "Testing launch_lite.bat... "
    echo -e "${RED}✗ MISSING${NC}"
    ((FAILED++))
fi

if [ -f "launch_regular.bat" ]; then
    echo -n "Testing launch_regular.bat... "
    echo -e "${GREEN}✓ EXISTS${NC}"
    ((PASSED++))
else
    echo -n "Testing launch_regular.bat... "
    echo -e "${RED}✗ MISSING${NC}"
    ((FAILED++))
fi

echo ""
echo "Testing Documentation:"
echo "---------------------"
docs=("README.md" "QUICK_START.md" "LAUNCHER_OPTIONS.md" "LAUNCHERS_README.md" "LAUNCHER_GUIDE.md" "TROUBLESHOOTING.md" "FIXED_ISSUES.md")

for doc in "${docs[@]}"; do
    if [ -f "$doc" ]; then
        echo -n "Testing $doc... "
        echo -e "${GREEN}✓ EXISTS${NC}"
        ((PASSED++))
    else
        echo -n "Testing $doc... "
        echo -e "${RED}✗ MISSING${NC}"
        ((FAILED++))
    fi
done

echo ""
echo "=========================================="
echo "  Test Results"
echo "=========================================="
echo -e "Passed: ${GREEN}$PASSED${NC}"
echo -e "Failed: ${RED}$FAILED${NC}"
echo ""

if [ $FAILED -eq 0 ]; then
    echo -e "${GREEN}✓ All tests passed!${NC}"
    echo ""
    echo "Ready to launch:"
    echo "  ./launch_lite.sh"
    echo "  ./launch_regular.sh"
    echo "  python launch_advisor.py"
    echo "  python run_sagemaker_migration_advisor_main.py"
    exit 0
else
    echo -e "${RED}✗ Some tests failed${NC}"
    exit 1
fi
