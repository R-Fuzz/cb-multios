#!/bin/bash
#
# Run poll tests for all challenges that use maths64.S functions
#
# This script focuses on testing the 83 challenges that use math functions
# to validate that all math library fixes are working correctly.
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$REPO_ROOT"

# Configuration
LOG_DIR="/tmp/math_poll_test_logs"
RESULTS_FILE="/tmp/math_poll_results.txt"
SUMMARY_FILE="/tmp/math_poll_summary.txt"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# Create log directory
mkdir -p "$LOG_DIR"

# Initialize results
echo "=== Math Challenges Poll Test Run - $TIMESTAMP ===" > "$RESULTS_FILE"
echo "" >> "$RESULTS_FILE"

# List of 83 challenges that use math functions (from our analysis)
MATH_CHALLENGES=(
    "3D_Image_Toolkit"
    "Accel"
    "A_Game_of_Chance"
    "anagram_game"
    "Audio_Visualizer"
    "Azurad"
    "basic_emulator"
    "BIRC"
    "Blubber"
    "CGC_Hangman_Game"
    "Childs_Game"
    "CML"
    "commerce_webscale"
    "Corinth"
    "cyber_blogger"
    "Dive_Logger"
    "Divelogger2"
    "ECM_TCM_Simulator"
    "Enslavednode_chat"
    "Estadio"
    "FailAV"
    "Finicky_File_Folder"
    "Flash_File_System"
    "Fortress"
    "FSK_Messaging_Service"
    "FUN"
    "Game_Night"
    "GPS_Tracker"
    "Gridder"
    "Griswold"
    "Grit"
    "H20FlowInc"
    "HIGHCOO"
    "humaninterface"
    "Image_Compressor"
    "Kaprica_Script_Interpreter"
    "LazyCalc"
    "Lazybox"
    "Messaging"
    "middleout"
    "middleware_handshake"
    "Monster_Game"
    "Mount_Filemore"
    "Movie_Rental_Service"
    "Movie_Rental_Service_Redux"
    "Multi_User_Calendar"
    "Multipass"
    "Multipass2"
    "Multipass3"
    "netstorage"
    "Neural_House"
    "One_Amp"
    "online_job_application"
    "online_job_application2"
    "OTPSim"
    "Pac_for_Edges"
    "Parking_Permit_Management_System_PPMS"
    "Pattern_Finder"
    "pizza_ordering_system"
    "PKK_Steganography"
    "Printer"
    "QuadtreeConways"
    "Recipe_and_Pantry_Manager"
    "root64_and_parcour"
    "router_simulator"
    "RRPN"
    "Sad_Face_Template_Engine_SFTE"
    "SAuth"
    "Scrum_Database"
    "Secure_Compression"
    "Sensr"
    "ShoutCTF"
    "SIGSEGV"
    "simple_integer_calculator"
    "simplenote"
    "simpleOCR"
    "Sorter"
    "Space_Attackers"
    "SPIFFS"
    "Square_Rabbit"
    "stream_vm"
    "stream_vm2"
    "Terrible_Ticket_Tracker"
    "TextSearch"
    "Tick-A-Tack"
    "university_enrollment"
    "Venture_Calculator"
    "vFilter"
    "Virtual_Machine"
    "XStore"
)

# Counters
TOTAL_CHALLENGES=0
PASSED_CHALLENGES=0
FAILED_CHALLENGES=0
SKIPPED_CHALLENGES=0
TOTAL_TESTS_PASSED=0
TOTAL_TESTS_RUN=0

echo "Testing ${#MATH_CHALLENGES[@]} math-using challenges..."
echo ""

