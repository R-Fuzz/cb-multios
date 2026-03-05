# basic_emulator 64-bit Fix - Solution

## Problem Summary

The `basic_emulator` challenge failed all poll tests on 64-bit but passed on 32-bit. Both patched and unpatched versions exhibited the same failure.

## Root Cause

**Bug Location**: `include/libcgc.h` lines 66-73

**Bug**: The `CGC_FD_SET`, `CGC_FD_CLR`, and `CGC_FD_ISSET` macros used integer literal `1` instead of long literal `1L` for bit shifting operations.

**Why This Matters**:
- On 64-bit systems, `_fd_mask` is `long int` (8 bytes, 64 bits)
- `CGC__NFDBITS = 8 * sizeof(_fd_mask) = 64` on 64-bit
- The macros perform bit shifts like `(1 << (fd & 63))`
- When `fd ≥ 32`, this becomes `(1 << 32)` or higher
- Since `1` is an `int` (32 bits), shifting by ≥32 is **undefined behavior**
- In practice on x86-64, the shift amount wraps: `1 << 32` behaves like `1 << 0` = `1`

**Specific Failure**:
- Setting FD 0 with `FD_SET(0, &fds)` correctly sets bit 0
- But checking FD 32 with `FD_ISSET(32, &fds)` incorrectly returns true:
  - `_fd_bits[0] & (1 << 32)`
  - Due to wraparound: `1 << 32` → `1 << 0` → `1`
  - So it checks bit 0 instead of bit 32!
- When `cgc_fdwait()` scans for set FDs, it finds FD 32 set
- FD 32 ≥ EXPECTED_MAX_FDS (23), so it returns `CGC_EBADF`
- The error causes `cgc_check_input()` to return 0, exiting the emulator

## The Fix

**File**: `include/libcgc.h`

**Change**: Replace `1` with `1L` in the bit shift operations:

```diff
 #define CGC_FD_SET(b, set) \
-    ((set)->_fd_bits[b / CGC__NFDBITS] |= (1 << (b & (CGC__NFDBITS - 1))))
+    ((set)->_fd_bits[b / CGC__NFDBITS] |= (1L << (b & (CGC__NFDBITS - 1))))

 #define CGC_FD_CLR(b, set) \
-    ((set)->_fd_bits[b / CGC__NFDBITS] &= ~(1 << (b & (CGC__NFDBITS - 1))))
+    ((set)->_fd_bits[b / CGC__NFDBITS] &= ~(1L << (b & (CGC__NFDBITS - 1))))

 #define CGC_FD_ISSET(b, set) \
-    ((set)->_fd_bits[b / CGC__NFDBITS] & (1 << (b & (CGC__NFDBITS - 1))))
+    ((set)->_fd_bits[b / CGC__NFDBITS] & (1L << (b & (CGC__NFDBITS - 1))))
```

**Why This Works**:
- `1L` is a `long` literal, matching the `_fd_mask` type
- On 64-bit: `1L` is 64 bits, so `1L << 32` is well-defined
- On 32-bit: `1L` is 32 bits, same as before (no change in behavior)

## Testing Results

### Before Fix
```
32-bit unpatched: ✅ PASS (100/100 polls)
32-bit patched:   ✅ PASS (100/100 polls)
64-bit unpatched: ❌ FAIL (0/100 polls)
64-bit patched:   ❌ FAIL (0/100 polls)
```

### After Fix
```
32-bit unpatched: ✅ PASS (100/100 polls)
32-bit patched:   ✅ PASS (100/100 polls)
64-bit unpatched: ✅ PASS (100/100 polls)
64-bit patched:   ✅ PASS (100/100 polls)
```

**All 200 tests now pass!**

## Investigation Process

### Debugging Steps

1. **Initial hypotheses ruled out**:
   - ❌ Buffer overflow vulnerability (patched version also failed)
   - ❌ STOP instruction causing exit
   - ❌ Crashes or signals
   - ❌ Explicit exit() calls
   - ❌ Struct layout issues
   - ❌ Type size mismatches

