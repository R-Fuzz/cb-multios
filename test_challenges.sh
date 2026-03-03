#!/bin/bash
# Test specific challenges against build64 polls.
# Usage: ./test_challenges.sh Challenge1 Challenge2 ...
# Exit criteria: all polls pass (polls failed: 0)
# Source venv if available and bash-compatible, otherwise use system python3
if [ -f venv/bin/activate ] && head -1 venv/bin/activate | grep -qE "^#!/.*bash"; then
    source venv/bin/activate
fi

PASS=0; FAIL=0
for chal in "$@"; do
    xml_dir=""
    for d in "polls/$chal/poller/for-release" "polls/$chal/poller/for-testing" \
             "challenges/$chal/poller/for-release" "challenges/$chal/poller/for-testing"; do
        if [ -d "$d" ] && ls "$d"/*.xml >/dev/null 2>&1; then xml_dir="$d" && break; fi
    done
    if [ -z "$xml_dir" ]; then echo "  SKIP $chal (no polls)"; continue; fi

    binary="build64/challenges/$chal/$chal"
    if [ ! -f "$binary" ]; then echo "  SKIP $chal (no binary)"; continue; fi

    result=$(python tools/cb-test.py --cb $chal --directory build64/challenges/$chal \
        --xml_dir $xml_dir --concurrent 1 --timeout 30 2>&1 | grep -E "^# polls (passed|failed)")
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
