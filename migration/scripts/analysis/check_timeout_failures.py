#!/usr/bin/env python3
"""
Parse test_all_challenges.log to find FAIL tests and re-run them without timeout
to determine if failures are due to timeout issues.
"""

import re
import subprocess
import os
import sys
from pathlib import Path

def parse_log_for_failures(log_file):
    """Parse log file and extract all failed tests."""
    failures = []
    current_challenge = None

    with open(log_file, 'r') as f:
        for line in f:
            # Match challenge name like: [2/241] Testing Accel...
            challenge_match = re.search(r'\[\d+/\d+\] Testing (.+?)\.\.\.', line)
            if challenge_match:
                current_challenge = challenge_match.group(1)

            # Match test failures like: Testing GEN_00000_00000.xml... FAIL
            fail_match = re.search(r'Testing (GEN_\d+_\d+\.xml|.*?\.xml).*?FAIL', line)
            if fail_match and current_challenge:
                xml_file = fail_match.group(1)
                failures.append((current_challenge, xml_file))

    return failures

def find_binary_and_xml(challenge, xml_file):
    """Find the binary and XML file paths for a challenge."""
    # Try build64 first, then build
    for build_dir in ['build64', 'build']:
        binary_path = Path(f"{build_dir}/challenges/{challenge}")
        if binary_path.exists():
            # Find the actual binary executable
            binary_files = list(binary_path.glob(f"{challenge}"))
            if not binary_files:
                # For multi-CB challenges, look for cb_1, cb_2, etc.
                binary_files = list(binary_path.glob("cb_*"))

            if binary_files:
                # Find the XML file
                xml_path = Path(f"polls/{challenge}/poller/for-release/{xml_file}")
                if not xml_path.exists():
                    # Try for-testing
                    xml_path = Path(f"polls/{challenge}/poller/for-testing/{xml_file}")

                if xml_path.exists():
                    return binary_files, xml_path, build_dir

    return None, None, None

def run_test_without_timeout(binaries, xml_path):
    """Run cb-replay.py without timeout."""
    cb_replay = Path("tools/cb-replay.py")

    # Build command
    cmd = [
        "python", str(cb_replay),
        "--cbs"
    ]

    # Add all binaries
    for binary in binaries:
        cmd.append(str(binary.absolute()))

    # Set high timeout (300s)
    cmd.extend(["--timeout", "300"])

    # Add XML file with --xml flag
    cmd.extend(["--xml", str(xml_path.absolute())])

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=350  # Give extra time beyond cb-replay timeout
        )
        return result.returncode == 0, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return False, "", "Timed out after 350s"
    except Exception as e:
        return False, "", str(e)

def main():
    log_file = "test_all_challenges.log"

    if not os.path.exists(log_file):
        print(f"Error: {log_file} not found")
        sys.exit(1)

    print("Parsing log file for failures...")
    failures = parse_log_for_failures(log_file)

    print(f"\nFound {len(failures)} failed tests")
    print("=" * 80)

    # Track results
    timeout_related = []
    still_failing = []
    now_passing = []
    not_found = []

    for i, (challenge, xml_file) in enumerate(failures, 1):
        print(f"\n[{i}/{len(failures)}] Testing {challenge} - {xml_file}")

        # Find binary and XML
        binaries, xml_path, build_dir = find_binary_and_xml(challenge, xml_file)

        if binaries is None or xml_path is None:
            print(f"  ⚠️  Could not find binary or XML")
            not_found.append((challenge, xml_file))
            continue

        print(f"  Binary: {binaries}")
        print(f"  XML: {xml_path}")
        print(f"  Build: {build_dir}")

        # Run test without timeout
        success, stdout, stderr = run_test_without_timeout(binaries, xml_path)

        if success:
            print(f"  ✅ PASSED with extended timeout!")
            now_passing.append((challenge, xml_file))
        else:
            print(f"  ❌ Still failing")
            if "timeout" in stderr.lower() or "timed out" in stderr.lower():
                print(f"     (appears to be timeout-related)")
                timeout_related.append((challenge, xml_file))
            else:
                still_failing.append((challenge, xml_file))

            # Show error details
            if stderr:
                print(f"  Error: {stderr[:200]}")

    # Print summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"Total failures analyzed: {len(failures)}")
    print(f"Now passing with extended timeout: {len(now_passing)}")
    print(f"Still failing (timeout-related): {len(timeout_related)}")
    print(f"Still failing (other reasons): {len(still_failing)}")
    print(f"Could not find binary/XML: {len(not_found)}")

    if now_passing:
        print(f"\n✅ Tests that PASS with extended timeout ({len(now_passing)}):")
        for challenge, xml in now_passing[:20]:  # Show first 20
            print(f"  - {challenge}: {xml}")
        if len(now_passing) > 20:
            print(f"  ... and {len(now_passing) - 20} more")

    if timeout_related:
        print(f"\n⏱️  Tests still timing out ({len(timeout_related)}):")
        for challenge, xml in timeout_related[:10]:
            print(f"  - {challenge}: {xml}")
        if len(timeout_related) > 10:
            print(f"  ... and {len(timeout_related) - 10} more")

    if still_failing:
        print(f"\n❌ Tests still failing for other reasons ({len(still_failing)}):")
        for challenge, xml in still_failing[:10]:
            print(f"  - {challenge}: {xml}")
        if len(still_failing) > 10:
            print(f"  ... and {len(still_failing) - 10} more")

if __name__ == "__main__":
    main()
