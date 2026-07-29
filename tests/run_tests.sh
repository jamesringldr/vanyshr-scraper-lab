#!/bin/bash

# Scraper Unit Tests Runner
# Runs all pytest tests for scrapers: anywho, fps-playwright, zabasearch-relay
#
# Usage:
#   ./run_tests.sh              # Run all tests
#   ./run_tests.sh -v           # Verbose output
#   ./run_tests.sh --fast       # Fast mode (only unit tests, skip slow)
#   ./run_tests.sh -k anywho    # Run only anywho tests
#   ./run_tests.sh --cov        # Include coverage report
#   ./run_tests.sh --log        # Log test results to Supabase
#
# Requirements:
#   - Python 3.8+
#   - pytest installed (pip install pytest)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Default options
PYTEST_ARGS="--tb=short -v"
FILTER=""
COVERAGE=0
LOG_RESULTS=0

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --fast)
            PYTEST_ARGS="$PYTEST_ARGS -m unit"  # Skip slow/integration tests
            shift
            ;;
        --cov)
            COVERAGE=1
            shift
            ;;
        --log)
            LOG_RESULTS=1
            PYTEST_ARGS="$PYTEST_ARGS --log-results"
            shift
            ;;
        -k)
            FILTER="$2"
            shift 2
            ;;
        -v|--verbose)
            PYTEST_ARGS="$PYTEST_ARGS -vv"
            shift
            ;;
        *)
            PYTEST_ARGS="$PYTEST_ARGS $1"
            shift
            ;;
    esac
done

# Add filter if specified
if [ ! -z "$FILTER" ]; then
    PYTEST_ARGS="$PYTEST_ARGS -k $FILTER"
fi

# Add coverage if requested
if [ $COVERAGE -eq 1 ]; then
    PYTEST_ARGS="$PYTEST_ARGS --cov=. --cov-report=html --cov-report=term"
fi

echo -e "${BLUE}════════════════════════════════════════${NC}"
echo -e "${BLUE}Scraper Unit Tests${NC}"
echo -e "${BLUE}════════════════════════════════════════${NC}"
echo ""

# Check if pytest is installed
if ! command -v pytest &> /dev/null; then
    echo -e "${YELLOW}pytest not found. Installing...${NC}"
    pip install pytest pytest-cov
fi

# Run pytest from tests directory
cd "$SCRIPT_DIR"
echo "Running: pytest $PYTEST_ARGS"
echo ""

pytest $PYTEST_ARGS

exit_code=$?

echo ""
echo -e "${BLUE}════════════════════════════════════════${NC}"
if [ $exit_code -eq 0 ]; then
    echo -e "${GREEN}✓ All tests passed!${NC}"
else
    echo -e "${YELLOW}✗ Some tests failed (exit code: $exit_code)${NC}"
fi
echo -e "${BLUE}════════════════════════════════════════${NC}"

exit $exit_code
