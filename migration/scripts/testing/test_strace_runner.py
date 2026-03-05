#!/usr/bin/env python3
"""Simple test script for challenge_runner_strace.py"""

import sys
import os
import time

# Add tools directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'tools'))

import challenge_runner_strace as challenge_runner

def simple_log(msg):
    """Simple logging function"""
    print(f"[LOG] {msg}")

def main():
    # Test parameters - each challenge should be a list
    challenges = [[os.path.abspath('build64/challenges/anagram_game/anagram_game')]]
    timeout = 30
    seed = '0' * 96  # 48 bytes in hex = 96 hex characters

    print(f"Testing challenge_runner_strace.py")
    print(f"Challenge: {challenges[0]}")
    print(f"Timeout: {timeout}s")
    print(f"Seed: {seed[:20]}...")
    print()

    # Launch the challenge
    procs, watcher = challenge_runner.run(challenges, timeout, seed, simple_log)

    print(f"Process launched, PID: {procs[0].pid}")
    print(f"Waiting 2 seconds...")
    time.sleep(2)

    # Send simple input to trigger some behavior
    try:
        # Send word count (small number, e.g., 2 words)
        procs[0].stdin.write(b'\x02\x00')
        procs[0].stdin.flush()
        print("Sent word count: 2")

        # Send 2 words
        procs[0].stdin.write(b'\x04test')
        procs[0].stdin.flush()
        print("Sent word 1: 'test'")

        procs[0].stdin.write(b'\x04word')
        procs[0].stdin.flush()
        print("Sent word 2: 'word'")

        time.sleep(1)

        # Try to send quit command (CMD_QUIT = 0)
        procs[0].stdin.write(b'\x00')
        procs[0].stdin.flush()
        print("Sent quit command")

    except Exception as e:
        print(f"Error sending data: {e}")

    # Wait for the watcher to complete
    print("Waiting for process to exit...")
    watcher.join(timeout=10)

    # Check if strace log was created
    strace_log = '/tmp/anagram_strace.log'
    if os.path.exists(strace_log):
        size = os.path.getsize(strace_log)
        print(f"\n[SUCCESS] Strace log created: {strace_log} ({size} bytes)")

        # Show first 50 lines
        print("\n=== First 50 lines of strace log ===")
        with open(strace_log, 'r') as f:
            for i, line in enumerate(f):
                if i >= 50:
                    print("... (truncated)")
                    break
                print(line.rstrip())
    else:
        print(f"\n[FAIL] Strace log not found at {strace_log}")

    return 0

if __name__ == '__main__':
    sys.exit(main())
