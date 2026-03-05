#!/usr/bin/env python3
"""
Check for missing binaries in 32-bit and 64-bit builds.
Compares build/challenges and build64/challenges to identify any discrepancies.
"""

import os
import sys
from pathlib import Path

def get_challenges(build_dir):
    """Get list of challenges in a build directory."""
    challenges_dir = Path(build_dir) / "challenges"
    if not challenges_dir.exists():
        return set()
    return set(d.name for d in challenges_dir.iterdir() if d.is_dir())

def get_binaries(challenge_dir):
    """Get list of binaries (executables) in a challenge directory."""
    if not challenge_dir.exists():
        return []

    binaries = []
    for item in challenge_dir.iterdir():
        if item.is_file() and os.access(item, os.X_OK) and not item.name.endswith('.pov'):
            binaries.append(item.name)
    return sorted(binaries)

def main():
    build32_dir = Path("build")
    build64_dir = Path("build64")

    # Get challenges in each build
    chals_32 = get_challenges(build32_dir)
    chals_64 = get_challenges(build64_dir)

    print(f"=== Build Status ===")
    print(f"32-bit challenges: {len(chals_32)}")
    print(f"64-bit challenges: {len(chals_64)}")
    print(f"Common challenges: {len(chals_32 & chals_64)}")
    print()

    # Check for challenges only in one build
    only_32 = chals_32 - chals_64
    only_64 = chals_64 - chals_32

    if only_32:
        print(f"⚠️  Challenges only in 32-bit build ({len(only_32)}):")
        for chal in sorted(only_32):
            print(f"  - {chal}")
        print()

    if only_64:
        print(f"⚠️  Challenges only in 64-bit build ({len(only_64)}):")
        for chal in sorted(only_64):
            print(f"  - {chal}")
        print()

    # Check binaries in common challenges
    common_chals = sorted(chals_32 & chals_64)
    missing_binaries = []
    binary_mismatches = []

    for chal in common_chals:
        dir_32 = build32_dir / "challenges" / chal
        dir_64 = build64_dir / "challenges" / chal

        bins_32 = get_binaries(dir_32)
        bins_64 = get_binaries(dir_64)

        if not bins_32:
            missing_binaries.append((chal, "32-bit", "No executables found"))
        elif not bins_64:
            missing_binaries.append((chal, "64-bit", "No executables found"))
        elif set(bins_32) != set(bins_64):
            binary_mismatches.append((chal, bins_32, bins_64))

    if missing_binaries:
        print(f"⚠️  Challenges with missing binaries ({len(missing_binaries)}):")
        for chal, build_type, reason in missing_binaries:
            print(f"  - {chal} ({build_type}): {reason}")
        print()

    if binary_mismatches:
        print(f"⚠️  Challenges with binary mismatches ({len(binary_mismatches)}):")
        for chal, bins_32, bins_64 in binary_mismatches:
            print(f"  - {chal}:")
            print(f"      32-bit: {', '.join(bins_32)}")
            print(f"      64-bit: {', '.join(bins_64)}")
        print()

    if not only_32 and not only_64 and not missing_binaries and not binary_mismatches:
        print("✅ All challenges have matching binaries in both 32-bit and 64-bit builds!")

    return 0

if __name__ == "__main__":
    sys.exit(main())
