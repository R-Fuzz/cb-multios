# Diary_Parser 64-bit Fix

## Problem

Diary_Parser was failing on 64-bit builds with SIGSEGV. The test `GEN_00000_00000.xml` was crashing immediately during initialization.

## Initial Debugging

```bash
# First test run showed immediate crash
python tools/cb-replay.py --cbs build64/challenges/Diary_Parser/Diary_Parser \
  --xml polls/Diary_Parser/poller/for-testing/GEN_00000_00000.xml --debug

# Output: sig: 11 (SIGSEGV)
```

Using GDB to get backtrace:
```bash
echo -e "\x02\x01" | gdb -batch -ex "set env seed=..." -ex "run" -ex "bt" \
  build64/challenges/Diary_Parser/Diary_Parser
```

Initial crash location: `cgc_malloc()` at `challenges/Diary_Parser/lib/stdlib.c:612`

## Root Cause Analysis

The Diary_Parser challenge includes a custom memory allocator implementation in `challenges/Diary_Parser/lib/stdlib.c`. This custom malloc/free has multiple 64-bit compatibility issues.

### Data Structure Differences

**32-bit:**
- `sizeof(heap_header) = 8` bytes
- `sizeof(heap_block_header) = 12` bytes (estimated)
- `cgc_size_t = unsigned long` (4 bytes)

**64-bit:**
- `sizeof(heap_header) = 16` bytes (due to 8-byte alignment of cgc_size_t)
- `sizeof(heap_block_header) = 24` bytes
- `cgc_size_t = unsigned long` (8 bytes)

### Bug #1: Incorrect Heap Accounting in malloc

**Location:** `stdlib.c:609`

**Original Code:**
```c
blockHead->remaining_size-=size;
```

**Problem:** The code only decremented by the requested data size, not including the header overhead. Each allocation actually consumes `size + sizeof(heap_header)` bytes, but `remaining_size` was only decremented by `size`.

In 64-bit:
- Each 30-byte allocation consumes 30 + 16 = 46 bytes
- But `remaining_size` only decreased by 30 bytes
- After ~88 allocations, the accounting was completely wrong
- The code thought there were 1432 bytes remaining when the heap was actually full
- When walking the chunk list at line 612, it accessed invalid memory → SIGSEGV

**Fix:**
```c
blockHead->remaining_size-=size+sizeof(heap_header);
```

### Bug #2: Incomplete New Block Allocation

**Location:** `stdlib.c:598-618`

**Original Code:**
```c
blockHead = (heap_block_header *)cgc_heap_manager->blocks;
if(size > blockHead->remaining_size) {
    cgc_allocate(4096, 0, (void *)&blockHead->next);
    if(blockHead->next == NULL) {
        cgc_puts("Not enough space available to allocate more heap.  Failure.");
        cgc__terminate(-1);
    }
    blockHead = blockHead->next;
    blockHead->remaining_size = 4096-sizeof(heap_block_header);
} else {
    heap_header *chunkHeader;
    blockHead->remaining_size-=size;
    chunkHeader = (heap_header *)blockHead->data;
    // ... allocation logic ...
    return (char *)chunkHeader+sizeof(heap_header);
}
return 0;  // BUG: Returns NULL when new block allocated!
```

**Problems:**
1. When a new 4096-byte block was allocated, it wasn't zeroed (unlike the first block at line 593)
2. The function returned 0 (NULL) after allocating a new block, instead of allocating from it
3. Uninitialized memory in new blocks caused the chunk walking loop to read garbage flags/sizes

**Fix:**
```c
blockHead = (heap_block_header *)cgc_heap_manager->blocks;
if(size > blockHead->remaining_size) {
    cgc_allocate(4096, 0, (void *)&blockHead->next);
    if(blockHead->next == NULL) {
        cgc_puts("Not enough space available to allocate more heap.  Failure.");
        cgc__terminate(-1);
    }
    cgc_memset(blockHead->next, 0, 4096);  // Zero the new block
    blockHead = blockHead->next;
    blockHead->remaining_size = 4096-sizeof(heap_block_header);
    blockHead->next = NULL;
}

// Removed 'else' - always allocate from current block
heap_header *chunkHeader;
blockHead->remaining_size-=size+sizeof(heap_header);
chunkHeader = (heap_header *)blockHead->data;

while((chunkHeader->flags & INUSE_FLAG) && (chunkHeader->size < size+sizeof(heap_header)))
    chunkHeader = (heap_header *)(((void *)(chunkHeader)+sizeof(heap_header)) + chunkHeader->size);
chunkHeader->size = size;
chunkHeader->flags = INUSE_FLAG;
return (char *)chunkHeader+sizeof(heap_header);
```

