#!/usr/bin/env python3
"""
Code analyzer for identifying common 64-bit porting issues.

This script scans challenge source code for patterns that commonly cause
64-bit porting problems.
"""

import argparse
import os
import re
import sys
from pathlib import Path
from collections import defaultdict


class CodeAnalyzer:
    def __init__(self, challenge_name):
        self.challenge = challenge_name
        self.root_dir = Path.cwd()
        self.challenge_dir = self.root_dir / "challenges" / challenge_name
        self.issues = []

    def scan_file(self, file_path):
        """Scan a single file for 64-bit issues."""
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                lines = content.split('\n')
        except Exception as e:
            return []

        file_issues = []

        for i, line in enumerate(lines, 1):
            # Check for cgc_size_t in structs (potential serialization issue)
            if re.search(r'cgc_size_t\s+\w+;', line) and 'struct' in '\n'.join(lines[max(0, i-10):i]):
                file_issues.append({
                    'line': i,
                    'type': 'cgc_size_t_in_struct',
                    'severity': 'HIGH',
                    'code': line.strip(),
                    'message': 'cgc_size_t in struct - 4 bytes on 32-bit, 8 bytes on 64-bit',
                    'suggestion': 'Use uint32_t for network protocol structs'
                })

            # Check for sizeof(cgc_size_t) or sizeof(size_t)
            if 'sizeof(cgc_size_t)' in line or 'sizeof(size_t)' in line:
                file_issues.append({
                    'line': i,
                    'type': 'sizeof_size_t',
                    'severity': 'MEDIUM',
                    'code': line.strip(),
                    'message': 'sizeof(cgc_size_t) will differ between 32-bit and 64-bit',
                    'suggestion': 'Use fixed-size types (sizeof(uint32_t)) for serialization'
                })

            # Check for pointer arithmetic assumptions
            if re.search(r'sizeof\(.*\*\)', line):
                file_issues.append({
                    'line': i,
                    'type': 'sizeof_pointer',
                    'severity': 'MEDIUM',
                    'code': line.strip(),
                    'message': 'sizeof(pointer) is 4 on 32-bit, 8 on 64-bit',
                    'suggestion': 'Ensure this is not used in serialization'
                })

            # Check for long type usage (problematic on LP64)
            if re.search(r'\blong\s+\w+', line) and 'long long' not in line:
                file_issues.append({
                    'line': i,
                    'type': 'long_type',
                    'severity': 'LOW',
                    'code': line.strip(),
                    'message': 'long is 4 bytes on 32-bit, 8 bytes on 64-bit (LP64)',
                    'suggestion': 'Use int32_t or int64_t explicitly'
                })

            # Check for type casting between pointers and integers
            if re.search(r'\(int\)\s*\w+\s*\*', line) or re.search(r'\(\w+\s*\*\)\s*\d+', line):
                file_issues.append({
                    'line': i,
                    'type': 'pointer_int_cast',
                    'severity': 'HIGH',
                    'code': line.strip(),
                    'message': 'Casting between pointer and int may lose data on 64-bit',
                    'suggestion': 'Use intptr_t or uintptr_t for pointer arithmetic'
                })

            # Check for struct packing pragmas
            if '#pragma pack' in line:
                file_issues.append({
                    'line': i,
                    'type': 'pragma_pack',
                    'severity': 'MEDIUM',
                    'code': line.strip(),
                    'message': 'Pragma pack may behave differently on 64-bit',
                    'suggestion': 'Verify struct layout with sizeof() checks'
                })

            # Check for potential alignment issues
            if 'memcpy' in line and 'sizeof' in line:
                file_issues.append({
                    'line': i,
                    'type': 'memcpy_sizeof',
                    'severity': 'LOW',
                    'code': line.strip(),
                    'message': 'memcpy with sizeof - verify correct size on both 32/64-bit',
                    'suggestion': 'Use fixed-size types for serialization'
                })

            # Check for transmit/receive with size_t
            if re.search(r'(cgc_transmit|cgc_receive).*cgc_size_t', line):
                file_issues.append({
                    'line': i,
                    'type': 'io_with_size_t',
                    'severity': 'HIGH',
                    'code': line.strip(),
                    'message': 'I/O operation with cgc_size_t - size differs on 32/64-bit',
                    'suggestion': 'Check if transmitting/receiving size value directly'
                })

        return file_issues

    def analyze(self):
        """Analyze all source files in the challenge."""
        if not self.challenge_dir.exists():
            print(f"Error: Challenge directory not found: {self.challenge_dir}")
            return None

        # Scan all .c, .cc, .cpp, .h files
        patterns = ['**/*.c', '**/*.cc', '**/*.cpp', '**/*.h']

        files_scanned = 0
        for pattern in patterns:
            for file_path in self.challenge_dir.glob(pattern):
                # Skip build directories
                if 'build' in str(file_path):
                    continue

                file_issues = self.scan_file(file_path)
                if file_issues:
                    self.issues.extend([
                        {**issue, 'file': str(file_path.relative_to(self.root_dir))}
                        for issue in file_issues
                    ])
                files_scanned += 1

        return {
            'challenge': self.challenge,
            'files_scanned': files_scanned,
            'issues': self.issues
        }

    def generate_report(self):
        """Generate a formatted report of issues."""
        if not self.issues:
            return f"No issues found in {self.challenge}"

        # Group by severity
        by_severity = defaultdict(list)
        for issue in self.issues:
            by_severity[issue['severity']].append(issue)

        # Group by file
        by_file = defaultdict(list)
        for issue in self.issues:
            by_file[issue['file']].append(issue)

        report = []
        report.append("=" * 80)
        report.append(f"CODE ANALYSIS REPORT: {self.challenge}")
        report.append("=" * 80)
        report.append("")

        report.append("SUMMARY:")
        report.append(f"  Total Issues: {len(self.issues)}")
        report.append(f"  HIGH:   {len(by_severity['HIGH'])}")
        report.append(f"  MEDIUM: {len(by_severity['MEDIUM'])}")
        report.append(f"  LOW:    {len(by_severity['LOW'])}")
        report.append("")

        report.append("ISSUES BY FILE:")
        report.append("")

        for file_path in sorted(by_file.keys()):
            issues = by_file[file_path]
            report.append(f"{file_path} ({len(issues)} issues)")
            report.append("-" * 80)

            for issue in sorted(issues, key=lambda x: x['line']):
                report.append(f"  Line {issue['line']}: [{issue['severity']}] {issue['type']}")
                report.append(f"    Code: {issue['code']}")
                report.append(f"    Issue: {issue['message']}")
                report.append(f"    Fix: {issue['suggestion']}")
                report.append("")

        report.append("=" * 80)
        report.append("PRIORITIZED FIXES:")
        report.append("")

        # Show high severity issues first
        for severity in ['HIGH', 'MEDIUM', 'LOW']:
            if by_severity[severity]:
                report.append(f"{severity} PRIORITY:")
                for issue in by_severity[severity][:5]:  # Top 5 per severity
                    report.append(f"  {issue['file']}:{issue['line']}")
                    report.append(f"    {issue['message']}")
                    report.append(f"    Fix: {issue['suggestion']}")
                    report.append("")

        return "\n".join(report)


def main():
    parser = argparse.ArgumentParser(
        description='Analyze challenge code for 64-bit porting issues',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument('challenge', help='Challenge name to analyze')
    parser.add_argument('--json', action='store_true',
                        help='Output in JSON format')
    parser.add_argument('--save', '-s', help='Save report to file')

    args = parser.parse_args()

    analyzer = CodeAnalyzer(args.challenge)
    result = analyzer.analyze()

    if result is None:
        return 1

    if args.json:
        import json
        print(json.dumps(result, indent=2))
    else:
        report = analyzer.generate_report()
        print(report)

        if args.save:
            with open(args.save, 'w') as f:
                f.write(report)
            print(f"\nReport saved to: {args.save}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
