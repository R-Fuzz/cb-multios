# CableGrindLlama 64-bit Debugging Experience

## Problem Summary

**Challenge:** CableGrindLlama
**Symptom:** Test GEN_00000_00060.xml fails at test 237/412 on 64-bit, passes all 412 tests on 32-bit
**Error:** Exit code 66 (heap cookie failure)
**Root Cause:** Hardcoded pointer size assumption in memory allocation

## Debugging Technique: Hardware Watchpoints

### Key Lesson: Use Hardware Watchpoints with Saved Addresses

The breakthrough came from using GDB hardware watchpoints to catch the exact moment of memory corruption.

#### Initial Failed Approach
```gdb
# This FAILS - watchpoint gets deleted when function returns
break cgc_insert
commands
  watch *(uint32_t*)node  # node is a local variable!
end
```

**Problem:** GDB deletes watchpoints when the variable goes out of scope.

#### Correct Approach
```gdb
# This WORKS - save address to GDB variable, watch that
set $insert_count = 0
set $watched_addr = 0

break cgc_insert
commands
  silent
  set $insert_count = $insert_count + 1
  if $insert_count == 201
    set $watched_addr = (uint64_t)node  # Save to GDB variable
    watch *(uint32_t*)$watched_addr     # Watch the saved address
    commands
      printf "Cookie modified at %p!\n", $watched_addr
      printf "New value: 0x%08x\n", *(uint32_t*)$watched_addr
      backtrace 10
      continue
    end
  end
  continue
end
```

**Key Points:**
1. Save the address to a GDB variable (`$watched_addr`)
2. Use the GDB variable in the watchpoint expression
3. The watchpoint persists after the function returns
4. Captures ALL modifications to that memory location

### What the Watchpoint Revealed

```
*** COOKIE MODIFIED at address 0x41d76dd0! ***
Insert count: 201
New value: 0xdf0571bd  <-- Correct initial value
Backtrace:
#0  cgc_insert (...) at libc.c:388

*** COOKIE MODIFIED at address 0x41d76dd0! ***
Insert count: 202
New value: 0xdf057156  <-- Being corrupted byte-by-byte
Backtrace:
#0  cgc_memcpy (dst=0x41d76c50, src=0x4166277f, n=387) at libc.c:319
#1  cgc_dupe_next (f=0x41661018) at libdupe.c:67

*** COOKIE MODIFIED at address 0x41d76dd0! ***
New value: 0xdf05d256  <-- Progressive corruption
#0  cgc_memcpy (dst=0x41d76c50, src=0x4166277f, n=387) at libc.c:319

*** COOKIE MODIFIED at address 0x41d76dd0! ***
New value: 0xdf93d256  <-- Final corrupted value
#0  cgc_memcpy (dst=0x41d76c50, src=0x4166277f, n=387) at libc.c:319
```

**Critical Evidence:**
- Chunk header at: `0x41d76dd0`
- memcpy destination: `0x41d76c50`
- Distance: `0x41d76dd0 - 0x41d76c50 = 0x180` (384 bytes)
- memcpy size: **387 bytes** (overflows by 3 bytes into the header!)

## Root Cause: Hardcoded Pointer Size

### The Bug (libdupe.c:49)

```c
typedef struct dupepkt {
    dupefile_t *parent;    // 4 bytes on 32-bit, 8 bytes on 64-bit!
    dupepkt_hdr_t hdr;     // 8 bytes
    uint8_t payload[0];    // flexible array
} dupepkt_t;

// WRONG: Assumes 4-byte pointers
pkt = cgc_malloc(sizeof(dupepkt_hdr_t)+4+f->framelen);
```

### The Fix

```c
// CORRECT: Uses actual struct size (portable)
pkt = cgc_malloc(sizeof(dupepkt_t)+f->framelen);
```

### Why It Failed on 64-bit

