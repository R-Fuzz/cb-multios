# maths64.S Float Function Return Bug Fix

**Date**: 2025-11-02
**Issue**: Childs_Game 64-bit crash on GEN_00000_00005.xml
**Root Cause**: All float functions returning double instead of float + stack corruption in exp2/pow/exp helpers
**Status**: ✅ RESOLVED - All 79 unit tests passing

---

## Problem Discovery

### Initial Symptom
Childs_Game crashed with SIGSEGV at test 37 during poll execution:
```
ok 36 - write: sent 1 bytes
# [DEBUG] pid: 1517304, sig: 11
not ok 37 - recv failed
```

### GDB Analysis
Crash occurred in `cgc_hi_lo()` at main.c:103 after calling `cgc_log2f(upper_limit)` at hi_lo_game.c:89:
```c
unsigned int guesses_left = cgc_log2f(upper_limit) + 1;  // Line 89
```

The crash backtrace showed corrupted `player` pointer, indicating `cgc_log2f()` returned garbage.

---

## Root Cause Analysis

### Issue 1: Float Functions Returning Double (CRITICAL)

**x86-64 ABI calling convention:**
- **Float (32-bit)**: returned in lower 32 bits of %xmm0 using `movss`
- **Double (64-bit)**: returned in full 64 bits of %xmm0 using `movsd`
- **Long double (80-bit)**: returned via x87 FPU stack (st(0))

**The Bug:**
All 15+ float functions shared code paths with double functions and used `movsd` (64-bit) instead of `movss` (32-bit), reading garbage from upper 32 bits.

**Example - cgc_log2f (BEFORE FIX):**
```asm
SYM(cgc_log2f):
    sub     $8, %rsp
    movss   %xmm0, (%rsp)
    flds    (%rsp)
    add     $8, %rsp
    jmp     1f                    # Jump to shared code
SYM(cgc_log2):
    sub     $8, %rsp
    movsd   %xmm0, (%rsp)
    fldl    (%rsp)
1:
    fld1
    fxch
    fyl2x
    fstpl   (%rsp)                # Store as long double
    movsd   (%rsp), %xmm0         # ❌ BUG: Load 64-bit double for BOTH!
    add     $8, %rsp
    ret
```

**After Fix:**
```asm
SYM(cgc_log2f):
    sub     $8, %rsp
    movss   %xmm0, (%rsp)
    flds    (%rsp)
    fld1
    fxch
    fyl2x
    fstps   (%rsp)                # ✅ Store single precision
    movss   (%rsp), %xmm0         # ✅ Load 32-bit float
    add     $8, %rsp
    ret
SYM(cgc_log2):
    sub     $8, %rsp
    movsd   %xmm0, (%rsp)
    fldl    (%rsp)
    fld1
    fxch
    fyl2x
    fstpl   (%rsp)
    movsd   (%rsp), %xmm0
    add     $8, %rsp
    ret
```

### Issue 2: Stack Corruption in exp2/pow/exp Helpers

**The Problem:**
`cgc_exp2x` helper used `fstpl` which stores 10 bytes (80-bit extended precision), but only 8 bytes were allocated.

**Initial buggy code:**
```asm
SYM(cgc_exp2):
    sub     $8, %rsp              # ❌ Only 8 bytes!
    movsd   %xmm0, (%rsp)
    fldl    (%rsp)
SYM(cgc_exp2x):
    fld     %st(0)
    frndint
    fsubr   %st,%st(1)
    fxch
    f2xm1
    fld1
    faddp
    fscale
    fstp    %st(1)
    fstpl   (%rsp)                # ❌ Writes 10 bytes, corrupts 2 bytes!
    movsd   (%rsp), %xmm0
    add     $8, %rsp
    ret
```

**After Fix:**
```asm
SYM(cgc_exp2):
    sub     $16, %rsp             # ✅ 16 bytes for alignment
    movsd   %xmm0, (%rsp)
    fldl    (%rsp)
SYM(cgc_exp2x):
    fld     %st(0)
    frndint
    fsubr   %st,%st(1)
    fxch
    f2xm1
    fld1
    faddp
    fscale
    fstp    %st(1)
    fstpl   (%rsp)                # ✅ 10 bytes stored safely
    movsd   (%rsp), %xmm0
    add     $16, %rsp             # ✅ Deallocate 16 bytes
    ret
```

### Issue 3: Stack Depth Mismatch in Jump Paths

**The Problem:**
`cgc_pow` was deallocating stack before jumping to `cgc_exp2x`:

```asm
SYM(cgc_pow):
    sub     $16, %rsp
    movsd   %xmm1, 8(%rsp)
    movsd   %xmm0, (%rsp)
    fldl    8(%rsp)
    fldl    (%rsp)
    add     $16, %rsp             # ❌ Deallocates too early!
    fyl2x
    jmp     SYM(cgc_exp2x)        # exp2x expects 16 bytes allocated
```

**After Fix:**
```asm
SYM(cgc_pow):
    sub     $16, %rsp
    movsd   %xmm1, 8(%rsp)
    movsd   %xmm0, (%rsp)
    fldl    8(%rsp)
    fldl    (%rsp)
    fyl2x
    jmp     SYM(cgc_exp2x)        # ✅ Keeps 16 bytes for exp2x
```

