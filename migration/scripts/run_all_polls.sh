#!/bin/bash
#
# Run all poll tests for CGC challenges
#
# This script runs the poll tests for all challenges that have them,
# collecting results and generating a summary report.
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$REPO_ROOT"

# Configuration
LOG_DIR="/tmp/poll_test_logs"
RESULTS_FILE="/tmp/poll_test_results.txt"
SUMMARY_FILE="/tmp/poll_test_summary.txt"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# Create log directory
mkdir -p "$LOG_DIR"

# Initialize results
echo "=== CGC Poll Test Run - $TIMESTAMP ===" > "$RESULTS_FILE"
echo "" >> "$RESULTS_FILE"

# Counters
TOTAL_CHALLENGES=0
PASSED_CHALLENGES=0
FAILED_CHALLENGES=0
SKIPPED_CHALLENGES=0

# Find all challenges with poll tests
echo "Scanning for challenges with poll tests..."
CHALLENGES=()
for poll_dir in polls/*; do
    if [ -d "$poll_dir" ]; then
        challenge=$(basename "$poll_dir")
        CHALLENGES+=("$challenge")
    fi
done

echo "Found ${#CHALLENGES[@]} challenges with poll tests"
echo ""

# Run tests for each challenge
for challenge in "${CHALLENGES[@]}"; do
    TOTAL_CHALLENGES=$((TOTAL_CHALLENGES + 1))

    echo "[$TOTAL_CHALLENGES/${#CHALLENGES[@]}] Testing $challenge..."

    # Check if binary exists
    BINARY_PATH="build64/challenges/$challenge/${challenge}_patched"
    if [ ! -f "$BINARY_PATH" ]; then
        echo "  ⚠ SKIPPED - Binary not found: $BINARY_PATH"
        echo "SKIPPED: $challenge - Binary not found" >> "$RESULTS_FILE"
        SKIPPED_CHALLENGES=$((SKIPPED_CHALLENGES + 1))
        continue
    fi

    # Run the poll tests
    LOG_FILE="$LOG_DIR/${challenge}_poll.log"

    if source venv/bin/activate && python tools/tester.py -c "$challenge" --polls > "$LOG_FILE" 2>&1; then
        # Extract pass/fail counts from log
        PASSED_COUNT=$(grep -oP 'Passed \K\d+(?=/\d+)' "$LOG_FILE" | tail -1 || echo "0")
        TOTAL_COUNT=$(grep -oP 'Passed \d+/\K\d+' "$LOG_FILE" | tail -1 || echo "0")

        if [ "$PASSED_COUNT" = "$TOTAL_COUNT" ] && [ "$TOTAL_COUNT" != "0" ]; then
            echo "  ✓ PASSED - $PASSED_COUNT/$TOTAL_COUNT tests"
            echo "PASSED: $challenge - $PASSED_COUNT/$TOTAL_COUNT tests" >> "$RESULTS_FILE"
            PASSED_CHALLENGES=$((PASSED_CHALLENGES + 1))
        else
            echo "  ✗ FAILED - $PASSED_COUNT/$TOTAL_COUNT tests passed"
            echo "FAILED: $challenge - $PASSED_COUNT/$TOTAL_COUNT tests passed" >> "$RESULTS_FILE"
            FAILED_CHALLENGES=$((FAILED_CHALLENGES + 1))
        fi
    else
        echo "  ✗ ERROR - Test execution failed"
        echo "ERROR: $challenge - Test execution failed" >> "$RESULTS_FILE"
        FAILED_CHALLENGES=$((FAILED_CHALLENGES + 1))
    fi

    echo ""
done

# Generate summary
echo "=== Test Summary ===" | tee "$SUMMARY_FILE"
echo "" | tee -a "$SUMMARY_FILE"
echo "Total challenges tested: $TOTAL_CHALLENGES" | tee -a "$SUMMARY_FILE"
echo "Passed: $PASSED_CHALLENGES" | tee -a "$SUMMARY_FILE"
echo "Failed: $FAILED_CHALLENGES" | tee -a "$SUMMARY_FILE"
echo "Skipped: $SKIPPED_CHALLENGES" | tee -a "$SUMMARY_FILE"
echo "" | tee -a "$SUMMARY_FILE"

if [ $TOTAL_CHALLENGES -gt 0 ]; then
    SUCCESS_RATE=$(awk "BEGIN {printf \"%.1f\", ($PASSED_CHALLENGES/$TOTAL_CHALLENGES)*100}")
    echo "Success rate: $SUCCESS_RATE%" | tee -a "$SUMMARY_FILE"
fi

echo "" | tee -a "$SUMMARY_FILE"
echo "Detailed results: $RESULTS_FILE" | tee -a "$SUMMARY_FILE"
echo "Individual logs: $LOG_DIR/" | tee -a "$SUMMARY_FILE"

# Append summary to results file
echo "" >> "$RESULTS_FILE"
cat "$SUMMARY_FILE" >> "$RESULTS_FILE"

echo ""
echo "Test run complete!"