| Architecture | `sizeof(dupefile_t*)` | `sizeof(dupepkt_hdr_t)` | Hardcoded `+4` | Total Allocated | Actual Needed | Deficit |
|--------------|----------------------|-------------------------|----------------|-----------------|---------------|---------|
| 32-bit       | 4 bytes              | 8 bytes                 | 4 bytes        | 16 bytes        | 16 bytes      | 0 ✅    |
| 64-bit       | 8 bytes              | 8 bytes                 | 4 bytes        | 16 bytes        | 20 bytes      | -4 ❌   |

When memcpy wrote `f->framelen` bytes to `pkt->payload`, it overflowed by 4 bytes, corrupting the next heap chunk's metadata.

## Common Pitfalls to Avoid

### ❌ Don't Hardcode Pointer Sizes
```c
// WRONG
malloc(sizeof(header) + 4 + data_size);           // Assumes 32-bit
malloc(sizeof(header) + sizeof(void*) + ...);     // Better but still fragile

// CORRECT
malloc(sizeof(struct_name) + data_size);          // Always use sizeof(struct)
```

### ❌ Don't Trust Symptoms
We initially focused on:
- Struct alignment issues (packed vs unpacked)
- Heap chunk size mismatches
- Size alignment requirements

All were **red herrings**! The real bug was a simple 4-byte under-allocation.

### ✅ Do Use Watchpoints for Corruption
When debugging memory corruption:
1. Use `watch -l` (watch location, not expression)
2. Save addresses to GDB variables (`set $addr = (uint64_t)ptr`)
3. Set watchpoints on the saved variables
4. Let the program run and catch WHEN and WHERE corruption happens

### ✅ Do Check Arithmetic Around Pointers
Look for:
- `+4`, `+8` magic numbers near pointer operations
- `sizeof(void*)` assumptions
- Struct size calculations with hardcoded values

## Testing Results

### Only libdupe.c Fix (All Alignment Changes Reverted)
- **64-bit:** ✅ 412/412 tests passed
- **32-bit:** ✅ 412/412 tests passed

### Unnecessary Changes (Reverted)
1. `__attribute__((packed))` on heap_chunk struct - NOT needed
2. Size alignment in malloc - NOT needed
3. `cgc_curleft` alignment - NOT needed

## Key Takeaways

1. **Hardware watchpoints are essential** for finding memory corruption bugs
   - Save addresses to GDB variables to persist after function returns
   - Watch the exact location being corrupted

2. **Check for hardcoded pointer sizes** when porting to 64-bit
   - Search for: `+4`, `+8`, `sizeof(int)` near pointer math
   - Use `sizeof(struct)` instead of manual size calculations

3. **Don't trust your first hypothesis**
   - Symptoms often mislead (alignment looked like the problem)
   - Use watchpoints to find the actual write that corrupts memory

4. **The simplest fix is often the right one**
   - One line change in libdupe.c fixed everything
   - Complex alignment fixes were unnecessary

## GDB Script for Future Reference

```gdb
# debug_watch_corruption.gdb
set pagination off
set logging file /tmp/gdb_corruption.txt
set logging on
set logging overwrite on

# Track insert operations
set $insert_count = 0
set $watched_addr = 0

break cgc_insert
commands
  silent
  set $insert_count = $insert_count + 1
  # Set watchpoint on the chunk that will fail
  if $insert_count == 201
    set $watched_addr = (uint64_t)node
    watch *(uint32_t*)$watched_addr
    commands
      silent
      printf "\n*** COOKIE MODIFIED at %p! ***\n", $watched_addr
      printf "Insert count: %d\n", $insert_count
      printf "New value: 0x%08x\n", *(uint32_t*)$watched_addr
      backtrace 10
      printf "\n"
      continue
    end
  end
  continue
end

continue
```

## Command to Run

```bash
source venv/bin/activate
python tools/cb-replay-gdb.py \
  --cbs build64/challenges/CableGrindLlama/CableGrindLlama \
  --xml polls/CableGrindLlama/poller/for-release/GEN_00000_00060.xml \
  --debug --gdb_script debug_watch_corruption.gdb --timeout 60
```

Check output in: `/tmp/gdb_corruption.txt`
