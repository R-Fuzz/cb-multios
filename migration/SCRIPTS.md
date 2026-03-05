# Migration Scripts Reference

Scripts, tools, and data used during the CGC 64-bit migration effort.

## Directory Layout

```
migration/
├── SCRIPTS.md              # This file
├── README.md
├── docs/                   # Analysis and debug reports
├── tests/                  # Unit test source and results
├── data/                   # Test output data and logs
└── scripts/
    ├── debug/              # GDB scripts and debug agents
    ├── testing/            # Test runners
    ├── analysis/           # Comparison and analysis tools
    ├── *.sh                # Top-level fix/scan scripts
```

## scripts/debug/ — GDB Scripts & Debug Agents

| File | Description |
|------|-------------|
| `debug_crash.gdb` | Catches SIGSEGV/SIGABRT/SIGBUS/SIGFPE/SIGILL, prints backtrace and registers on crash. Use with `cb-replay-gdb.py --gdb_script`. |
| `debug_hang.gdb` | Like `debug_crash.gdb` plus breakpoints on `cgc_receive`/`cgc_transmit` for I/O tracing. Good for timeout debugging. |
| `debug_malloc_simple.gdb` | Traces malloc/free calls to detect heap corruption. |
| `debug_malloc_trace.gdb` | Detailed 64-bit malloc tracing with allocation tracking. |
| `debug_malloc_trace32.gdb` | 32-bit variant of malloc tracing. |
| `debug_uninit_memory.gdb` | Detects use of uninitialized memory (64-bit). |
| `debug_uninit_memory64.gdb` | Extended uninitialized memory detection for 64-bit. |
| `debug_agent.py` | Automated debugging agent that follows the manual GDB workflow: run test, check crash/hang, analyze trace. |
| `auto_debug_agent.py` | Orchestrator that launches independent debug agents for parallel 64-bit porting. |

### Usage Example

```bash
source venv/bin/activate
python tools/cb-replay-gdb.py \
  --cbs build64/challenges/Accel/Accel \
  --xml polls/Accel/poller/for-release/GEN_00000.xml \
  --debug --gdb_script migration/scripts/debug/debug_crash.gdb
# Check output: /tmp/gdb_output_<pid>.txt
```

## scripts/testing/ — Test Runners

| File | Description |
|------|-------------|
| `test_challenges.sh` | Test specific 64-bit challenges by name. Usage: `bash migration/scripts/testing/test_challenges.sh FASTLANE Accel` |
| `test_all_challenges.sh` | Run poll tests for all challenges sequentially. |
| `test_anagram_direct.sh` | Targeted test for the `anagram_game` challenge (known timeout-sensitive). |
| `test_pov_with_strace.py` | Run POV tests under strace to trace syscalls. |
| `test_strace_runner.py` | Helper for strace-based test execution. |
| `run_pov_strace_direct.py` | Feed POV input directly to a challenge binary under strace (bypasses test framework). |

### Usage Example

```bash
source venv/bin/activate

# Test specific challenges
bash migration/scripts/testing/test_challenges.sh FASTLANE Casino_Games

# Test all challenges
bash migration/scripts/testing/test_all_challenges.sh
```

## scripts/analysis/ — Comparison & Analysis Tools

| File | Description |
|------|-------------|
| `compare_32_64_tests.py` | Systematically test and compare 32-bit vs 64-bit poll results for each challenge. |
| `compare_simple.py` | Lightweight 32-bit vs 64-bit comparison using `cb-replay.py` directly. |
| `check_timeout_failures.py` | Parse test logs for FAIL results and re-run without timeout to distinguish real failures from timeout issues. |
| `code_analyzer.py` | Scan challenge source code for common 64-bit porting patterns (pointer casts, `sizeof` assumptions, struct packing). |
| `decode_varint.py` | Utility to decode variable-length integers from POV test data. Used during `anagram_game` investigation. |

## scripts/ (top-level) — Fix & Scan Scripts

| File | Description |
|------|-------------|
| `fix_all_intptr.sh` | Automated fix for `intptr_t` type size bug across 72 `cgc_stdint.h` files. |
| `fix_all_header_padding.sh` | Automated fix for `HEADER_PADDING` heap corruption across 18 `cgc_malloc.h` files. |
| `find_math_bins.sh` | Find challenge binaries that link against maths64.S functions. |
| `analyze_math_usage.sh` | Analyze which math functions each challenge uses. |
| `summarize_math.sh` | Generate usage statistics from math analysis. |
| `run_all_polls.sh` | Run poll tests for all challenges (sequential). |
| `run_all_polls_parallel.sh` | Run poll tests for all challenges in parallel (uses xargs -P). |
| `run_math_polls.sh` | Run poll tests for all 90 math-using challenges only. |

## data/ — Test Output & Logs

| File | Description |
|------|-------------|
| `test_comparison_results.json` | 32-bit vs 64-bit comparison results (per-challenge). |
| `test_progress.txt` | List of challenges tested during migration. |
| `retest_later.txt` | Challenges flagged for re-testing. |
| `timeout_check_results.txt` | Results from timeout failure analysis. |
| `test_simple.xml` | Minimal test XML used for quick validation. |

## tests/ — Unit Tests

| File | Description |
|------|-------------|
| `test_maths64.c` | Unit test suite for all 16 maths64.S functions (67 test cases). |
| `test_maths64` | Compiled test binary. |
| `accel_test_output.txt` | Captured output from Accel integration test (200/200 passed). |
