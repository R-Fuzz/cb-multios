# BudgIT 32-bit/64-bit Compatibility Fix

## Problem

BudgIT 32-bit binary was failing poll tests with error:
```
not ok 8 - recv failed. No data returned.
# [DEBUG] pid: 1174651, sig: 1
```

The 64-bit binary passed all tests with the same poll XMLs.

## Root Cause Analysis

### Issue 1: Architecture-dependent `unsigned long` Type

The BudgIT source code used `unsigned long` for instruction values:

**challenges/BudgIT/src/service.c:27,92**
```c
void cgc_receiveInstruction(unsigned long *instruction) {
    int bytes_read;
    bytes_read = cgc_recv(STDIN, (char *)instruction, sizeof(unsigned long));
    // ...
}

int main(int cgc_argc, char *cgc_argv[]) {
    unsigned long instruction;
    // ...
}
```

**Problem:** `unsigned long` size is architecture-dependent:
- **32-bit systems**: 4 bytes
- **64-bit systems**: 8 bytes (LP64 model)

### Issue 2: Poll Generator Used Architecture-dependent Pack Format

The poll generator used Python's `pack('l')` format:

**challenges/BudgIT/poller/for-release/machine.py**
```python
instruction = pack('l', 1)  # 'l' = long (platform-dependent)
```

**Problem:** `pack('l')` size varies by platform:
- On 64-bit systems: 8 bytes
- On 32-bit systems: 4 bytes (but would be 8 on 64-bit Python)

### Issue 3: Python 2 to Python 3 Migration

The `generate-polls` tool was Python 2, incompatible with modern systems.

## Investigation Process

1. **GDB Debugging**: Used `cb-replay-gdb.py` with `debug_hang.gdb` to trace I/O operations
   - Showed process receiving data byte-by-byte correctly
   - Process exited with code 01 (not crash) after 7 successful tests

2. **XML Analysis**: Examined poll XML structure
   ```xml
   <write><data>\x01\x00\x00\x00\x00\x00\x00\x00</data></write>
   ```
   - 8 bytes sent (instruction value 1 as 64-bit long)
   - 32-bit binary expected only 4 bytes
   - Extra 4 bytes corrupted subsequent data stream

3. **64-bit Testing**: Verified 64-bit binary passed same tests
   - Confirmed polls were generated for 64-bit architecture

## Solution

### 1. Fixed Source Code to Use Fixed-width Type

**challenges/BudgIT/src/service.c**
```c
// OLD:
void cgc_receiveInstruction(unsigned long *instruction) {
    bytes_read = cgc_recv(STDIN, (char *)instruction, sizeof(unsigned long));

// NEW:
void cgc_receiveInstruction(uint32_t *instruction) {
    bytes_read = cgc_recv(STDIN, (char *)instruction, sizeof(uint32_t));
```

**Rationale:** `uint32_t` is always 4 bytes on both 32-bit and 64-bit systems (defined in `challenges/BudgIT/include/cgc_stdint.h` as `unsigned int`).

### 2. Fixed Poll Generator to Use Fixed-width Pack Format

**challenges/BudgIT/poller/for-release/machine.py**
```python
# OLD:
instruction = pack('l', 1)  # Platform-dependent

# NEW:
instruction = pack('I', 1)  # Always 4 bytes (unsigned int)
```

**Changed in 7 locations:**
- `newBudgetItem()` - instruction 1
- `newInBudgetTransaction()` - instruction 2
- `newOverBudgetTransaction()` - instruction 2
- `getBudget()` - instruction 3
- `deleteBudget()` - instruction 6
- `sendReport()` - instruction 7
- `quit()` - instruction 8

### 3. Upgraded generate-polls to Python 3

**tools/generate-polls/generate-polls**

Changes made:
1. Shebang: `#!/usr/bin/env python` → `#!/usr/bin/env python3`
2. Import: `import imp` → `import importlib.util`
3. Module loading:
   ```python
   # OLD:
   module = imp.load_source('state_machine', filename)

   # NEW:
   spec = importlib.util.spec_from_file_location('state_machine', filename)
   module = importlib.util.module_from_spec(spec)
   spec.loader.exec_module(module)
   ```
