#!/usr/bin/env python3
"""
Simple comparison script that tests 32-bit vs 64-bit using cb-replay.py directly.
"""

import argparse
import os
import sys
import subprocess
from pathlib import Path

def get_poll_xmls(challenge_name):
    """Get list of poll XML files for a challenge."""
    polls_dir = Path(f"polls/{challenge_name}")
    xml_files = []

    for subdir in ["poller/for-release", "poller/for-testing"]:
        poll_path = polls_dir / subdir
        if poll_path.exists():
            xml_files.extend(sorted(poll_path.glob("*.xml")))

    return xml_files

def run_cb_replay(binary_path, xml_file, timeout=600):
    """Run cb-replay.py on a single XML file."""
    cmd = [
        sys.executable,
        "tools/cb-replay.py",
        "--cbs", str(binary_path),
        "--timeout", str(timeout),
        "--xml", str(xml_file)
    ]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout + 10
        )
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return -1, "", "Timeout"
    except Exception as e:
        return -1, "", str(e)

def parse_tap_output(output):
    """Parse TAP output to count passed/failed tests."""
    passed = 0
    failed = 0

    for line in output.split('\n'):
        if '# tests passed:' in line:
            passed = int(line.split(':')[1].strip())
        elif '# tests failed:' in line:
            failed = int(line.split(':')[1].strip())

    return passed, failed

def test_challenge(challenge_name, verbose=False, max_tests=None):
    """Test a single challenge in both 32-bit and 64-bit."""
    bin_32 = Path(f"build/challenges/{challenge_name}/{challenge_name}")
    bin_64 = Path(f"build64/challenges/{challenge_name}/{challenge_name}")

    if not bin_32.exists():
        return None, f"32-bit binary not found"
    if not bin_64.exists():
        return None, f"64-bit binary not found"

    xml_files = get_poll_xmls(challenge_name)
    if not xml_files:
        return None, "No poll XMLs found"

    # Limit number of tests if specified
    if max_tests is not None and max_tests > 0:
        xml_files = xml_files[:max_tests]

    results_32 = []
    results_64 = []
    mismatches = []

    for xml_file in xml_files:
        xml_name = xml_file.name

        if verbose:
            print(f"    Testing {xml_name}... ", end="", flush=True)

        # Test 32-bit
        ret_32, out_32, err_32 = run_cb_replay(bin_32, xml_file)
        passed_32, failed_32 = parse_tap_output(out_32)

        # Test 64-bit
        ret_64, out_64, err_64 = run_cb_replay(bin_64, xml_file)
        passed_64, failed_64 = parse_tap_output(out_64)

        results_32.append((ret_32, passed_32, failed_32))
        results_64.append((ret_64, passed_64, failed_64))

        # Check for mismatches
        if (ret_32, passed_32, failed_32) != (ret_64, passed_64, failed_64):
            mismatches.append({
                'xml': xml_name,
                '32-bit': {'return': ret_32, 'passed': passed_32, 'failed': failed_32, 'output': out_32},
                '64-bit': {'return': ret_64, 'passed': passed_64, 'failed': failed_64, 'output': out_64}
            })

            if verbose:
                print(f"MISMATCH")
        else:
            if verbose:
                status = "PASS" if ret_32 == 0 else "FAIL"
                print(status)

    # Summary
    total_32_passed = sum(p for _, p, _ in results_32)
    total_32_failed = sum(f for _, _, f in results_32)
    total_64_passed = sum(p for _, p, _ in results_64)
    total_64_failed = sum(f for _, _, f in results_64)

    return {
        'xml_count': len(xml_files),
        '32-bit': {'total_passed': total_32_passed, 'total_failed': total_32_failed},
        '64-bit': {'total_passed': total_64_passed, 'total_failed': total_64_failed},
        'mismatches': mismatches
    }, None

def main():
    parser = argparse.ArgumentParser(description='Compare 32-bit vs 64-bit challenge binaries')
    parser.add_argument('challenges', nargs='+', help='Challenge names to test')
    parser.add_argument('--limit', type=int, default=None,
                        help='Limit number of XML tests per challenge (default: all)')
    args = parser.parse_args()

    challenges = args.challenges

    print(f"Testing {len(challenges)} challenge(s)")
    if args.limit:
        print(f"Limiting to {args.limit} test(s) per challenge")
    print()

    all_results = {}
    identical = []
    different = []

    for i, chal in enumerate(challenges, 1):
        print(f"[{i}/{len(challenges)}] {chal}")

        result, error = test_challenge(chal, verbose=True, max_tests=args.limit)

        if error:
            print(f"  ⚠️  Skipped: {error}")
            print()
            continue

        all_results[chal] = result

        if result['mismatches']:
            different.append(chal)
            print(f"  ❌ Found {len(result['mismatches'])} mismatch(es)")
        else:
            identical.append(chal)
            print(f"  ✅ Identical results (32-bit: {result['32-bit']['total_passed']} passed, {result['32-bit']['total_failed']} failed)")

        print()

    # Final summary
    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"✅ Identical behavior: {len(identical)}")
    print(f"❌ Different behavior: {len(different)}")
    print()

    if different:
        print("Challenges with different 32-bit vs 64-bit behavior:")
        for chal in different:
            result = all_results[chal]
            print(f"\n  {chal}:")
            print(f"    32-bit: {result['32-bit']['total_passed']} passed, {result['32-bit']['total_failed']} failed")
            print(f"    64-bit: {result['64-bit']['total_passed']} passed, {result['64-bit']['total_failed']} failed")
            print(f"    Mismatched XMLs: {len(result['mismatches'])}")

            for mismatch in result['mismatches'][:3]:  # Show first 3
                print(f"      - {mismatch['xml']}")

    return 0 if not different else 1

if __name__ == "__main__":
    sys.exit(main())
