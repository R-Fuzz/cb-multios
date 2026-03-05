# DARPA Challenge Binaries on Linux, OS X, and Windows

[![Build Status](https://img.shields.io/github/workflow/status/trailofbits/cb-multios/CI/master)](https://github.com/trailofbits/cb-multios/actions?query=workflow%3ACI)
[![Slack Status](https://empireslacking.herokuapp.com/badge.svg)](https://empireslacking.herokuapp.com)

The DARPA Challenge Binaries (CBs) are custom-made programs specifically designed to contain vulnerabilities that represent a wide variety of crashing software flaws. They are more than simple test cases, they approximate real software with enough complexity to stress both manual and automated vulnerability discovery. The CBs come with extensive functionality tests, triggers for introduced bugs, patches, and performance monitoring tools, enabling benchmarking of patching tools and bug mitigation strategies.

The CBs were originally developed for DECREE -- a custom Linux-derived operating system that has no signals, no shared memory, no threads, no standard libc runtime, and only seven system calls -- making them incompatible with most existing analysis tools. In this repository, we have modified the CBs to work on Linux and OS X by replacing the build system and re-implementing CGC system calls via standard libc functionality and native operating system semantics. Scripts have been provided that help modify the CBs to support other operating systems.

The CBs are the best available benchmark to evaluate program analysis tools. Using them, it is possible to make comparisons such as:

* How good are tools from the Cyber Grand Challenge vs. existing program analysis and bug finding tools?
* When a new tool is released, how does it stack up against the current best?
* Do static analysis tools that work with source code find more bugs than dynamic analysis tools that work with binaries?
* Are tools written for Mac OS X better than tools written for Linux, and are they better than tools written for Windows?

## Components

### challenges
This directory contains all of the source code for the challenge binaries. Challenges that are not building or are not yet supported are in the `disabled-challenges` directory.

### include
This directory contains `libcgc`, which implements the syscalls to work on non-DECREE systems. `libcgc` currently works on OS X and Linux.

### tools
This folder contains Python scripts that help with modifying, building, and testing the original challenges.

#### tester.py
This is a helper script to test all challenges using `cb-test`. Results are summarized and can be output to an excel spreadsheet. More details in the [testing section](#testing) below.

## Building

The following steps will build both the patched and unpatched binaries in `build/challenges/[challenge]/`.

### MacOS

The challenges build as i386 binaries, but Mac OS 10.14+ only supports building x86-64 binaries by default. To enable i386 support, run the following command:

```
sudo installer -pkg /Library/Developer/CommandLineTools/Packages/macOS_SDK_headers_for_macOS_10.14.pkg -target /
```

After this, proceed to the common directions for MacOS and Linux.

### Linux

The following packages are required for building the challenges on Linux:

```
libc6-dev libc6-dev-i386 gcc-multilib g++-multilib clang cmake
```

### MacOS/Linux Common Directions

First, install pre-requisites via pip.

```
sudo pip install xlsxwriter pycrypto defusedxml pyyaml matplotlib
```

Then to build all challenges, run:

```bash
$ ./build.sh
```

If you are **absolutely certain** that you don't intend to use any of the Python components of the
build or repository, you can tell the build script to ignore them:

```bash
$ NO_PYTHON_I_KNOW_WHAT_I_AM_DOING_I_SWEAR=1 ./build.sh
```

This is **not** a publicly supported build mode.

#### Build 64-bits version of the challenges
By default, the build system will build 32 bits version of the challenges.
However, by defining `BUILD64`, the build system will build 64-bits version of the challenges.

```bash
$ BUILD64=1 ./build.sh
```

Note: This has only been tested on *Linux*

### Windows

The following packages are required for building the challenges on Windows:

|Name                             |  Version/Info                       |
|---------------------------------|-------------------------------------|
| Visual Studio Build Tools       | included in Visual Studio           |
| Windows SDK (for running tests) | optional install with Visual Studio |
| CMake                           | 3.1+                                |
| Clang                           | 3.8+                                |

**Note:** depending on where you clone the repo, you may run into build errors about the path being too long. It's best to clone the repo closer to your root directory, e.g. `C:\cb-multios\`

To build all challenges, run:

```
> powershell .\build.ps1
```

## Testing

The `tester.py` utility is a wrapper around `cb-test` that can be used to test challenges and summarize results. The [`cb-test`](https://github.com/CyberGrandChallenge/cb-testing) tool is a testing utility created for the DARPA Cyber Grand Challenge to verify CBs are fully functional.

`cb-test` has been modified to run tests locally with no networking involved. All changes include:

* The removal of any kind of server for launching challenges
* Skipping any checks that verify the file is a valid DECREE binary
* Lessening sleeps and timeouts to allow tests to run at a reasonable rate

### Options

```
-a / --all: Run tests against all challenges
-c / --chals [CHALS ...]: Run tests against individual challenges
--povs: Only test POVs for every challenge
--polls: Only test POLLs for every challenge
-o / --output OUTPUT: Output a summary of the results to an excel spreadsheet
```

### Example Usage

The following will run tests against all challenges in `challenges` and save the results to `out.xlsx`:

```bash
$ ./tester.py -a -o out.xlsx
```

To run tests against only two challenges, do this:

```bash
$ ./tester.py -c Palindrome basic_messaging
```

To test all POVs and save the results, run:

```bash
$ ./tester.py -a --povs -o out.xlsx
```

### Types of Tests

All tests are a series of input strings and expected output for a challenge. There are two types of tests that are used:

`POV (Proof of Vulnerability)`: These tests are intended to exploit any vulnerabilities that exist in a challenge. They are expected to pass with the patched versions of the challenges, and in many cases cause the unpatched version to crash.

`POLL`: These tests are used to check that a challenge is functioning correctly, and are expected to pass with both the unpatched and patched versions of challenges.

### Type 1 POV notice

Verifying type 1 POVs relies on analyzing the core dump generated when a process crashes. They can be enabled with:

###### OS X:
```bash
$ sudo sysctl -w kern.coredump=1
```

###### Linux:
```bash
$ ulimit -c unlimited
```

###### Windows:

Merge `tools/win_enable_dumps.reg` into your registry. Note that this will disable the Windows Error Reporting dialog when a program crashes, so it's recommended that you do this in a VM if you want to keep that enabled.

## Current Status

Porting the Challenge Binaries is a work in progress. Please help us out by
reporting any build and/or behavior errors you discover!

## Notes

We use the CMake build system to enable portability across different compilers and operating systems. CMake works across a large matrix of compiler and operating system versions, while providing a consistent interface to check for dependencies and build software projects.

We are working to make this repository easier to use for the evaluation of program analysis tools. If you have questions about the challenge binaries, please [join our Slack](https://empireslacking.herokuapp.com) and we'll be happy to answer them.

## 64-bit Support

Full 64-bit support has been added and validated. All single-CB challenges pass their poll tests on x86-64.

### Building

```bash
$ BUILD64=1 ./build.sh
```

Rebuilding after source changes:

```bash
$ cmake --build build64/
```

### What Was Fixed

Three critical bug classes were discovered and fixed during the 64-bit porting effort:

1. **x86-64 ABI violation in `maths64.S`** — All 16 math functions (sin, cos, sqrt, pow, etc.) computed correctly in the x87 FPU but returned values in `st(0)` instead of `xmm0` as required by the System V x86-64 calling convention. This caused all 90 math-using challenges to produce incorrect results. Fixed by adding `fstpl (%rsp); movsd (%rsp), %xmm0` to each function.

2. **`intptr_t` type size** — `intptr_t` was defined as 32-bit `int` in 72 challenge-local `cgc_stdint.h` files, causing sign-extended pointer arithmetic (e.g., `0xfffffffff7a64030` instead of `0x7ffff7a64030`). Fixed with architecture-conditional `#ifdef __x86_64__`.

3. **`HEADER_PADDING` in custom malloc** — 18 challenges had a hardcoded `HEADER_PADDING=24` in their `cgc_malloc.h`, correct for 32-bit `struct blk_t` (24 bytes) but wrong for 64-bit (48 bytes). This caused heap corruption. Fixed with architecture-conditional sizing.

Additional per-challenge fixes were applied for pointer-size assumptions, struct serialization, and `cgc_size_t` usage in network protocols. See `migration/docs/` for detailed reports.

### Test Results

| Scope | Tests | Passed | Rate |
|-------|-------|--------|------|
| Single-CB challenges with polls | 180 | 180 | 100% |
| Math function unit tests | 67 | 67 | 100% |
| Multi-CB challenges | 13 | — | timeout-sensitive |

Multi-CB challenges may require extended timeouts (`--timeout 60` or higher) due to IPC pipe overhead.

### Python 3 Migration

The test infrastructure (`tools/`) was migrated from Python 2 to Python 3. Use a virtualenv:

```bash
$ python3 -m venv venv
$ source venv/bin/activate
$ pip install xlsxwriter pycrypto defusedxml pyyaml matplotlib
$ python tools/tester.py --all --polls --build-dir build64
```

### Migration Documentation

All migration artifacts are in the `migration/` directory:

- `migration/docs/` — Debug reports and technical analysis for individual challenges
- `migration/scripts/` — GDB scripts, test runners, automated fix scripts
- `migration/SCRIPTS.md` — Reference guide for all scripts
- `migration/tests/` — Unit test source for maths64.S validation

## Authors

Porting work was completed by Kareem El-Faramawi and Loren Maggiore, with help from Artem Dinaburg, Peter Goodman, Ryan Stortz, and Jay Little. Challenges were originally created by NARF Industries, Kaprica Security, Chris Eagle, Lunge Technology, Cromulence, West Point Military Academy, Thought Networks, and Air Force Research Labs while under contract for the DARPA Cyber Grand Challenge.

64-bit porting and Python 3 migration by Chengyu Song, with assistance from Claude Code.