### Bug #3: Pointer Truncation in free

**Location:** `stdlib.c:577-578`

**Original Code:**
```c
void cgc_free(void *ptr) {
    heap_header *chunkHeader;
    heap_block_header *blockHead;

    chunkHeader = (heap_header*)(((char*)ptr)-sizeof(heap_header));
    chunkHeader->flags = FREE_FLAG;
    blockHead = (heap_block_header *)((int)&ptr & 0xfffff000);  // BUG!
    blockHead->remaining_size+=chunkHeader->size;
    return;
}
```

**Problems:**
1. Used `&ptr` (address of the local parameter variable on stack) instead of `ptr` (the heap address to free)
2. Cast to `int` (32-bit) which truncates 64-bit pointers
3. Incorrect accounting: should add back both data size AND header size

Example failure:
- `ptr = 0x4114d020` (heap address)
- `&ptr = 0x7ffd2f48c9d8` (stack address)
- `(int)&ptr = 0x2f48c9d8` (truncated)
- `(int)&ptr & 0xfffff000 = 0x2f48c000` (wrong block!)
- Accessing this wrong address → SIGSEGV

**Fix:**
```c
void cgc_free(void *ptr) {
    heap_header *chunkHeader;
    heap_block_header *blockHead;

    chunkHeader = (heap_header*)(((char*)ptr)-sizeof(heap_header));
    chunkHeader->flags = FREE_FLAG;
    blockHead = (heap_block_header *)((cgc_size_t)ptr & ~(cgc_size_t)0xfff);
    blockHead->remaining_size+=chunkHeader->size+sizeof(heap_header);
    return;
}
```

Changes:
- Use `ptr` not `&ptr`
- Cast to `cgc_size_t` (architecture-independent: 4 bytes on 32-bit, 8 bytes on 64-bit)
- Use `~(cgc_size_t)0xfff` for proper masking on both architectures
- Add back `size+sizeof(heap_header)` to match malloc accounting

## Testing

### Before Fix (64-bit):
```
# GEN_00000_00000.xml
sig: 11
not ok 1 - recv failed.  No data returned.
polls passed: 0
polls failed: 1
```

### After Fix (64-bit):
```
# GEN_00000_00000.xml
ok 1-30 - all tests passed
polls passed: 1
polls failed: 0

# Multiple tests (GEN_00000_00000-00003.xml)
total tests passed: 199
total tests failed: 0
polls passed: 3
polls failed: 0
```

### 32-bit Compatibility:
```
# GEN_00000_00000-00003.xml (32-bit build)
total tests passed: 199
total tests failed: 0
polls passed: 3
polls failed: 0
```

The fixes are architecture-agnostic and work correctly on both 32-bit and 64-bit builds.

## Files Modified

- `challenges/Diary_Parser/lib/stdlib.c`
  - Fixed `cgc_malloc()` heap accounting (line 609, 612)
  - Fixed new block allocation and initialization (lines 598-619)
  - Fixed `cgc_free()` pointer handling and accounting (lines 577-578)

## Key Takeaways

1. **Structure size changes:** Always account for structure size differences between 32-bit and 64-bit (alignment, padding)
2. **Pointer arithmetic:** Never cast pointers to `int` on 64-bit; use `cgc_size_t` or `uintptr_t`
3. **Address vs address-of:** Be careful with `ptr` vs `&ptr` - local variable addresses are on the stack, not the heap
4. **Accounting consistency:** If malloc subtracts `size+header`, free must add `size+header`
5. **Block initialization:** Always initialize allocated memory blocks to prevent garbage data from being interpreted as valid structures

## Related Issues

This is similar to malloc issues found in other challenges:
- KKVS: Fixed with `HEADER_PADDING` conditional on `__x86_64__`
- Other challenges with custom allocators need similar scrutiny for 64-bit compatibility
