#!/bin/bash
#
# Run all poll tests for CGC challenges IN PARALLEL
#
# This script runs poll tests for all single-CB challenges in parallel,
# utilizing multi-core systems for faster testing.
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$REPO_ROOT"

# Configuration
NUM_JOBS=32  # Use 32 parallel jobs (leaving some headroom on 36-thread system)
LOG_DIR="/tmp/poll_test_logs_parallel"
RESULTS_DIR="/tmp/poll_results_parallel"
RESULTS_FILE="/tmp/poll_test_results_parallel.txt"
SUMMARY_FILE="/tmp/poll_test_summary_parallel.txt"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# Create directories
mkdir -p "$LOG_DIR"
mkdir -p "$RESULTS_DIR"

# Initialize results
echo "=== CGC Poll Test Run (Parallel) - $TIMESTAMP ===" > "$RESULTS_FILE"
echo "" >> "$RESULTS_FILE"

# Function to test a single challenge
test_challenge() {
    local challenge=$1
    local result_file="$RESULTS_DIR/${challenge}.result"
    
    # Check if it's a single-CB challenge
    BINARY_PATH="build64/challenges/$challenge/${challenge}_patched"
    
    # Check if binary exists (single CB)
    if [ ! -f "$BINARY_PATH" ]; then
        # Check if it's a multi-CB challenge
        if ls build64/challenges/$challenge/${challenge}_*_patched 2>/dev/null | grep -q .; then
            echo "SKIPPED: $challenge - Multi-CB challenge" > "$result_file"
            return
        fi
        echo "SKIPPED: $challenge - Binary not found" > "$result_file"
        return
    fi
    
    # Run the poll tests
    LOG_FILE="$LOG_DIR/${challenge}_poll.log"
    
    if source venv/bin/activate && timeout 300 python tools/tester.py -c "$challenge" --polls > "$LOG_FILE" 2>&1; then
        # Extract pass/fail counts from log
        PASSED_COUNT=$(grep -oP 'Passed \K\d+(?=/\d+)' "$LOG_FILE" | tail -1 || echo "0")
        TOTAL_COUNT=$(grep -oP 'Passed \d+/\K\d+' "$LOG_FILE" | tail -1 || echo "0")
        
        if [ "$PASSED_COUNT" = "$TOTAL_COUNT" ] && [ "$TOTAL_COUNT" != "0" ]; then
            echo "PASSED: $challenge - $PASSED_COUNT/$TOTAL_COUNT tests" > "$result_file"
        elif [ "$TOTAL_COUNT" = "0" ]; then
            echo "SKIPPED: $challenge - No tests executed" > "$result_file"
        else
            echo "FAILED: $challenge - $PASSED_COUNT/$TOTAL_COUNT tests passed" > "$result_file"
        fi
    else
        EXIT_CODE=$?
        if [ $EXIT_CODE -eq 124 ]; then
            echo "TIMEOUT: $challenge - Test execution timed out after 300s" > "$result_file"
        else
            echo "ERROR: $challenge - Test execution failed (exit code: $EXIT_CODE)" > "$result_file"
        fi
    fi
}

# Export function and variables for parallel execution
export -f test_challenge
export LOG_DIR RESULTS_DIR REPO_ROOT

