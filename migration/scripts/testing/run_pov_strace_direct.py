#!/usr/bin/env python3
"""Feed POV test input directly to anagram_game under strace"""

import subprocess
import time
import os
import defusedxml.ElementTree as ET

def parse_pov_xml(xml_file):
    """Parse POV XML and extract write commands"""
    with open(xml_file, 'rb') as f:
        tree = ET.fromstring(f.read())

    # Find all write elements in the replay
    replay = tree.find('replay')
    writes = []
    for elem in replay:
        if elem.tag == 'write':
            # Extract data from write element
            data_parts = []
            for data_elem in elem:
                if data_elem.tag == 'data':
                    format_type = data_elem.attrib.get('format', 'asciic')
                    text = data_elem.text
                    if format_type == 'hex':
                        # Remove whitespace and convert hex to bytes
                        hex_str = text.replace(' ', '').replace('\n', '').replace('\r', '').replace('\t', '')
                        data_parts.append(bytes.fromhex(hex_str))
                    elif format_type == 'asciic':
                        # Convert asciic format (with \x escapes) to bytes
                        data_parts.append(compile_asciic(text))
            writes.append(b''.join(data_parts))

    return writes

def compile_asciic(text):
    """Convert asciic string to bytes"""
    result = []
    i = 0
    while i < len(text):
        if text[i] == '\\' and i + 1 < len(text):
            next_char = text[i + 1]
            if next_char == 'n':
                result.append(ord('\n'))
                i += 2
            elif next_char == 'r':
                result.append(ord('\r'))
                i += 2
            elif next_char == 't':
                result.append(ord('\t'))
                i += 2
            elif next_char == '\\':
                result.append(ord('\\'))
                i += 2
            elif next_char == 'x' and i + 3 < len(text):
                hex_val = text[i+2:i+4]
                result.append(int(hex_val, 16))
                i += 4
            else:
                result.append(ord(text[i]))
                i += 1
        else:
            result.append(ord(text[i]))
            i += 1
    return bytes(result)

def main():
    xml_file = 'polls/anagram_game/poller/for-testing/GEN_00000_00001.xml'
    binary = 'build64/challenges/anagram_game/anagram_game'
    strace_log = '/tmp/pov_direct_strace.log'

    # Remove old log
    if os.path.exists(strace_log):
        os.remove(strace_log)

    print(f"Parsing POV XML: {xml_file}")
    writes = parse_pov_xml(xml_file)
    print(f"Found {len(writes)} write commands")
    print()

    # Prepare seed environment
    seed = '6f9a99085fc2e2d57b4a5476a27683918d9a517623b7428f11655409bfe78ec39dd7f8441a206661b57ab11520310773'
    env = os.environ.copy()
    env['seed'] = seed

    # Run binary under strace
    print(f"Launching {binary} under strace...")
    strace_cmd = [
        'strace',
        '-e', 'trace=mmap,read,write,exit_group',
        '-o', strace_log,
        '-f',
        binary
    ]

    proc = subprocess.Popen(
        strace_cmd,
        env=env,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT
    )

    print(f"Process PID: {proc.pid}")
    print(f"Sending {len(writes)} commands...")
    print()

    # Send all writes
    for i, data in enumerate(writes):
        try:
            proc.stdin.write(data)
            proc.stdin.flush()
            if i % 100 == 0:
                print(f"Sent {i} commands...")
            # Small delay to let it process
            if i == len(writes) - 1:  # Last command
                time.sleep(2)
        except:
            print(f"Failed to send command {i}")
            break

    print(f"All commands sent, waiting for process...")

    # Wait for process to exit or timeout
    try:
        proc.wait(timeout=10)
        print(f"Process exited with code: {proc.returncode}")
    except subprocess.TimeoutExpired:
        print("Process timed out, terminating...")
        proc.terminate()
        proc.wait()

    # Check strace log
    time.sleep(1)
    if os.path.exists(strace_log):
        size = os.path.getsize(strace_log)
        print(f"\n[SUCCESS] Strace log created: {strace_log} ({size} bytes)")

        # Search for large allocations
        print("\n=== Searching for large mmap calls (> 1GB) ===")
        with open(strace_log, 'r') as f:
            for line in f:
                if 'mmap' in line:
                    # Try to extract size
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

        # Show exit calls
        print("\n=== Exit calls ===")
        with open(strace_log, 'r') as f:
            for line in f:
                if 'exit_group' in line or 'exit(' in line:
                    print(line.rstrip())

        # Show last 30 lines
        print("\n=== Last 30 lines ===")
        with open(strace_log, 'r') as f:
            lines = f.readlines()
            for line in lines[-30:]:
                print(line.rstrip())
    else:
        print(f"\n[FAIL] Strace log not found")

if __name__ == '__main__':
    main()