4. YAML: `yaml.load(graph_fh)` → `yaml.load(graph_fh, Loader=yaml.FullLoader)`
5. Function attributes: `func_name` → `__name__` (10 occurrences)
6. Print: `print "..."` → `print("...")`

**tools/generate-polls/generator/actions.py**

1. Import: `import ansi_x931_aes128` → `from . import ansi_x931_aes128`
2. String module: `string.letters` → `string.ascii_letters`
3. Hex encoding: `seed.encode('hex')` → `seed.hex()` (with bytes handling)
4. Bytes handling in `encode()`:
   ```python
   # Convert bytes to string if necessary (Python 3 compatibility)
   if isinstance(data, bytes):
       data = data.decode('latin-1')
   ```

**tools/generate-polls/generator/graph.py**

1. Dict keys: `nodes = self._neighbors[node].keys()` → `nodes = list(self._neighbors[node].keys())`
2. Sorting: `nodes.sort()` → `nodes.sort(key=lambda x: x.__name__)`
3. Matplotlib: `plt.yscale('log', nonposy='clip')` → `plt.yscale('log', nonpositive='clip')`

### 4. Regenerated Poll XMLs

Used genpolls.sh parameters:
```bash
./tools/generate-polls/generate-polls \
  --count 100 \
  --store_seed \
  --depth 1048575 \
  challenges/BudgIT/poller/for-release/machine.py \
  challenges/BudgIT/poller/for-release/state-graph.yaml \
  polls/BudgIT/poller/for-release
```

Generated 100 new poll XMLs with correct 4-byte instruction format.

## Test Results

### Before Fix
- **32-bit**: ❌ Failed on GEN_00000_00000.xml (test 8)
- **64-bit**: ✅ Passed all tests

### After Fix
- **32-bit**: ✅ Passed all tests (245/245 on GEN_00000_00000.xml)
- **64-bit**: ✅ Passed all tests (245/245 on GEN_00000_00000.xml)

## Files Modified

1. **challenges/BudgIT/src/service.c** - Changed `unsigned long` → `uint32_t`
2. **challenges/BudgIT/poller/for-release/machine.py** - Changed `pack('l')` → `pack('I')`
3. **tools/generate-polls/generate-polls** - Python 3 upgrade
4. **tools/generate-polls/generator/actions.py** - Python 3 compatibility
5. **tools/generate-polls/generator/graph.py** - Python 3 compatibility
6. **polls/BudgIT/poller/for-release/*.xml** - Regenerated 100 poll files

## Lessons Learned

1. **Avoid platform-dependent types for serialization**: Use fixed-width types (`uint32_t`, `uint64_t`) instead of `long`, `unsigned long`, etc.

2. **Pack format matters**: Python's struct format codes:
   - `'l'` = long (4 bytes on 32-bit, 8 bytes on 64-bit)
   - `'I'` = unsigned int (always 4 bytes)
   - `'Q'` = unsigned long long (always 8 bytes)

3. **Test infrastructure must match**: Poll generators must produce data compatible with both architectures when using fixed-width types.

4. **Python 2 → 3 migration issues**:
   - Module loading APIs changed completely
   - String vs bytes distinction is strict
   - Dict methods return views, not lists
   - Function introspection changed

## Related Issues

This fix pattern applies to any challenge using architecture-dependent types for network protocol or file format serialization. Search for similar patterns:

```bash
# Find challenges using unsigned long in I/O
grep -r "unsigned long.*instruction\|unsigned long.*value" challenges/*/src/

# Find challenges using pack('l') or pack('q')
grep -r "pack('l'\|pack('q'" challenges/*/poller/
```

## References

- CLAUDE.md: Project porting guidelines
- LP64 data model: https://en.wikipedia.org/wiki/64-bit_computing#64-bit_data_models
- Python struct format codes: https://docs.python.org/3/library/struct.html#format-characters
