#!/usr/bin/env python3
"""
Automated debugging agent for 64-bit porting issues.

This agent follows the manual debugging workflow:
1. Identify failed challenges from test results
2. Run cb-replay on failed poll tests to observe failure type
3. Use cb-replay-gdb for hangs/crashes, cb-replay-strace for I/O issues
4. Hypothesize root cause based on common patterns
5. Once fixed, verify no 32-bit regression
6. Run compare_simple.py to verify all tests pass
"""

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from collections import defaultdict


class DebugAgent:
    def __init__(self, verbose=False, dry_run=False):
        self.verbose = verbose
        self.dry_run = dry_run
        self.root_dir = Path.cwd()
        self.migration_docs = self.root_dir / "migration" / "docs"

    def log(self, msg, level="INFO"):
        """Print log message with level."""
        print(f"[{level}] {msg}")

    def run_command(self, cmd, description, timeout=None, capture=True):
        """Run a command and return output."""
        if self.verbose:
            self.log(f"Running: {' '.join(cmd)}", "DEBUG")

        if self.dry_run:
            self.log(f"DRY RUN: {description}", "INFO")
            return 0, "", ""

        try:
            result = subprocess.run(
                cmd,
                capture_output=capture,
                text=True,
                timeout=timeout
            )
            return result.returncode, result.stdout, result.stderr
        except subprocess.TimeoutExpired:
            return -1, "", "TIMEOUT"
        except Exception as e:
            return -1, "", str(e)

    def identify_failures(self, challenge_name=None, limit=None):
        """
        Identify failures by running compare_simple.py.

        Returns dict of {challenge_name: [failed_xml_files]}
        """
        self.log("Identifying failures using compare_simple.py...")

        if challenge_name:
            challenges = [challenge_name]
        else:
            # Get all challenges with polls
            polls_dir = self.root_dir / "polls"
            challenges = sorted([d.name for d in polls_dir.iterdir() if d.is_dir()])

        failures = {}

        for chal in challenges:
            self.log(f"Testing {chal}...")

            cmd = [
                sys.executable,
                "compare_simple.py",
                chal
            ]

            if limit:
                cmd.extend(["--limit", str(limit)])

            ret, stdout, stderr = self.run_command(cmd, f"Compare {chal}", timeout=600)

            # Parse output to find mismatches
            mismatches = []
            for line in stdout.split('\n'):
                if 'MISMATCH' in line and '.xml' in line:
                    # Extract XML filename
                    match = re.search(r'(GEN_\d+_\d+\.xml)', line)
                    if match:
                        mismatches.append(match.group(1))

            if mismatches:
                failures[chal] = mismatches
                self.log(f"  Found {len(mismatches)} failures in {chal}", "WARN")
            else:
                self.log(f"  {chal}: OK", "INFO")

        return failures

    def analyze_failure(self, challenge, xml_file):
        """
        Analyze a specific failure by running cb-replay on both 32-bit and 64-bit.

        Returns dict with failure analysis.
        """
        self.log(f"Analyzing {challenge} / {xml_file}...")

        bin_32 = self.root_dir / f"build/challenges/{challenge}/{challenge}"
        bin_64 = self.root_dir / f"build64/challenges/{challenge}/{challenge}"
        xml_path = None

        # Find XML file
        for subdir in ["poller/for-release", "poller/for-testing"]:
            candidate = self.root_dir / f"polls/{challenge}/{subdir}/{xml_file}"
            if candidate.exists():
                xml_path = candidate
                break

        if not xml_path:
            return {"error": f"XML file not found: {xml_file}"}

        analysis = {
            "challenge": challenge,
            "xml": xml_file,
            "32bit": {},
            "64bit": {},
            "failure_type": None,
            "hypothesis": []
        }

        # Test 32-bit
        if bin_32.exists():
            cmd_32 = [
                sys.executable,
                "tools/cb-replay.py",
                "--cbs", str(bin_32),
                "--xml", str(xml_path),
                "--timeout", "30"
            ]
            ret_32, out_32, err_32 = self.run_command(cmd_32, f"Test 32-bit {challenge}", timeout=60)
            analysis["32bit"] = {
                "returncode": ret_32,
                "output": out_32,
                "stderr": err_32,
                "timeout": "TIMEOUT" in err_32
            }

        # Test 64-bit
        if bin_64.exists():
            cmd_64 = [
                sys.executable,
                "tools/cb-replay.py",
                "--cbs", str(bin_64),
                "--xml", str(xml_path),
                "--timeout", "30"
            ]
            ret_64, out_64, err_64 = self.run_command(cmd_64, f"Test 64-bit {challenge}", timeout=60)
            analysis["64bit"] = {
                "returncode": ret_64,
                "output": out_64,
                "stderr": err_64,
                "timeout": "TIMEOUT" in err_64
            }

        # Determine failure type
        if analysis["64bit"].get("timeout"):
            analysis["failure_type"] = "TIMEOUT"
            analysis["hypothesis"].append("Infinite loop or I/O hang in 64-bit")
            analysis["hypothesis"].append("Possible struct size/alignment issue")
            analysis["hypothesis"].append("Possible cgc_size_t serialization issue")
        elif analysis["64bit"]["returncode"] != 0 and analysis["32bit"].get("returncode") == 0:
            analysis["failure_type"] = "CRASH"
            analysis["hypothesis"].append("Segfault or abort in 64-bit")
            analysis["hypothesis"].append("Possible pointer size assumption")
            analysis["hypothesis"].append("Possible struct padding difference")
        else:
            analysis["failure_type"] = "WRONG_OUTPUT"
            analysis["hypothesis"].append("Different output between 32-bit and 64-bit")
            analysis["hypothesis"].append("Likely serialization format difference")
            analysis["hypothesis"].append("Check for cgc_size_t in network protocol")

        return analysis

    def deep_debug(self, challenge, xml_file, failure_type):
        """
        Run deep debugging tools based on failure type.

        Returns debugging output and recommendations.
        """
        self.log(f"Deep debugging {challenge} / {xml_file} (type: {failure_type})...")

        bin_64 = self.root_dir / f"build64/challenges/{challenge}/{challenge}"
        xml_path = None

        # Find XML file
        for subdir in ["poller/for-release", "poller/for-testing"]:
            candidate = self.root_dir / f"polls/{challenge}/{subdir}/{xml_file}"
            if candidate.exists():
                xml_path = candidate
                break

        debug_info = {
            "failure_type": failure_type,
            "tools_used": [],
            "recommendations": []
        }

        if failure_type == "TIMEOUT":
            # Use GDB with hang debug script
            self.log("Using cb-replay-gdb with debug_hang.gdb...")

            if (self.root_dir / "debug_hang.gdb").exists():
                cmd = [
                    sys.executable,
                    "tools/cb-replay-gdb.py",
                    "--cbs", str(bin_64),
                    "--xml", str(xml_path),
                    "--debug",
                    "--gdb_script", "debug_hang.gdb",
                    "--timeout", "60"
                ]
                ret, out, err = self.run_command(cmd, "GDB hang debug", timeout=90)
                debug_info["tools_used"].append("cb-replay-gdb (hang)")
                debug_info["gdb_output"] = out

                # Look for GDB output file
                pid_match = re.search(r'\[DEBUG\] pid (\d+)', out)
                if pid_match:
                    gdb_file = f"/tmp/gdb_output_{pid_match.group(1)}.txt"
                    if Path(gdb_file).exists():
                        with open(gdb_file, 'r') as f:
                            debug_info["gdb_trace"] = f.read()

                        # Analyze for common patterns
                        if "cgc_receive" in debug_info["gdb_trace"]:
                            debug_info["recommendations"].append(
                                "Hanging in cgc_receive - likely waiting for more data than sent"
                            )
                            debug_info["recommendations"].append(
                                "Check struct sizes in network protocol"
                            )

            # Use strace for I/O comparison
            self.log("Using cb-replay-strace for I/O analysis...")
            if (self.root_dir / "tools" / "cb-replay-strace.py").exists():
                cmd = [
                    sys.executable,
                    "tools/cb-replay-strace.py",
                    "--cbs", str(bin_64),
                    "--xml", str(xml_path),
                    "--timeout", "30"
                ]
                ret, out, err = self.run_command(cmd, "Strace I/O analysis", timeout=60)
                debug_info["tools_used"].append("cb-replay-strace")
                debug_info["strace_output"] = out

        elif failure_type == "CRASH":
            # Use GDB with crash debug script
            self.log("Using cb-replay-gdb with debug_crash.gdb...")

            if (self.root_dir / "debug_crash.gdb").exists():
                cmd = [
                    sys.executable,
                    "tools/cb-replay-gdb.py",
                    "--cbs", str(bin_64),
                    "--xml", str(xml_path),
                    "--debug",
                    "--gdb_script", "debug_crash.gdb",
                    "--timeout", "30"
                ]
                ret, out, err = self.run_command(cmd, "GDB crash debug", timeout=60)
                debug_info["tools_used"].append("cb-replay-gdb (crash)")
                debug_info["gdb_output"] = out

                # Look for crash info
                pid_match = re.search(r'\[DEBUG\] pid (\d+)', out)
                if pid_match:
                    gdb_file = f"/tmp/gdb_output_{pid_match.group(1)}.txt"
                    if Path(gdb_file).exists():
                        with open(gdb_file, 'r') as f:
                            debug_info["gdb_trace"] = f.read()

                        if "SIGSEGV" in debug_info["gdb_trace"]:
                            debug_info["recommendations"].append(
                                "Segmentation fault detected"
                            )
                            debug_info["recommendations"].append(
                                "Check for pointer size assumptions or uninitialized memory"
                            )

        else:  # WRONG_OUTPUT
            # Use strace to compare I/O
            self.log("Using cb-replay-strace for I/O comparison...")

            if (self.root_dir / "tools" / "cb-replay-strace.py").exists():
                bin_32 = self.root_dir / f"build/challenges/{challenge}/{challenge}"

                # Run both 32 and 64 bit with strace
                for bits, bin_path in [("32", bin_32), ("64", bin_64)]:
                    if bin_path.exists():
                        cmd = [
                            sys.executable,
                            "tools/cb-replay-strace.py",
                            "--cbs", str(bin_path),
                            "--xml", str(xml_path),
                            "--timeout", "30"
                        ]
                        ret, out, err = self.run_command(cmd, f"Strace {bits}-bit", timeout=60)
                        debug_info[f"strace_{bits}bit"] = out

                debug_info["tools_used"].append("cb-replay-strace (comparison)")
                debug_info["recommendations"].append(
                    "Compare strace output to identify I/O differences"
                )
                debug_info["recommendations"].append(
                    "Look for different read/write sizes (cgc_size_t issue)"
                )

        return debug_info

    def search_similar_fixes(self, challenge, failure_type):
        """
        Search migration docs for similar fixes.

        Returns list of relevant documentation.
        """
        self.log(f"Searching for similar fixes in migration docs...")

        if not self.migration_docs.exists():
            return []

        relevant_docs = []

        # Read all markdown files
        for doc_file in self.migration_docs.glob("*.md"):
            with open(doc_file, 'r') as f:
                content = f.read()

            # Check for relevant keywords
            score = 0

            if failure_type == "TIMEOUT" and "timeout" in content.lower():
                score += 10
            if failure_type == "CRASH" and "crash" in content.lower():
                score += 10
            if failure_type == "WRONG_OUTPUT" and "output" in content.lower():
                score += 5

            if "cgc_size_t" in content:
                score += 15
            if "struct" in content and "alignment" in content:
                score += 10
            if "serialization" in content.lower():
                score += 10

            if score > 0:
                relevant_docs.append({
                    "file": doc_file.name,
                    "score": score,
                    "path": str(doc_file)
                })

        # Sort by score
        relevant_docs.sort(key=lambda x: x["score"], reverse=True)

        return relevant_docs[:5]  # Return top 5

    def generate_report(self, challenge, analysis, debug_info, similar_fixes):
        """
        Generate a comprehensive debugging report.
        """
        report = []
        report.append("=" * 80)
        report.append(f"DEBUGGING REPORT: {challenge}")
        report.append("=" * 80)
        report.append("")

        report.append(f"Challenge: {challenge}")
        report.append(f"Failed Test: {analysis['xml']}")
        report.append(f"Failure Type: {analysis['failure_type']}")
        report.append("")

        report.append("HYPOTHESES:")
        for i, hyp in enumerate(analysis['hypothesis'], 1):
            report.append(f"  {i}. {hyp}")
        report.append("")

        if debug_info:
            report.append("DEBUGGING TOOLS USED:")
            for tool in debug_info.get('tools_used', []):
                report.append(f"  - {tool}")
            report.append("")

            if debug_info.get('recommendations'):
                report.append("RECOMMENDATIONS:")
                for rec in debug_info['recommendations']:
                    report.append(f"  - {rec}")
                report.append("")

        if similar_fixes:
            report.append("SIMILAR FIXES IN MIGRATION DOCS:")
            for doc in similar_fixes:
                report.append(f"  - {doc['file']} (relevance: {doc['score']})")
                report.append(f"    Path: {doc['path']}")
            report.append("")

        report.append("NEXT STEPS:")
        report.append("  1. Review similar fixes in migration docs")
        report.append("  2. Examine the challenge source code:")
        report.append(f"     - challenges/{challenge}/src/")
        report.append(f"     - challenges/{challenge}/include/")
        report.append("  3. Look for:")
        report.append("     - cgc_size_t in network protocol structs")
        report.append("     - Pointer size assumptions")
        report.append("     - Struct serialization/deserialization")
        report.append("  4. Make fixes (only in headers, not source files)")
        report.append("  5. Rebuild: BUILD64=1 ./build.sh")
        report.append("  6. Test the specific XML:")
        report.append(f"     python tools/cb-replay.py --cbs build64/challenges/{challenge}/{challenge} --xml polls/{challenge}/poller/for-release/{analysis['xml']}")
        report.append("  7. Verify no 32-bit regression:")
        report.append(f"     python tools/cb-replay.py --cbs build/challenges/{challenge}/{challenge} --xml polls/{challenge}/poller/for-release/{analysis['xml']}")
        report.append("  8. Run full comparison:")
        report.append(f"     python compare_simple.py {challenge}")
        report.append("")

        report.append("=" * 80)

        return "\n".join(report)

    def debug_challenge(self, challenge, xml_file=None, save_report=True):
        """
        Main debugging workflow for a single challenge.
        """
        self.log(f"Starting debug session for {challenge}")

        # If no specific XML file, identify failures
        if not xml_file:
            failures = self.identify_failures(challenge_name=challenge, limit=5)
            if not failures.get(challenge):
                self.log(f"No failures found for {challenge}", "INFO")
                return None

            xml_file = failures[challenge][0]  # Debug first failure
            self.log(f"Found {len(failures[challenge])} failures, debugging: {xml_file}")

        # Analyze the failure
        analysis = self.analyze_failure(challenge, xml_file)
        if "error" in analysis:
            self.log(analysis["error"], "ERROR")
            return None

        self.log(f"Failure type: {analysis['failure_type']}")

        # Deep debugging
        debug_info = self.deep_debug(challenge, xml_file, analysis['failure_type'])

        # Search for similar fixes
        similar_fixes = self.search_similar_fixes(challenge, analysis['failure_type'])

        # Generate report
        report = self.generate_report(challenge, analysis, debug_info, similar_fixes)

        print("\n" + report)

        # Save report
        if save_report:
            report_file = self.root_dir / f"/tmp/{challenge}_debug_report.txt"
            with open(report_file, 'w') as f:
                f.write(report)
            self.log(f"Report saved to: {report_file}", "INFO")

        return {
            "analysis": analysis,
            "debug_info": debug_info,
            "similar_fixes": similar_fixes,
            "report": report
        }


