# basic_emulator 64-bit Test Failure Debugging

## Problem Summary

The `basic_emulator` challenge passes all poll tests on 32-bit but fails all 100 polls on 64-bit.
Both patched and unpatched 64-bit versions exhibit the same failure.

## Test Results

| Version | Result |
|---------|--------|
| 32-bit unpatched | ✅ PASS (100/100 polls) |
| 32-bit patched | ✅ PASS (100/100 polls) |
| 64-bit unpatched | ❌ FAIL (0/100 polls) |
| 64-bit patched | ❌ FAIL (0/100 polls) |

## Failure Mode

**Symptom**: After test 3 (500ms sleep), test 4 fails with:
```
not ok 4 - write failed.  wrote 0 of 1 bytes
```

**Root Cause**: The 64-bit emulator process exits prematurely (before test 4), causing the test framework's pipe to break with EPIPE.

## Investigation Process

### 1. Initial Hypothesis: STOP Instruction

**Theory**: The emulated Game Boy CPU was hitting a STOP instruction (opcode 0x10) that causes the emulator to exit.

**Testing**: Created GDB script to detect STOP instruction execution.

**Result**: ❌ REJECTED - No STOP instruction was executed before the exit.

### 2. Hypothesis: Crash or Signal

**Theory**: The 64-bit binary was crashing or receiving a signal.

**Testing**: Used GDB to monitor for crashes and signals.

**Result**: ❌ REJECTED - Process exits normally with code 0, no crashes detected.

### 3. Hypothesis: cgc__terminate Call

**Theory**: The code was explicitly calling cgc__terminate or exit.

**Testing**: Set GDB breakpoints on all exit functions.

**Result**: ❌ REJECTED - No explicit exit calls detected before termination.

### 4. strace Analysis: EPIPE Discovery

**Testing**: Attached strace to both 32-bit and 64-bit processes.

**Findings**:
- **64-bit**: `write(5, "?", 1) = -1 EPIPE (Broken pipe)` followed by `SIGPIPE`
- **32-bit**: `write(5, "?", 1) = 1` (succeeds)

**Key insight**: FD 5 is a pipe used for IPC. The 64-bit child process exits before the parent tries to write test 4 input.

### 5. Struct Layout Analysis

**Investigation**: Checked if pointer size differences cause memory corruption.

**32-bit layout**:
```
sizeof(gb_t) = 124 bytes
offsetof(title) = 8
offsetof(reg) = 70
offsetof(ticks) = 104
```

**64-bit layout**:
```
sizeof(gb_t) = 144 bytes
offsetof(title) = 16
offsetof(reg) = 86
offsetof(ticks) = 120
```

### 6. Buffer Overflow Vulnerability

**Discovery**: Found buffer overflow in `copy_title()` function (gb.c:201-214):

```c
static void copy_title(char *dst, const hdr_t *hdr)
{
    cgc_size_t i;
    for (i = 0; cgc_isupper(hdr->title[i]); i++)
        if (i < TITLE_SIZE)
            dst[i] = hdr->title[i];
#ifdef PATCHED
        else
            return;
#endif
    dst[i] = 0;  // <- VULNERABLE: writes past buffer if title has >16 uppercase chars
}
```

**Exploit**: The test ROM contains a 64-character uppercase title:
```
QZSFTBYXXPUYEJFUHSEHHVBMFHDKUHGXGQTSYTKODYMKGZMOEGJQXOLIFUCZAECK
```

**Impact analysis**:
- **32-bit**: Overflow writes at offset 72, corrupting `reg.PC` register
- **64-bit**: Overflow writes at offset 80, corrupting `palettes[2]` array

**Testing patched version**:
- 32-bit patched: ✅ PASS
- 64-bit patched: ❌ STILL FAILS

**Conclusion**: ❌ Buffer overflow is NOT the root cause (though it is a real vulnerability).

### 7. Process Execution Trace

**64-bit strace findings**:
```
1024289 write(1, "SP = FFFE, PC = 0154\n", ...) = ...
1024289 +++ exited with 0 +++
1024291 --- SIGCHLD {si_signo=SIGCHLD, si_code=CLD_EXITED, si_pid=1024289, si_status=0} ---
1024286 write(5, "?", 1) = -1 EPIPE (Broken pipe)
```

**Key finding**: The emulator child process (PID 1024289) completes normally and exits, then the parent tries to write the next test input and gets EPIPE.

**32-bit strace findings**:
```
1024435 read(0, "?", 1) = 1
1024435 read(0, "?", 1) = 1
1024435 read(0, "q", 1) = 1
1024435 +++ exited with 0 +++
```

**Key finding**: The 32-bit version continues running and accepts input '?', '?', 'q' after the 500ms sleep.

## Current Status

### What We Know

1. **Both patched and unpatched 64-bit versions fail** - This is not about the buffer overflow vulnerability
2. **The 64-bit emulator exits normally** - Not a crash or signal
3. **The timing is consistent** - Always fails after test 3 (500ms sleep), before test 4
4. **The exit appears intentional** - Process reaches `print_reg()` and exits with status 0
5. **FD 5 pipe breaks because child exits early** - EPIPE is a symptom, not the cause

### What We Don't Know

1. **Why does the 64-bit emulator exit after the 500ms sleep?**
   - Does it hit TICKS_MAX sooner?
   - Does it process input differently?
   - Is there a timing or race condition?

