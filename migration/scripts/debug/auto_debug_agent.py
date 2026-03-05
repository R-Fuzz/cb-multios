#!/usr/bin/env python3
"""
Autonomous debugging agent orchestrator for 64-bit porting.

This script launches independent Claude Code agents to autonomously debug and fix
64-bit porting issues, avoiding context pollution by using separate agent sessions.
"""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path


def get_failures(challenge_name=None, limit=None):
    """Run compare_simple.py to identify failures."""
    print("[ORCHESTRATOR] Identifying failures...")

    if challenge_name:
        challenges = [challenge_name]
    else:
        # Get all challenges
        polls_dir = Path("polls")
        if not polls_dir.exists():
            print("[ERROR] polls/ directory not found")
            return {}
        challenges = sorted([d.name for d in polls_dir.iterdir() if d.is_dir()])

    failures = {}

    for chal in challenges:
        cmd = [sys.executable, "compare_simple.py", chal]
        if limit:
            cmd.extend(["--limit", str(limit)])

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)

            # Parse for mismatches
            mismatches = []
            for line in result.stdout.split('\n'):
                if 'MISMATCH' in line and 'Testing' in line:
                    # Extract XML filename
                    parts = line.split('Testing')[1].strip()
                    xml_name = parts.split('...')[0].strip()
                    if xml_name.endswith('.xml'):
                        mismatches.append(xml_name)

            if mismatches:
                failures[chal] = mismatches
                print(f"[ORCHESTRATOR] {chal}: {len(mismatches)} failures found")

        except Exception as e:
            print(f"[ORCHESTRATOR] Error testing {chal}: {e}")

    return failures


