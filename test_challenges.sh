#!/bin/bash
# Test specific challenges against build64 polls.
# Usage: ./test_challenges.sh Challenge1 Challenge2 ...
# Exit criteria: all polls pass (polls failed: 0)
source venv/bin/activate

PASS=0; FAIL=0
for chal in "$@"; do
    xml_dir=""
    for d in "polls/$chal/poller/for-release" "polls/$chal/poller/for-testing"; do
        [ -d "$d" ] && xml_dir="$d" && break
    done
    if [ -z "$xml_dir" ]; then echo "  SKIP $chal (no polls)"; continue; fi

    binary="build64/challenges/$chal/$chal"
    if [ ! -f "$binary" ]; then echo "  SKIP $chal (no binary)"; continue; fi

    result=$(python tools/cb-test.py --cb $chal --directory build64/challenges/$chal \
        --xml_dir $xml_dir --concurrent 4 --timeout 15 2>&1 | grep -E "^# polls (passed|failed)")
    passed=$(echo "$result" | grep "passed" | grep -o "[0-9]*$")
    failed=$(echo "$result" | grep "failed" | grep -o "[0-9]*$")
    if [ "${failed:-1}" -eq 0 ]; then
        echo "  PASS $chal ($passed passed)"
        PASS=$((PASS+1))
    else
        echo "  FAIL $chal ($passed passed, $failed failed)"
        FAIL=$((FAIL+1))
    fi
done
echo ""
echo "Summary: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ]  # exit 0 only if all pass