---

## Affected Functions (15+)

### All Float Functions Fixed:
- **Trigonometric**: `sinf`, `cosf`, `tanf`
- **Logarithmic**: `logf`, `log10f`, `log2f` ⚠️ *Caused Childs_Game crash*
- **Exponential**: `expf`, `exp2f`, `powf`
- **Other**: `sqrtf`, `fabsf`, `atan2f`, `remainderf`, `significandf`, `scalbnf`, `scalblnf`, `rintf`

### Special Handling for exp2/pow/exp Family:

Created separate float helper `cgc_exp2xf`:
- **cgc_exp2x**: For double (returns via movsd, needs 16-byte stack)
- **cgc_exp2xf**: For float (returns via movss, manages own 8-byte stack)

Long double versions (`*l`) are independent and return via FPU stack.

---

## Why 32-bit Didn't Have This Bug

In 32-bit x86, **ALL** floating point values (float, double, long double) are returned via the x87 FPU stack (st(0)). The FPU stack naturally preserves precision, so shared code paths worked correctly:

**32-bit maths.S (no bug):**
```asm
SYM(cgc_log2f):
    flds    4(%esp)               # Load float
    jmp     1f
SYM(cgc_log2):
    fldl    4(%esp)               # Load double
1:
    fld1
    fxch
    fyl2x
    ret                           # ✅ Return via FPU stack - works for both!
```

---

## Test Coverage Gap

### Original Problem
`migration/tests/test_maths64.c` **only tested double functions**:

```c
extern double cgc_sin(double x);     // ✅ Tested
extern double cgc_cos(double x);     // ✅ Tested
extern double cgc_log2(double x);    // ✅ Tested

// Missing:
// extern float cgc_sinf(float x);   // ❌ NOT tested
// extern float cgc_cosf(float x);   // ❌ NOT tested
// extern float cgc_log2f(float x);  // ❌ NOT tested - this caused crash!
```

### Fix Applied
Added comprehensive float function tests:
```c
extern float cgc_sinf(float x);
extern float cgc_cosf(float x);
extern float cgc_log2f(float x);
// ... all 15+ float functions

void test_float(const char *name, float result, float expected) {
    // Test with TOLERANCE_FLOAT 1e-6
}

// Added tests:
test_float("log2f(65536.0f)", cgc_log2f(65536.0f), 16.0f);  // UPPER_RAND_MAX+1
```

---

## Verification

### Unit Test Results
```
=== Test Summary ===
Total tests: 79
Passed: 79
Failed: 0

✓ All tests passed!
```

### Stack Audit
All jump paths verified for correct stack depth:

| Function | Allocates | Jumps To | Depth at Jump | Helper Expects | Status |
|----------|-----------|----------|---------------|----------------|--------|
| exp2f    | +8,-8     | exp2xf   | 0             | 0              | ✅ OK   |
| exp2     | +16       | exp2x    | 16            | 16             | ✅ OK   |
| powf     | +16,-16   | exp2xf   | 0             | 0              | ✅ OK   |
| pow      | +16       | exp2x    | 16            | 16             | ✅ OK   |
| expf     | +8,-8     | exp2xf   | 0             | 0              | ✅ OK   |
| exp      | +16       | exp2x    | 16            | 16             | ✅ OK   |

### Childs_Game Test
```bash
python tools/cb-replay.py \
  --cbs build64/challenges/Childs_Game/Childs_Game \
  --xml polls/Childs_Game/poller/for-release/GEN_00000_00005.xml

# Result: ✅ All 484 tests passed
# Previously failed at test 37 with SIGSEGV
```

---

## Files Modified

1. **include/maths64.S** - Fixed all 15+ float functions and stack issues
2. **include/libcgc.h** - Already correct (no changes needed)
3. **migration/tests/test_maths64.c** - Added comprehensive float function tests

---

## Key Takeaways

### Technical Insights

1. **x86-64 vs x86-32 differences**:
   - 32-bit: All FP returns via FPU stack → shared code works
   - 64-bit: Float/double via XMM registers → need separate paths

2. **Assembly precision matters**:
   - `fstps` vs `fstpl`: 32-bit vs 80-bit storage
   - `movss` vs `movsd`: 32-bit vs 64-bit XMM load/store
   - Stack alignment: `fstpl` needs 16 bytes (stores 10, but alignment)

3. **Test coverage is critical**:
   - Double functions all worked, so tests passed
   - Float functions were completely untested
   - Need to test ALL type variants (float, double, long double)

### Project Impact

- **Fixes Childs_Game crash** and likely many other challenges using float math
- **Improves 64-bit port quality** - fundamental math library correctness
- **Establishes testing pattern** - test all type variants, not just one

---

## Related Issues

This same pattern may exist in other 64-bit porting efforts. When porting from 32-bit to 64-bit:
- ✅ Check ALL floating point return types
- ✅ Verify stack allocation sizes for FPU operations
- ✅ Test float, double, AND long double variants
- ✅ Don't assume shared code paths work on different architectures