2. **What exit condition is triggered?**
   - The main loop exits when `cgc_gb_tick()` returns 0 or `cgc_check_input()` returns 0
   - Need to identify which one triggers on 64-bit

3. **Is there undefined behavior manifesting differently on 64-bit?**
   - Integer overflow/underflow?
   - Uninitialized memory?
   - Alignment issues?

## Recommended Next Steps

1. **Instrument cgc_gb_tick() and cgc_check_input()** to log return values
2. **Add tick counter logging** to verify if TICKS_MAX is reached
3. **Compare emulation state** at the 500ms mark between 32-bit and 64-bit
4. **Check for integer type mismatches** that could cause different behavior
5. **Verify floating point operations** - especially `speed` variable usage
6. **Examine the input processing** after sleep to see if 64-bit handles it differently

## Technical Details

### Type Definitions (Verified Correct)

- `cgc_size_t`: `unsigned long` (4 bytes on 32-bit, 8 bytes on 64-bit) ✅
- `cgc_ssize_t`: `long` (4 bytes on 32-bit, 8 bytes on 64-bit) ✅
- `cgc_fd_set`: Handles both architectures correctly ✅

### Exit Conditions in Code

From `main.c:282-300`:
```c
for (;;)
{
    if (!cgc_gb_tick(gb))
        break;  // Exit condition 1: tick returns 0

    if (gb->vblank)
    {
        if ((++vblanks % REFRESH_DIVIDER) == 0)
            draw_screen(gb);
        gb->vblank = 0;
    }

    if (ticks_sleep++ == TICKS_SLEEP * gb->speed)
    {
        if (!cgc_check_input(gb))
            break;  // Exit condition 2: check_input returns 0
        ticks_sleep = 0;
    }
}
print_reg(gb);
return 0;
```

### cgc_gb_tick() Return Conditions

From `gb.c:138-199`:
```c
int cgc_gb_tick(gb_t *gb)
{
    update_joypad(gb);

    if (!cgc_cpu_tick(gb))
        return 0;  // CPU tick failed

    if (!cgc_lcd_tick(gb))
        return 0;  // LCD tick failed

    if (++gb->ticks == TICKS_MAX)
    {
        ERR("Game Over");
        return 0;  // Hit max ticks (10 million)
    }

    // ... timer handling ...

    return 1;
}
```

### cgc_check_input() Return Conditions

From `main.c:236-255`:
```c
int cgc_check_input(gb_t *gb)
{
    cgc_fd_set fds;
    int readyfds = 0;
    struct cgc_timeval tv;

    FD_ZERO(&fds);
    FD_SET(STDIN, &fds);
    tv.tv_sec = 0;
    tv.tv_usec = SLEEP_US;

    if (cgc_fdwait(STDIN+1, &fds, NULL, &tv, &readyfds) != 0)
        return 0;  // fdwait failed

    if (readyfds)
    {
        return cgc_process_input(gb);  // Returns 0 if user pressed 'q'
    }
    return 1;
}
```

## Files Created During Investigation

### GDB Scripts
- `/tmp/debug_crash.gdb` - Crash detection
- `/tmp/debug_hang.gdb` - Hang detection with I/O tracing
- `/tmp/debug_stop_detection.gdb` - STOP instruction detection
- `/tmp/debug_exit_cause.gdb` - Exit path tracing
- `/tmp/trace_exit_code_1.gdb` - Exit code tracing
- `/tmp/check_stdout_value.gdb` - cgc_transmit FD monitoring
- `/tmp/trace_emulator_exit.gdb` - Main loop exit tracing
- `/tmp/check_ticks_simple.gdb` - Ticks monitoring
- `/tmp/trace_ticks_detailed.gdb` - Detailed tick tracing

### Shell Scripts
- `/tmp/run_with_strace.sh` - 64-bit strace attachment
- `/tmp/run_with_strace32.sh` - 32-bit strace attachment
- `/tmp/check_fds.sh` - 64-bit FD inspection
- `/tmp/check_fds32.sh` - 32-bit FD inspection
- `/tmp/trace_fd_writes.sh` - Write syscall tracing

### Analysis Tools
- `/tmp/check_struct_layout.c` - Struct size/offset calculator
- `/tmp/check_overflow_impact.c` - Buffer overflow impact analyzer
- `/tmp/check_opcode_10.c` - Opcode pattern matcher
- `/tmp/test_float_comparison.c` - Floating point comparison tester

### Trace Outputs
- `/tmp/gdb_output_*.txt` - Various GDB session outputs
- `/tmp/basic_emu64_strace.log` - 64-bit strace trace
- `/tmp/basic_emu32_strace.log` - 32-bit strace trace
- `/tmp/full_fd_trace64.log` - Complete 64-bit FD operations
- `/tmp/full_fd_trace32.log` - Complete 32-bit FD operations

## Conclusion

The basic_emulator 64-bit failure is **NOT** caused by:
- The buffer overflow vulnerability (patched version also fails)
- Crashes or signals (exits normally)
- STOP instruction execution (never hit)
- Explicit exit calls (no cgc__terminate detected)

The failure **IS** caused by:
- The emulator reaching a normal exit condition prematurely on 64-bit
- Either `cgc_gb_tick()` or `cgc_check_input()` returning 0 earlier than expected
- Some architecture-dependent difference in execution timing or state

**Further investigation required** to identify the exact trigger for early termination.
