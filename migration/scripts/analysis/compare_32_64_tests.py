#!/usr/bin/env python3
"""
Systematically test and compare 32-bit vs 64-bit challenge binaries.
Tests each challenge with its polls and compares results.
"""

import os
import sys
import subprocess
import json
from pathlib import Path
from collections import defaultdict

def get_challenge_list():
    """Get list of challenges that exist in both builds."""
    build32 = Path("build/challenges")
    build64 = Path("build64/challenges")

    if not build32.exists() or not build64.exists():
        print("Error: build/ or build64/ directory not found")
        sys.exit(1)

    chals_32 = set(d.name for d in build32.iterdir() if d.is_dir())
    chals_64 = set(d.name for d in build64.iterdir() if d.is_dir())

    return sorted(chals_32 & chals_64)

def has_polls(challenge_name):
    """Check if a challenge has poll tests."""
    polls_dir = Path(f"polls/{challenge_name}")
    if not polls_dir.exists():
        return False

    # Check for poller/for-release or poller/for-testing
    for subdir in ["poller/for-release", "poller/for-testing"]:
        poll_path = polls_dir / subdir
        if poll_path.exists():
            xml_files = list(poll_path.glob("*.xml"))
            if xml_files:
                return True
    return False

def run_test(challenge_name, build_dir, timeout=15):
    """Run cb-test.py for a single challenge."""
    # Find poll XMLs
    polls_dir = Path(f"polls/{challenge_name}")
    xml_dir = None

    for subdir in ["poller/for-release", "poller/for-testing"]:
        poll_path = polls_dir / subdir
        if poll_path.exists() and list(poll_path.glob("*.xml")):
            xml_dir = poll_path
            break

    if not xml_dir:
        return None, "No polls found"

    # Build cb-test.py command
    cb_dir = Path(build_dir) / "challenges" / challenge_name

    cmd = [
        sys.executable,
        "tools/cb-test.py",
        "--cb", challenge_name,
        "--directory", str(cb_dir.absolute()),
        "--xml_dir", str(xml_dir.absolute()),
        "--timeout", str(timeout),
        "--concurrent", "1"
    ]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout * 60  # Overall timeout
        )
        return result.returncode, result.stdout + result.stderr
    except subprocess.TimeoutExpired:
        return -1, "Test timed out"
    except Exception as e:
        return -1, f"Error: {str(e)}"

def main():
    if len(sys.argv) > 1:
        # Test specific challenges
        challenges = sys.argv[1:]
    else:
        # Test all challenges
        challenges = get_challenge_list()
        # Filter to only those with polls
        challenges = [c for c in challenges if has_polls(c)]

    print(f"Found {len(challenges)} challenges with polls to test")
    print()

    results = {}
    passed_both = []
    failed_32_only = []
    failed_64_only = []
    failed_both = []
    different_output = []

    for i, chal in enumerate(challenges, 1):
        print(f"[{i}/{len(challenges)}] Testing {chal}...")

        # Test 32-bit
        print(f"  Running 32-bit... ", end="", flush=True)
        ret_32, output_32 = run_test(chal, "build")
        if ret_32 is None:
            print("SKIP (no polls)")
            continue

        status_32 = "PASS" if ret_32 == 0 else "FAIL"
        print(status_32)

        # Test 64-bit
        print(f"  Running 64-bit... ", end="", flush=True)
        ret_64, output_64 = run_test(chal, "build64")
        status_64 = "PASS" if ret_64 == 0 else "FAIL"
        print(status_64)

        results[chal] = {
            "32-bit": {"return_code": ret_32, "output": output_32},
            "64-bit": {"return_code": ret_64, "output": output_64}
        }

        # Categorize results
        if ret_32 == 0 and ret_64 == 0:
            passed_both.append(chal)
        elif ret_32 != 0 and ret_64 == 0:
            failed_32_only.append(chal)
        elif ret_32 == 0 and ret_64 != 0:
            failed_64_only.append(chal)
        elif ret_32 != 0 and ret_64 != 0:
            failed_both.append(chal)

        print()

    # Print summary
    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"✅ Passed both 32-bit and 64-bit: {len(passed_both)}")
    print(f"⚠️  Failed 32-bit only: {len(failed_32_only)}")
    print(f"⚠️  Failed 64-bit only: {len(failed_64_only)}")
    print(f"❌ Failed both: {len(failed_both)}")
    print()

    if failed_32_only:
        print("Challenges that FAILED 32-bit but PASSED 64-bit:")
        for chal in failed_32_only:
            print(f"  - {chal}")
        print()

    if failed_64_only:
        print("Challenges that PASSED 32-bit but FAILED 64-bit:")
        for chal in failed_64_only:
            print(f"  - {chal}")
        print()

    if failed_both:
        print("Challenges that FAILED both:")
        for chal in failed_both:
            print(f"  - {chal}")
        print()

    # Save detailed results
    results_file = "test_comparison_results.json"
    with open(results_file, 'w') as f:
        json.dump(results, f, indent=2)
    print(f"Detailed results saved to {results_file}")

    return 0 if not failed_64_only else 1

if __name__ == "__main__":
    sys.exit(main())