2. **Key discovery via strace**:
   - Found that `cgc_fdwait()` was failing with `EBADF`
   - 64-bit: `write(5, "?", 1) = -1 EPIPE` (pipe broken because child exited)
   - 32-bit: `write(5, "?", 1) = 1` (succeeded)

3. **Traced the error path**:
   - Used GDB to break at `cgc_fdwait()` return
   - Found it returned error code 1 (`CGC_EBADF`)
   - Traced into `cgc_copy_cgc_fd_set()`

4. **Found the smoking gun**:
   - GDB showed FD 32 was set in the fd_set when only FD 0 should be
   - Created test program to reproduce: confirmed FD 0 and FD 32 both appeared set
   - Analyzed the macro and identified the integer overflow/undefined behavior

5. **Verified the fix**:
   - Changed `1` to `1L` in test program - only FD 0 set ✓
   - Applied fix to `libcgc.h`
   - Rebuilt and tested - all polls pass ✓

## Technical Details

### Bit Shift Undefined Behavior in C

From the C standard (C11 §6.5.7):
> The result of E1 << E2 is E1 left-shifted E2 bit positions; vacated bits are filled with zeros. If E1 has an unsigned type, the value of the result is E1 × 2^E2, reduced modulo one more than the maximum value representable in the result type. If E1 has a signed type and nonnegative value, and E1 × 2^E2 is representable in the result type, then that is the resulting value; **otherwise, the behavior is undefined**.

Additionally:
> If the value of the right operand is negative or is greater than or equal to the width of the promoted left operand, **the behavior is undefined**.

### Why x86-64 Wraps the Shift

On x86-64, the `SHL` instruction only uses the low 5 bits of the shift count for 32-bit operands and low 6 bits for 64-bit operands. This is a CPU-level behavior, not guaranteed by C. So:
- `SHL eax, 32` → uses shift count `32 & 31 = 0` → no shift
- `SHL rax, 32` → uses shift count `32 & 63 = 32` → proper shift

This CPU behavior caused the bug to manifest as FD 32 aliasing to FD 0.

### Similar Bugs in Other Code

This bug could affect any code using similar bit manipulation patterns. Search for:
```bash
grep -r "1 <<" --include="*.h" --include="*.c"
```

And verify that shifts can never exceed the operand width, or use appropriately-sized literals (`1L`, `1UL`, etc.).

## Impact

This bug affects **ALL 64-bit challenges** that use `cgc_fdwait()`, potentially causing:
- Spurious `EBADF` errors
- Incorrect file descriptor checks
- Premature process termination

It only manifests when the FD scan loop checks FD values ≥ 32.

## Files Modified

- `include/libcgc.h` - Fixed FD manipulation macros

## Related Files

- `include/libcgc.c` - Contains `cgc_fdwait()` implementation
- `challenges/basic_emulator/src/main.c` - Uses `FD_SET`/`FD_ISSET` via `cgc_check_input()`

## Lessons Learned

1. **Bit shift operations require careful type matching**
   - Use `1L` for long, `1ULL` for unsigned long long, etc.

2. **Undefined behavior is not always obvious**
   - Code may work on some platforms and fail on others
   - Compiler optimizations can expose UB in unexpected ways

3. **Cross-architecture porting requires thorough testing**
   - Even "simple" macro changes can have subtle effects
   - Type sizes matter: int vs long, 32-bit vs 64-bit

4. **GDB + test programs are invaluable for debugging**
   - Reproducing issues in isolation helps identify root causes
   - Adding detailed logging reveals unexpected behavior

## Verification

To verify the fix works correctly:

```bash
# Test 64-bit
source venv/bin/activate
python tools/tester.py -c basic_emulator --polls

# Should show:
# Testing basic_emulator...
# POLL:
#   for-release: Running 200 test(s) => Passed 200/200
```