def main():
    parser = argparse.ArgumentParser(
        description='Automated debugging agent for 64-bit porting',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Debug a specific challenge
  python debug_agent.py --challenge Audio_Visualizer

  # Debug a specific test
  python debug_agent.py --challenge Audio_Visualizer --xml GEN_00000_00000.xml

  # List all failures
  python debug_agent.py --list-failures

  # Batch debug mode (debug all failures, one by one)
  python debug_agent.py --batch
        """
    )

    parser.add_argument('--challenge', '-c', help='Challenge name to debug')
    parser.add_argument('--xml', help='Specific XML test to debug')
    parser.add_argument('--list-failures', '-l', action='store_true',
                        help='List all failures without debugging')
    parser.add_argument('--batch', '-b', action='store_true',
                        help='Debug all failures in batch mode')
    parser.add_argument('--verbose', '-v', action='store_true',
                        help='Verbose output')
    parser.add_argument('--dry-run', '-n', action='store_true',
                        help='Dry run mode (no actual commands)')

    args = parser.parse_args()

    agent = DebugAgent(verbose=args.verbose, dry_run=args.dry_run)

    if args.list_failures:
        failures = agent.identify_failures()
        print("\nFAILURES SUMMARY:")
        print("=" * 80)
        for chal, xmls in sorted(failures.items()):
            print(f"{chal}: {len(xmls)} failures")
            for xml in xmls[:3]:
                print(f"  - {xml}")
            if len(xmls) > 3:
                print(f"  ... and {len(xmls) - 3} more")
        print(f"\nTotal: {len(failures)} challenges with failures")
        return 0

    elif args.batch:
        failures = agent.identify_failures()
        print(f"\nFound {len(failures)} challenges with failures")
        print("Starting batch debug mode...\n")

        for i, (chal, xmls) in enumerate(sorted(failures.items()), 1):
            print(f"\n[{i}/{len(failures)}] Debugging {chal}...")
            agent.debug_challenge(chal, xmls[0])

            input("\nPress Enter to continue to next challenge (or Ctrl+C to stop)...")

        return 0

    elif args.challenge:
        result = agent.debug_challenge(args.challenge, args.xml)
        return 0 if result else 1

    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