# Run tests for each challenge
for challenge in "${MATH_CHALLENGES[@]}"; do
    TOTAL_CHALLENGES=$((TOTAL_CHALLENGES + 1))

    printf "[%3d/%3d] Testing %-50s" "$TOTAL_CHALLENGES" "${#MATH_CHALLENGES[@]}" "$challenge..."

    # Check if binary exists
    BINARY_PATH="build64/challenges/$challenge/${challenge}_patched"
    if [ ! -f "$BINARY_PATH" ]; then
        echo " ⚠ SKIPPED (no binary)"
        echo "SKIPPED: $challenge - Binary not found" >> "$RESULTS_FILE"
        SKIPPED_CHALLENGES=$((SKIPPED_CHALLENGES + 1))
        continue
    fi

    # Check if polls exist
    POLL_DIR="polls/$challenge"
    if [ ! -d "$POLL_DIR" ]; then
        echo " ⚠ SKIPPED (no polls)"
        echo "SKIPPED: $challenge - No poll tests" >> "$RESULTS_FILE"
        SKIPPED_CHALLENGES=$((SKIPPED_CHALLENGES + 1))
        continue
    fi

    # Run the poll tests
    LOG_FILE="$LOG_DIR/${challenge}_poll.log"

    if source venv/bin/activate && timeout 300 python tools/tester.py -c "$challenge" --polls > "$LOG_FILE" 2>&1; then
        # Extract pass/fail counts from log
        PASSED_COUNT=$(grep -oP 'Passed \K\d+(?=/\d+)' "$LOG_FILE" | tail -1 || echo "0")
        TOTAL_COUNT=$(grep -oP 'Passed \d+/\K\d+' "$LOG_FILE" | tail -1 || echo "0")

        TOTAL_TESTS_PASSED=$((TOTAL_TESTS_PASSED + PASSED_COUNT))
        TOTAL_TESTS_RUN=$((TOTAL_TESTS_RUN + TOTAL_COUNT))

        if [ "$PASSED_COUNT" = "$TOTAL_COUNT" ] && [ "$TOTAL_COUNT" != "0" ]; then
            echo " ✓ PASSED ($PASSED_COUNT/$TOTAL_COUNT)"
            echo "PASSED: $challenge - $PASSED_COUNT/$TOTAL_COUNT tests" >> "$RESULTS_FILE"
            PASSED_CHALLENGES=$((PASSED_CHALLENGES + 1))
        elif [ "$TOTAL_COUNT" = "0" ]; then
            echo " ⚠ SKIPPED (no tests run)"
            echo "SKIPPED: $challenge - No tests executed" >> "$RESULTS_FILE"
            SKIPPED_CHALLENGES=$((SKIPPED_CHALLENGES + 1))
        else
            echo " ✗ FAILED ($PASSED_COUNT/$TOTAL_COUNT)"
            echo "FAILED: $challenge - $PASSED_COUNT/$TOTAL_COUNT tests passed" >> "$RESULTS_FILE"
            FAILED_CHALLENGES=$((FAILED_CHALLENGES + 1))
        fi
    else
        EXIT_CODE=$?
        if [ $EXIT_CODE -eq 124 ]; then
            echo " ✗ TIMEOUT"
            echo "TIMEOUT: $challenge - Test execution timed out after 300s" >> "$RESULTS_FILE"
        else
            echo " ✗ ERROR"
            echo "ERROR: $challenge - Test execution failed (exit code: $EXIT_CODE)" >> "$RESULTS_FILE"
        fi
        FAILED_CHALLENGES=$((FAILED_CHALLENGES + 1))
    fi
done

# Generate summary
echo ""
echo "=== Math Challenges Test Summary ===" | tee "$SUMMARY_FILE"
echo "" | tee -a "$SUMMARY_FILE"
echo "Total math challenges: ${#MATH_CHALLENGES[@]}" | tee -a "$SUMMARY_FILE"
echo "Tested: $TOTAL_CHALLENGES" | tee -a "$SUMMARY_FILE"
echo "Passed: $PASSED_CHALLENGES" | tee -a "$SUMMARY_FILE"
echo "Failed: $FAILED_CHALLENGES" | tee -a "$SUMMARY_FILE"
echo "Skipped: $SKIPPED_CHALLENGES" | tee -a "$SUMMARY_FILE"
echo "" | tee -a "$SUMMARY_FILE"

if [ $TOTAL_TESTS_RUN -gt 0 ]; then
    echo "Total tests run: $TOTAL_TESTS_RUN" | tee -a "$SUMMARY_FILE"
    echo "Total tests passed: $TOTAL_TESTS_PASSED" | tee -a "$SUMMARY_FILE"
    TEST_SUCCESS_RATE=$(awk "BEGIN {printf \"%.1f\", ($TOTAL_TESTS_PASSED/$TOTAL_TESTS_RUN)*100}")
    echo "Test success rate: $TEST_SUCCESS_RATE%" | tee -a "$SUMMARY_FILE"
    echo "" | tee -a "$SUMMARY_FILE"
fi

if [ $TOTAL_CHALLENGES -gt 0 ]; then
    CHALLENGE_SUCCESS_RATE=$(awk "BEGIN {printf \"%.1f\", ($PASSED_CHALLENGES/$TOTAL_CHALLENGES)*100}")
    echo "Challenge success rate: $CHALLENGE_SUCCESS_RATE%" | tee -a "$SUMMARY_FILE"
fi

echo "" | tee -a "$SUMMARY_FILE"
echo "Detailed results: $RESULTS_FILE" | tee -a "$SUMMARY_FILE"
echo "Individual logs: $LOG_DIR/" | tee -a "$SUMMARY_FILE"

# Append summary to results file
echo "" >> "$RESULTS_FILE"
cat "$SUMMARY_FILE" >> "$RESULTS_FILE"

echo ""
echo "Math challenge test run complete!"