def create_agent_prompt(challenge, xml_file, failure_context=None):
    """Create a detailed prompt for the autonomous debugging agent."""

    prompt = f"""You are an autonomous debugging agent tasked with fixing a 64-bit porting issue in a CGC challenge binary.

# Challenge Information
- Challenge Name: {challenge}
- Failed Test: {xml_file}
- Task: Make the 64-bit version behave identically to the 32-bit version

# Your Mission
Fix the 64-bit porting issue for this specific test. Work autonomously through the debugging workflow until the test passes.

# Available Tools and Workflow

## Step 1: Analyze the Failure
Run cb-replay.py on both 32-bit and 64-bit to observe the failure:

```bash
# Test 32-bit (baseline)
python tools/cb-replay.py \\
  --cbs build/challenges/{challenge}/{challenge} \\
  --xml polls/{challenge}/poller/for-release/{xml_file} \\
  --timeout 30

# Test 64-bit (failing)
python tools/cb-replay.py \\
  --cbs build64/challenges/{challenge}/{challenge} \\
  --xml polls/{challenge}/poller/for-release/{xml_file} \\
  --timeout 30
```

Determine the failure type:
- **TIMEOUT**: 64-bit hangs (likely struct size mismatch in I/O)
- **CRASH**: Segfault (likely pointer size or alignment issue)
- **WRONG_OUTPUT**: Different output (likely serialization format difference)

## Step 2: Deep Debugging

### For TIMEOUT (hangs):
Use cb-replay-gdb.py with debug_hang.gdb to see where it's stuck:

```bash
python tools/cb-replay-gdb.py \\
  --cbs build64/challenges/{challenge}/{challenge} \\
  --xml polls/{challenge}/poller/for-release/{xml_file} \\
  --debug --gdb_script debug_hang.gdb \\
  --timeout 60
```

Check GDB output in /tmp/gdb_output_*.txt for where it's hanging (usually cgc_receive).

Also use cb-replay-strace.py to compare I/O:
```bash
python tools/cb-replay-strace.py \\
  --cbs build64/challenges/{challenge}/{challenge} \\
  --xml polls/{challenge}/poller/for-release/{xml_file} \\
  --timeout 30
```

### For CRASH:
Use cb-replay-gdb.py with debug_crash.gdb:

```bash
python tools/cb-replay-gdb.py \\
  --cbs build64/challenges/{challenge}/{challenge} \\
  --xml polls/{challenge}/poller/for-release/{xml_file} \\
  --debug --gdb_script debug_crash.gdb
```

### For WRONG_OUTPUT:
Use cb-replay-strace.py to compare I/O between 32-bit and 64-bit:

```bash
# 32-bit I/O trace
python tools/cb-replay-strace.py \\
  --cbs build/challenges/{challenge}/{challenge} \\
  --xml polls/{challenge}/poller/for-release/{xml_file}

# 64-bit I/O trace
python tools/cb-replay-strace.py \\
  --cbs build64/challenges/{challenge}/{challenge} \\
  --xml polls/{challenge}/poller/for-release/{xml_file}
```

Look for different read/write sizes.

## Step 3: Examine Source Code

Read the challenge source to identify the issue:
- challenges/{challenge}/src/
- challenges/{challenge}/include/
- challenges/{challenge}/lib/

Look for:
1. **cgc_size_t in structs** (4 bytes on 32-bit, 8 bytes on 64-bit)
2. **Pointer size assumptions**
3. **Struct serialization/deserialization**
4. **Network protocol definitions**

## Step 4: Review Similar Fixes

Check migration/docs/ for similar fixes:
- azurad_64bit_porting.md
- basic_emulator_64bit_solution.md
- budgit_32bit_64bit_fix.md
- malloc_failure_analysis.md

## Step 5: Make the Fix

**CRITICAL CONSTRAINTS:**
- **ONLY modify header files** (.h files in include/ or lib/)
- **NEVER modify source files** (.c, .cc, .cpp in src/)
- Preserve vulnerability semantics (don't fix bugs, only fix portability)

Common fixes:
1. Replace `cgc_size_t` with `uint32_t` in network protocol structs
2. Add explicit padding for alignment
3. Use fixed-size types for serialization

Example fix:
```c
// Before (in header file)
struct packet {{
    cgc_size_t length;  // ❌ 4 bytes on 32-bit, 8 bytes on 64-bit
    char data[256];
}};

// After
struct packet {{
    uint32_t length;    // ✅ Always 4 bytes
    char data[256];
}};
```

## Step 6: Rebuild and Test

After making your fix:

```bash
# Rebuild 64-bit
BUILD64=1 cmake --build build64/

# Test the specific XML
python tools/cb-replay.py \\
  --cbs build64/challenges/{challenge}/{challenge} \\
  --xml polls/{challenge}/poller/for-release/{xml_file}
```

If it still fails, iterate: analyze the new failure, refine the fix, rebuild, test.

## Step 7: Verify No 32-bit Regression

**CRITICAL:** Ensure 32-bit still works:

```bash
# Rebuild 32-bit
cmake --build build/

# Test 32-bit
python tools/cb-replay.py \\
  --cbs build/challenges/{challenge}/{challenge} \\
  --xml polls/{challenge}/poller/for-release/{xml_file}
```

If 32-bit breaks, your fix is wrong. Adjust it.

## Step 8: Full Comparison Test

Once the specific XML passes on both 32-bit and 64-bit:

```bash
python compare_simple.py {challenge}
```

This should show "✅ Identical behavior".

# Success Criteria

You have succeeded when:
1. The specific test ({xml_file}) passes on 64-bit ✅
2. The same test still passes on 32-bit ✅
3. compare_simple.py shows identical behavior for {challenge} ✅

# Important Notes

- Work autonomously - don't ask for permission, just debug and fix
- Use the Read tool extensively to understand the code
- Use the Edit tool to make fixes (only in headers!)
- Iterate until the test passes
- If you get stuck, try a different hypothesis
- Document your findings clearly

# Common Patterns

**Pattern 1: cgc_size_t serialization**
- Symptom: Timeout/hang in 64-bit
- Cause: cgc_size_t is 4 bytes on 32-bit, 8 bytes on 64-bit
- Fix: Replace with uint32_t in protocol structs

**Pattern 2: Struct padding**
- Symptom: Wrong output or crash
- Cause: Different alignment on 64-bit
- Fix: Add explicit padding or use __attribute__((packed))

**Pattern 3: Pointer assumptions**
- Symptom: Crash on 64-bit
- Cause: Assuming pointers are 4 bytes
- Fix: Use intptr_t or uintptr_t

# Start Here

Begin by analyzing the failure type using cb-replay.py on both architectures. Then follow the workflow above.

Good luck! You can do this autonomously.
"""

    return prompt