# Find all challenges with poll tests
echo "Scanning for challenges with poll tests..."
CHALLENGES=()
for poll_dir in polls/*; do
    if [ -d "$poll_dir" ]; then
        challenge=$(basename "$poll_dir")
        CHALLENGES+=("$challenge")
    fi
done

TOTAL_CHALLENGES=${#CHALLENGES[@]}
echo "Found $TOTAL_CHALLENGES challenges with poll tests"
echo "Running tests in parallel with $NUM_JOBS jobs..."
echo ""

# Check if GNU parallel is available
if command -v parallel &> /dev/null; then
    # Use GNU parallel
    printf '%s\n' "${CHALLENGES[@]}" | parallel -j $NUM_JOBS --bar test_challenge {}
else
    # Fallback to xargs
    printf '%s\n' "${CHALLENGES[@]}" | xargs -P $NUM_JOBS -I {} bash -c 'test_challenge "$@"' _ {}
fi

echo ""
echo "All tests completed. Aggregating results..."

# Aggregate results
PASSED_CHALLENGES=0
FAILED_CHALLENGES=0
SKIPPED_CHALLENGES=0
TIMEOUT_CHALLENGES=0
ERROR_CHALLENGES=0
TOTAL_TESTS_PASSED=0
TOTAL_TESTS_RUN=0

for result_file in "$RESULTS_DIR"/*.result; do
    if [ -f "$result_file" ]; then
        result=$(cat "$result_file")
        echo "$result" >> "$RESULTS_FILE"
        
        if [[ $result == PASSED:* ]]; then
            PASSED_CHALLENGES=$((PASSED_CHALLENGES + 1))
            # Extract test counts
            PASSED=$(echo "$result" | grep -oP '\d+(?=/\d+ tests)')
            TOTAL=$(echo "$result" | grep -oP '/\K\d+(?= tests)')
            TOTAL_TESTS_PASSED=$((TOTAL_TESTS_PASSED + PASSED))
            TOTAL_TESTS_RUN=$((TOTAL_TESTS_RUN + TOTAL))
        elif [[ $result == FAILED:* ]]; then
            FAILED_CHALLENGES=$((FAILED_CHALLENGES + 1))
            # Extract test counts
            PASSED=$(echo "$result" | grep -oP '\d+(?=/\d+ tests)' || echo "0")
            TOTAL=$(echo "$result" | grep -oP '/\K\d+(?= tests)' || echo "0")
            TOTAL_TESTS_PASSED=$((TOTAL_TESTS_PASSED + PASSED))
            TOTAL_TESTS_RUN=$((TOTAL_TESTS_RUN + TOTAL))
        elif [[ $result == SKIPPED:* ]]; then
            SKIPPED_CHALLENGES=$((SKIPPED_CHALLENGES + 1))
        elif [[ $result == TIMEOUT:* ]]; then
            TIMEOUT_CHALLENGES=$((TIMEOUT_CHALLENGES + 1))
        elif [[ $result == ERROR:* ]]; then
            ERROR_CHALLENGES=$((ERROR_CHALLENGES + 1))
        fi
    fi
done

# Generate summary
{
    echo "=== Test Summary (Parallel Execution) ==="
    echo ""
    echo "Total challenges: $TOTAL_CHALLENGES"
    echo "Passed: $PASSED_CHALLENGES"
    echo "Failed: $FAILED_CHALLENGES"
    echo "Skipped: $SKIPPED_CHALLENGES"
    echo "Timeout: $TIMEOUT_CHALLENGES"
    echo "Error: $ERROR_CHALLENGES"
    echo ""
    
    if [ $TOTAL_TESTS_RUN -gt 0 ]; then
        echo "Total tests run: $TOTAL_TESTS_RUN"
        echo "Total tests passed: $TOTAL_TESTS_PASSED"
        TEST_SUCCESS_RATE=$(awk "BEGIN {printf \"%.1f\", ($TOTAL_TESTS_PASSED/$TOTAL_TESTS_RUN)*100}")
        echo "Test success rate: $TEST_SUCCESS_RATE%"
        echo ""
    fi
    
    TESTED_CHALLENGES=$((PASSED_CHALLENGES + FAILED_CHALLENGES))
    if [ $TESTED_CHALLENGES -gt 0 ]; then
        CHALLENGE_SUCCESS_RATE=$(awk "BEGIN {printf \"%.1f\", ($PASSED_CHALLENGES/$TESTED_CHALLENGES)*100}")
        echo "Challenge success rate: $CHALLENGE_SUCCESS_RATE%"
    fi
    
    echo ""
    echo "Detailed results: $RESULTS_FILE"
    echo "Individual logs: $LOG_DIR/"
} | tee "$SUMMARY_FILE"

# Append summary to results file
echo "" >> "$RESULTS_FILE"
cat "$SUMMARY_FILE" >> "$RESULTS_FILE"

echo ""
echo "Parallel test run complete!"
echo "Results: $RESULTS_FILE"
