#!/usr/bin/env python3
"""Run the POV test with strace enabled"""

import subprocess
import os
import sys
import time

def main():
    # Clear old strace log
    strace_log = '/tmp/anagram_strace.log'
    if os.path.exists(strace_log):
        os.remove(strace_log)
        print(f"Removed old strace log")

    # Run the POV test with strace-enabled cb-replay
    print("Running POV test with strace enabled...")
    print("Command: python tools/cb-replay-strace.py --cbs build64/challenges/anagram_game/anagram_game --timeout 60 --xml polls/anagram_game/poller/for-testing/GEN_00000_00001.xml")
    print()

    # Activate venv and run
    cmd = [
        'bash', '-c',
        'source venv/bin/activate && python tools/cb-replay-strace.py --cbs build64/challenges/anagram_game/anagram_game --timeout 60 --xml polls/anagram_game/poller/for-testing/GEN_00000_00001.xml'
    ]

    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)

    # Print output as it comes
    for line in proc.stdout:
        print(line.rstrip())

    proc.wait()
    print(f"\nProcess exited with code: {proc.returncode}")

    # Wait a moment for strace to flush
    time.sleep(1)

    # Check if strace log was created
    if os.path.exists(strace_log):
        size = os.path.getsize(strace_log)
        print(f"\n[SUCCESS] Strace log created: {strace_log} ({size} bytes)")

        # Look for the 1.7GB allocation
        print("\n=== Searching for large mmap calls (> 1GB) ===")
        with open(strace_log, 'r') as f:
            for line in f:
                if 'mmap' in line:
                    # Extract size parameter
                    parts = line.split('(')
                    if len(parts) > 1:
                        params = parts[1].split(',')
                        if len(params) > 1:
                            try:
                                size_str = params[1].strip()
                                size_val = int(size_str)
                                if size_val > 1000000000:  # > 1GB
                                    print(line.rstrip())
                            except:
                                pass

        # Also show exit_group calls
        print("\n=== Exit calls ===")
        with open(strace_log, 'r') as f:
            for line in f:
                if 'exit_group' in line or 'exit(' in line:
                    print(line.rstrip())

        # Show last 20 lines of strace log
        print("\n=== Last 20 lines of strace log ===")
        with open(strace_log, 'r') as f:
            lines = f.readlines()
            for line in lines[-20:]:
                print(line.rstrip())
    else:
        print(f"\n[FAIL] Strace log not found at {strace_log}")

if __name__ == '__main__':
    sys.exit(main())
