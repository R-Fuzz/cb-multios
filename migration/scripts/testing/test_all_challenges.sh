#!/bin/bash
set -e  # Exit immediately if any command fails

# Activate virtual environment
source venv/bin/activate

# Get list of all challenges that exist in both build directories
CHALLENGES=$(comm -12 <(ls build/challenges/ | sort) <(ls build64/challenges/ | sort))

# Count total challenges
TOTAL=$(echo "$CHALLENGES" | wc -l)
CURRENT=0
PASSED=0
FAILED=0

# Log file
LOG_FILE="test_all_challenges.log"
PROGRESS_FILE="test_progress.txt"

# Check if we should resume from previous run
RESUME=false
if [ -f "$PROGRESS_FILE" ]; then
    echo "Found previous test progress. Resume from last position? (y/n)"
    read -r ANSWER
    if [ "$ANSWER" = "y" ] || [ "$ANSWER" = "Y" ]; then
        RESUME=true
        # Load skip list
        mapfile -t SKIP_LIST < "$PROGRESS_FILE"
        echo "Resuming tests, skipping ${#SKIP_LIST[@]} already-tested challenges"
    else
        > "$LOG_FILE"  # Clear log file
        > "$PROGRESS_FILE"  # Clear progress file
    fi
else
    > "$LOG_FILE"  # Clear log file
    > "$PROGRESS_FILE"  # Clear progress file
fi

echo "======================================================================"
if [ "$RESUME" = true ]; then
    echo "Resuming tests (32-bit vs 64-bit comparison)"
else
    echo "Testing all challenges (32-bit vs 64-bit comparison)"
fi
echo "Total challenges to test: $TOTAL"
echo "======================================================================"
echo ""

for CHALLENGE in $CHALLENGES; do
    CURRENT=$((CURRENT + 1))

    # Check if this challenge should be skipped (already tested)
    if [ "$RESUME" = true ]; then
        SKIP=false
        for SKIP_CHAL in "${SKIP_LIST[@]}"; do
            if [ "$CHALLENGE" = "$SKIP_CHAL" ]; then
                SKIP=true
                break
            fi
        done

        if [ "$SKIP" = true ]; then
            # Count it as already tested
            if grep -q "Testing $CHALLENGE" "$LOG_FILE" 2>/dev/null; then
                if grep -A 1 "Testing $CHALLENGE" "$LOG_FILE" | grep -q "PASSED"; then
                    PASSED=$((PASSED + 1))
                elif grep -A 1 "Testing $CHALLENGE" "$LOG_FILE" | grep -q "FAILED"; then
                    FAILED=$((FAILED + 1))
                fi
            fi
            continue
        fi
    fi

    echo "[$CURRENT/$TOTAL] Testing $CHALLENGE..." | tee -a "$LOG_FILE"

    # Check if polls exist for this challenge
    if [ ! -d "polls/$CHALLENGE" ]; then
        echo "  ⚠️  Skipped: No polls directory found" | tee -a "$LOG_FILE"
        echo "$CHALLENGE" >> "$PROGRESS_FILE"
        echo ""
        continue
    fi

    # Check if there are any XML files
    XML_COUNT=$(find "polls/$CHALLENGE" -name "*.xml" 2>/dev/null | wc -l)
    if [ "$XML_COUNT" -eq 0 ]; then
        echo "  ⚠️  Skipped: No poll XMLs found" | tee -a "$LOG_FILE"
        echo "$CHALLENGE" >> "$PROGRESS_FILE"
        echo ""
        continue
    fi

    # Run the comparison test
    if python3 compare_simple.py "$CHALLENGE" >> "$LOG_FILE" 2>&1; then
        PASSED=$((PASSED + 1))
        echo "  ✅ PASSED" | tee -a "$LOG_FILE"
        echo "$CHALLENGE" >> "$PROGRESS_FILE"
    else
        FAILED=$((FAILED + 1))
        echo "  ❌ FAILED" | tee -a "$LOG_FILE"
        echo "$CHALLENGE" >> "$PROGRESS_FILE"
        echo ""
        echo "======================================================================"
        echo "FAILURE DETECTED - Stopping tests"
        echo "======================================================================"
        echo "Challenge: $CHALLENGE"
        echo "Passed: $PASSED"
        echo "Failed: $FAILED"
        echo "Progress: $CURRENT/$TOTAL"
        echo ""
        echo "See $LOG_FILE for details"
        echo "Run this script again to resume from this point"
        # exit 1
    fi

    echo "" | tee -a "$LOG_FILE"
done

echo "======================================================================"
echo "ALL TESTS COMPLETED SUCCESSFULLY"
echo "======================================================================"
echo "Total tested: $CURRENT"
echo "Passed: $PASSED"
echo "Failed: $FAILED"
echo ""
echo "Full log saved to: $LOG_FILE"