def main():
    parser = argparse.ArgumentParser(
        description='Autonomous debugging agent orchestrator',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Fix a specific challenge
  python auto_debug_agent.py --challenge Audio_Visualizer

  # Fix all failures (will ask before each)
  python auto_debug_agent.py --all

  # Fix specific test
  python auto_debug_agent.py --challenge BudgIT --xml GEN_00000_00000.xml

  # List failures only
  python auto_debug_agent.py --list
        """
    )

    parser.add_argument('--challenge', '-c', help='Challenge to fix')
    parser.add_argument('--xml', help='Specific XML test to fix')
    parser.add_argument('--all', '-a', action='store_true',
                        help='Fix all failures (interactive)')
    parser.add_argument('--list', '-l', action='store_true',
                        help='List failures only')
    parser.add_argument('--limit', type=int, help='Limit tests per challenge for detection')
    parser.add_argument('--batch', '-b', action='store_true',
                        help='Batch mode (no prompts between challenges)')

    args = parser.parse_args()

    # Identify failures
    failures = get_failures(args.challenge, args.limit)

    if not failures:
        print("[ORCHESTRATOR] No failures found!")
        return 0

    if args.list:
        print("\n" + "=" * 80)
        print("FAILURES DETECTED")
        print("=" * 80)
        for chal, xmls in sorted(failures.items()):
            print(f"\n{chal}: {len(xmls)} failures")
            for xml in xmls[:5]:
                print(f"  - {xml}")
            if len(xmls) > 5:
                print(f"  ... and {len(xmls) - 5} more")
        print(f"\nTotal: {len(failures)} challenges with failures")
        return 0

    # If specific XML provided, just fix that one
    if args.xml:
        if not args.challenge:
            print("[ERROR] --xml requires --challenge")
            return 1

        print(f"\n[ORCHESTRATOR] Launching agent for {args.challenge} / {args.xml}")
        prompt = create_agent_prompt(args.challenge, args.xml)

        # Save prompt for inspection
        with open(f"/tmp/agent_prompt_{args.challenge}_{args.xml}.txt", 'w') as f:
            f.write(prompt)

        print(f"[ORCHESTRATOR] Agent prompt saved to /tmp/agent_prompt_{args.challenge}_{args.xml}.txt")
        print("[ORCHESTRATOR] Now you should use the Task tool to launch the agent with this prompt.")
        print("\nTo launch the agent, use:")
        print(f'  Task(subagent_type="general-purpose", description="Fix {args.challenge}", prompt="""<prompt_content>""")')

        return 0

    # Interactive mode for all failures
    if args.all or args.challenge:
        if args.challenge:
            # Filter to just this challenge
            failures = {k: v for k, v in failures.items() if k == args.challenge}

        print(f"\n[ORCHESTRATOR] Found {len(failures)} challenges to fix")

        for i, (chal, xmls) in enumerate(sorted(failures.items()), 1):
            print(f"\n{'=' * 80}")
            print(f"[{i}/{len(failures)}] Challenge: {chal}")
            print(f"Failures: {len(xmls)}")
            print('=' * 80)

            # Fix first failure for this challenge
            xml = xmls[0]

            if not args.batch:
                response = input(f"\nLaunch agent to fix {chal} / {xml}? [y/N/q]: ")
                if response.lower() == 'q':
                    print("[ORCHESTRATOR] Quitting...")
                    break
                if response.lower() != 'y':
                    print(f"[ORCHESTRATOR] Skipping {chal}")
                    continue

            print(f"\n[ORCHESTRATOR] Preparing agent for {chal} / {xml}")
            prompt = create_agent_prompt(chal, xml)

            # Save prompt
            prompt_file = f"/tmp/agent_prompt_{chal}.txt"
            with open(prompt_file, 'w') as f:
                f.write(prompt)

            print(f"[ORCHESTRATOR] Agent prompt saved to {prompt_file}")
            print("\n" + "=" * 80)
            print("NEXT STEP: Launch the agent manually using Task tool")
            print("=" * 80)
            print(f"\nChallenge: {chal}")
            print(f"Test: {xml}")
            print(f"Prompt file: {prompt_file}")
            print("\nRead the prompt file and use the Task tool to launch a general-purpose agent.")
            print("The agent will work autonomously to fix the issue.")

            if not args.batch:
                input("\nPress Enter when agent is done (or Ctrl+C to stop)...")

    return 0


if __name__ == "__main__":
    sys.exit(main())
