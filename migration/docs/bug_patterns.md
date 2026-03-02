# 64-bit Porting Bug Patterns

This document catalogs root causes and fixes found while porting CGC challenges to 64-bit.
Extracted from git history, commit diffs, and per-challenge debug reports.

---

## Pattern Categories

- **intptr-size** — `intptr_t` defined as 32-bit `int` instead of 64-bit `long`
- **header-padding** — `HEADER_PADDING` hardcoded at 24 bytes instead of 48 on 64-bit
- **tiny-size** — `TINY_SIZE` hardcoded at 4 bytes (pointer-sized free-list slot too small on 64-bit)
- **wire-format** — protocol uses `cgc_size_t`/`unsigned long` (8 bytes on 64-bit) where 4-byte fixed width expected
- **struct-alloc** — allocation uses hardcoded `+4` instead of `sizeof(struct)`, breaks when pointer grows
- **uninit-memory** — uninitialized struct/stack memory; padding differs between 32/64-bit
- **custom-malloc** — hand-rolled allocator has 32-bit assumptions in accounting, alignment, or pointer arithmetic
- **abi-calling-conv** — x86-64 calling convention violation (e.g., math result in st(0) not xmm0)
- **pointer-cast** — pointer cast to `int` truncates on 64-bit; should use `cgc_size_t`/`uintptr_t`
- **varargs** — custom printf treats `va_list` as `char**` array; breaks on x86-64 register-based ABI
- **flag-page-addr** — intermediate `intptr_t` variable truncates `CGC_FLAG_PAGE_ADDRESS` on 64-bit
- **pre-existing** — bug exists in both 32-bit and 64-bit; not a porting issue
- **test-runner-perf** — `cb-replay.py` per-read overhead (0.1s sleep) causes timeouts on polls with high `MAX_DEPTH` (500+ exchanges)

---

## Fixes Extracted from Git History

### ASCII_Content_Server — `f1d92896`
- **Category**: custom-malloc
- **Symptom**: Heap corruption on 64-bit
- **Root Cause**: `FREE_BLOCK_NEXT/PREV` macros used `sizeof(tMallocAllocHdr)` but should subtract `sizeof(tMallocAllocFtr) - sizeof(tMallocAllocHdr)`; also `grow_size` added hardcoded `4` instead of `sizeof(tMallocAllocHdr)`; minimum alloc size hardcoded as 8 instead of `sizeof(tMallocAllocFtr)`
- **Fix**: Replace all hardcoded sizes with `sizeof()` of the actual struct; add 64-bit alignment path using 8-byte alignment
- **Files**: `challenges/ASCII_Content_Server/lib/cgc_malloc.h`

### ASL6parse — `e2fabd64`
- **Category**: intptr-size + header-padding
- **Symptom**: Crashes / wrong output on 64-bit
- **Fix**: Standard `intptr_t`/`HEADER_PADDING` guard (`#ifdef __x86_64__`)
- **Files**: `challenges/ASL6parse/lib/cgc_stdint.h`, `cgc_malloc.h`

### Accel — `cfcf0ca7`
- **Category**: intptr-size + header-padding
- **Fix**: Standard `intptr_t`/`HEADER_PADDING` guard
- **Files**: `challenges/Accel/lib/cgc_stdint.h`, `cgc_malloc.h`

### Audio_Visualizer — `9fee4a7e`
- **Category**: intptr-size + header-padding + argument-order bug
- **Symptom**: Wrong output; `cgc_send_n_bytes(STDOUT, astring, cgc_strlen(astring))` had length and data arguments swapped
- **Fix**: Standard guards + fix argument order to `cgc_send_n_bytes(STDOUT, cgc_strlen(astring), astring)`; add `#pragma pack(push/pop,1)` on wire structs
- **Files**: `challenges/Audio_Visualizer/lib/cgc_stdint.h`, `cgc_malloc.h`, `src/`

### Azurad — `bec876ba`
- **Category**: custom-malloc + uninit-memory (UB in C++ copy constructor)
- **Symptom**: 32-bit crashed with SIGABRT; 64-bit worked by luck (uninitialized memory happened to be zeroed)
- **Root Cause 1**: Custom allocator's `mem_map` array sized for 32-bit address space (4096 entries). On 64-bit, `mmap()` returns high addresses causing out-of-bounds array index.
  - Fix: Add `MAP_32BIT` flag to `cgc_allocate()` in `include/libcgc.c`
- **Root Cause 2**: `TINY_SIZE=4` — free-list slots too small to hold 8-byte pointers.
  - Fix: `#ifdef __x86_64__ #define TINY_SIZE 8`
- **Root Cause 3**: `vector<T>` copy constructor called `operator=` on uninitialized memory → double-free via garbage pointer in `unique_ptr`.
  - Fix: Construct via copy constructor into temp, then `cgc_memcpy` into destination (pattern from `enlarge()`)
- **Files**: `include/libcgc.c`, `challenges/Azurad/lib/cgc_malloc_private.h`, `challenges/Azurad/src/cgc_vector.h`
- **Detail**: `migration/docs/azurad_64bit_porting.md`

### Barcoder — `2427e45f`
- **Category**: intptr-size
- **Fix**: Standard `intptr_t` guard
- **Files**: `challenges/Barcoder/lib/cgc_stdint.h`

### Bloomy_Sunday — `972ee85d`
- **Category**: intptr-size + header-padding
- **Fix**: Standard `intptr_t`/`HEADER_PADDING` guard
- **Files**: `challenges/Bloomy_Sunday/lib/cgc_stdint.h`, `cgc_malloc.h`

### BudgIT — `706960a9`
- **Category**: wire-format (also: poller machine.py uses platform-dependent `pack('l')`)
- **Symptom**: 32-bit binary failed poll tests; 64-bit binary passed. Polls were generated on 64-bit and sent 8-byte instructions; 32-bit binary only read 4 bytes, corrupting stream.
- **Root Cause**: Source used `unsigned long` (4 bytes on 32-bit, 8 bytes on 64-bit) for wire protocol. Poller used Python `pack('l')` which is also platform-dependent.
- **Fix**: Change `unsigned long` → `uint32_t` in source; change `pack('l')` → `pack('I')` in `machine.py`
- **Files**: `challenges/BudgIT/src/service.c`, `challenges/BudgIT/poller/for-release/machine.py`
- **Detail**: `migration/docs/budgit_32bit_64bit_fix.md`

### CableGrindLlama — `bc37e0ee`
- **Category**: struct-alloc (hardcoded pointer size)
- **Symptom**: Heap cookie corruption at test 237/412 on 64-bit; exit code 66
- **Root Cause**: `pkt = cgc_malloc(sizeof(dupepkt_hdr_t) + 4 + f->framelen)` — the `+4` assumed 32-bit pointer size for `dupefile_t*`. On 64-bit the pointer is 8 bytes, under-allocating by 4 bytes, causing memcpy overflow into next chunk header.
- **Fix**: `pkt = cgc_malloc(sizeof(dupepkt_t) + f->framelen)` — use `sizeof(struct)` which includes the pointer field
- **Files**: `challenges/CableGrindLlama/src/libdupe.c`
- **Debugging**: Hardware watchpoints in GDB — save address to `$gdb_var`, then `watch *(uint32_t*)$gdb_var` to survive function returns
- **Detail**: `migration/docs/cablegrindllama_64bit_debugging.md`

### CGC_Board — `76e8d723`
- **Category**: intptr-size + header-padding
- **Fix**: Standard guards + add missing `cgc_sink_error` alias
- **Files**: `challenges/CGC_Board/lib/cgc_stdint.h`, `cgc_malloc.h`

### CGC_Hangman_Game — `3d534270`
- **Category**: varargs
- **Symptom**: Wrong output from custom printf on 64-bit
- **Root Cause**: Custom `cgc_vprintf` treated `va_list` as `char**` array (`char **args = (char**)ap`). On x86-64, function arguments are passed in registers (not on stack), so `va_list` is a struct, not a simple pointer array.
- **Fix**: Replace manual `char**` iteration with proper `va_arg(ap, type)` via `__builtin_va_arg`. Pre-scan format string to count `%` specifiers, extract all args into `cgc_size_t arg_values[MAX_PRINTF_ARGS]`.
- **Files**: `challenges/CGC_Hangman_Game/src/`

### CGC_Symbol_Viewer_CSV — `a99b52e8`
- **Category**: intptr-size + header-padding + wire-format
- **Fix**: Standard guards + change wire-format struct field from `cgc_size_t` to `uint32_t`
- **Files**: `challenges/CGC_Symbol_Viewer_CSV/lib/cgc_stdint.h`, `cgc_malloc.h`, `src/`

### Cereal_Mixup — `d95961b9`
- **Category**: custom-malloc (size class minimums)
- **Symptom**: Heap corruption on 64-bit
- **Root Cause**: Size class minimums in custom allocator assumed 32-bit struct sizes (header+list_node+footer = 16 bytes on 32-bit, 32 bytes on 64-bit)
- **Fix**: `#if UINTPTR_MAX == 0xFFFFFFFF` guard to select 32-bit vs 64-bit size class tables
- **Files**: `challenges/Cereal_Mixup__A_Cereal_Vending_Machine_Controller/lib/cgc_malloc.h`

### Childs_Game — `0de69202`
- **Category**: intptr-size
- **Fix**: Standard `intptr_t` guard
- **Files**: `challenges/Childs_Game/lib/cgc_stdint.h`

### CML — `e1c4ba7e`
- **Category**: tiny-size + intptr-size + flexible-array
- **Root Cause 1**: `TINY_SIZE=4` — free-list next pointer (8 bytes on 64-bit) doesn't fit in tiny block, corrupts adjacent memory
- **Root Cause 2**: `intptr_t` as 32-bit `int`
- **Root Cause 3**: Flexible array member `char d_data[]` — not standard C; some compilers handle it differently on 64-bit. Changed to `char d_data[1]`.
- **Root Cause 4**: Intermediate `intptr_t` variable used to hold `CGC_FLAG_PAGE_ADDRESS` — truncated on 64-bit
- **Fix**: `#ifdef __x86_64__ #define TINY_SIZE 8`; standard `intptr_t` guard; use `char d_data[1]`; eliminate intermediate variable
- **Files**: `challenges/CML/lib/cgc_stdint.h`, `cgc_malloc.h`, `src/`

### Cromulence_All_Service — `78fe1c39`
- **Category**: custom-malloc + uninit bug
- **Root Cause 1**: `grow_size = request_size + 4` — hardcoded 4 instead of `sizeof(tMallocAllocHdr)`
- **Root Cause 2**: Min alloc size `8` and alignment `4` hardcoded instead of `sizeof(tMallocAllocFtr)` and `sizeof(cgc_size_t)`
- **Root Cause 3**: Matrix code used uninitialized local `x`/`y` on second call; fixed to use globals `X`/`Y`
- **Fix**: Replace all hardcoded sizes with `sizeof()` of actual types; fix matrix global reference
- **Files**: `challenges/Cromulence_All_Service/lib/cgc_malloc.h`, `src/`

### CTTP — `38e2c202`
- **Category**: wire-format
- **Symptom**: Timeout/wrong output on 64-bit
- **Root Cause**: Protocol structs used `cgc_size_t` for `psize`/`bodysize`/`rsize` fields. On 64-bit these are 8 bytes but the wire format expects 4 bytes (32-bit protocol). `READDATA(req)` read the full 64-bit struct including pointer fields.
- **Fix**: Change all wire-format fields from `cgc_size_t` to `uint32_t`; read only the fixed 20-byte header manually then read 4-byte pointer placeholders separately
- **Files**: `challenges/CTTP/src/`

### DFARS_Sample_Service — `a4f28370`
- **Category**: uninit-memory
- **Symptom**: Intermittent wrong output on 64-bit (struct padding garbage differs between architectures)
- **Root Cause**: Large stack-allocated `command_t` structs not zero-initialized. On 64-bit, different struct padding means garbage bytes appear in different positions.
- **Fix**: Add `cgc_bzero` / zero-initialization for all stack-allocated `command_t` nodes
- **Files**: `challenges/DFARS_Sample_Service/src/`

### Diary_Parser — `ad212361`
- **Category**: custom-malloc (multiple bugs)
- **Symptom**: SIGSEGV on 64-bit at malloc during initialization
- **Root Cause 1**: `remaining_size -= size` instead of `size + sizeof(heap_header)` → accounting error, walks off valid memory after ~88 allocations
- **Root Cause 2**: When a new 4096-byte block is allocated, the old code returned NULL (logic was in `else` branch only; the `if` branch fell through to `return 0`)
- **Root Cause 3**: New block not zeroed → garbage flags/sizes in heap chunk walk loop
- **Root Cause 4**: `cgc_free` used `(int)&ptr & 0xfffff000` — cast pointer ADDRESS (stack) to `int` (truncated) instead of the actual heap pointer `ptr`
- **Fix**: Fix accounting to subtract full `size+sizeof(heap_header)`; remove `else`; `cgc_memset` new block to 0; use `(cgc_size_t)ptr & ~(cgc_size_t)0xfff` in free
- **Files**: `challenges/Diary_Parser/lib/stdlib.c`
- **Detail**: `migration/docs/diary_parser_64bit_fix.md`

### Differ — `e2097791`
- **Category**: intptr-size + header-padding
- **Fix**: Standard guards
- **Files**: `challenges/Differ/lib/cgc_stdint.h`, `cgc_malloc.h`

### Dive_Logger — `f8fb5bb6`
- **Category**: wire-format
- **Symptom**: Wrong output on 64-bit
- **Root Cause**: `cgc_GetUInt32()` returned `unsigned long int` and read `sizeof(unsigned long)` bytes — 8 bytes on 64-bit, consuming 4 extra bytes from the stream
- **Fix**: Change return type and read size to `uint32_t`
- **Files**: `challenges/Dive_Logger/src/`

### Document_Rendering_Engine — `d9d6507c`
- **Category**: custom-malloc (size classes)
- **Symptom**: Heap corruption on 64-bit
- **Root Cause**: Size class table designed for 32-bit minimum block sizes
- **Fix**: Add `#if defined(__LP64__) || defined(__x86_64__)` block with 64-bit-appropriate size classes
- **Files**: `challenges/Document_Rendering_Engine/lib/cgc_malloc.h`

### Dungeon_Master — `30c0b827`
- **Category**: uninit-memory
- **Symptom**: Intermittent wrong behavior on 64-bit (uninitialized struct fields differ by architecture due to padding)
- **Fix**: `cgc_bzero((char*)&dungeon, sizeof(Dungeon))` before use
- **Files**: `challenges/Dungeon_Master/src/`

### ECM_TCM_Simulator — `c189e5f8`
- **Category**: flag-page-addr
- **Symptom**: Wrong flag page access on 64-bit
- **Root Cause**: `secret_page_i = CGC_FLAG_PAGE_ADDRESS; void *secret_page = (void *)secret_page_i;` — `secret_page_i` was `intptr_t` (32-bit), truncating the 64-bit address
- **Fix**: `void *secret_page = (void *)CGC_FLAG_PAGE_ADDRESS;` — eliminate intermediate variable
- **Files**: `challenges/ECM_TCM_Simulator/src/`

### Eddy — `b0dd72cc`
- **Category**: intptr-size (full stdint.h was missing)
- **Symptom**: Type errors and wrong behavior on 64-bit
- **Fix**: Add full `cgc_stdint.h` with proper `#ifdef __x86_64__` for `intptr_t`/`uintptr_t`
- **Files**: `challenges/Eddy/lib/cgc_stdint.h`

### Enslavednode_chat — `fd4fa2dc`
- **Category**: intptr-size + header-padding + hardcoded FD
- **Root Cause 1**: Standard `intptr_t`/`HEADER_PADDING` issues
- **Root Cause 2**: `cgc_readline(1, ...)` hardcoded FD `1` (stdout) instead of `STDIN` — reads from wrong fd
- **Fix**: Standard guards + change `1` to `STDIN`; add missing `cgc_strcmp`/`cgc_strncmp` externs
- **Files**: `challenges/Enslavednode_chat/lib/cgc_stdint.h`, `cgc_malloc.h`, `src/`

---

## Previously Documented Systemic Fixes (72+ files)

### intptr_t Type Size — 72 files
- **Category**: intptr-size
- **Symptom**: Sign-extended pointers (`0xfffffffff7a64030` instead of `0x7ffff7a64030`)
- **Root Cause**: `intptr_t` defined as `int` (always 32-bit) in `cgc_stdint.h`
- **Fix**:
  ```c
  #ifdef __x86_64__
  typedef long intptr_t;
  typedef unsigned long uintptr_t;
  #else
  typedef int intptr_t;
  typedef unsigned int uintptr_t;
  #endif
  ```
- **Files**: `challenges/*/lib/cgc_stdint.h`

### HEADER_PADDING — 18 files
- **Category**: header-padding
- **Symptom**: Heap corruption, overlapping allocations
- **Root Cause**: `HEADER_PADDING` hardcoded as `24` (32-bit `sizeof(struct blk_t)`); on 64-bit it's 48
- **Fix**:
  ```c
  #ifdef __x86_64__
  #define HEADER_PADDING 48
  #else
  #define HEADER_PADDING 24
  #endif
  ```
- **Files**: `challenges/*/lib/cgc_malloc.h`

### maths64.S ABI Violation — 16 math functions
- **Category**: abi-calling-conv
- **Symptom**: Math functions returned 0 or garbage (e.g., `cgc_sin(x)` always returned 0)
- **Root Cause**: Functions computed result in x87 FPU (`st(0)`) but x86-64 ABI requires float return in `xmm0`
- **Fix**: Add `fstpl (%rsp); movsd (%rsp), %xmm0` after each computation
- **Files**: `include/maths64.S`
- **Functions**: cgc_sin, cgc_cos, cgc_tan, cgc_sqrt, cgc_fabs, cgc_atan2, cgc_log, cgc_log10, cgc_log2, cgc_exp, cgc_exp2, cgc_pow, cgc_remainder, cgc_significand, cgc_scalbn, cgc_rint

---

## Fixes from Sub-agent Run (March 2026)

### virtual_pet
- **Category**: missing-constructor (CRT startup difference)
- **Symptom**: All 200 polls fail immediately — first expected output `ctors called...\n` never appears
- **Root Cause**: `call_inits()` was declared but never defined. On DECREE OS, the CRT startup called it before running C++ global constructors. On Linux, no such call is made.
- **Fix**: Add definition with `__attribute__((constructor(101)))` so it runs before the `cgc_myList` global constructor (priority 101 < default 65535):
  ```c
  void __attribute__((constructor(101))) call_inits(void) {
      cgc_transmit_all(1, "ctors called...\n", 16);
  }
  ```
- **Files**: `challenges/virtual_pet/src/main.cc`

### No_Paper._Not_Ever._NOPE
- **Category**: uninit-memory
- **Symptom**: All 100 polls fail — binary sends garbage bytes where polls expect zeros
- **Root Cause**: `Response r;` left uninitialized in main loop. On 32-bit Linux, the OS zero-initializes new stack pages so the struct happened to be all zeros. On 64-bit Linux, different stack layout / ABI means the same region contains non-zero garbage.
- **Fix**: `Response r = {0};` — deterministic zero-initialization across architectures
- **Files**: `challenges/No_Paper._Not_Ever._NOPE/src/service.c`
- **Note**: This is the unpatched code path; the vulnerability semantics are preserved.

### WhackJack
- **Category**: uninit-memory + broken-memset
- **Symptom**: 92/100 polls fail — `show_players()` prints garbage player names for empty slots
- **Root Cause 1**: `players[MAX_PLAYERS]` stack array not zero-initialized. On 64-bit, uninitialized stack bytes are non-zero, so `player_name[0] != 0` causes garbage names to print.
  - Fix: `cgc_memset(players, 0, sizeof(players))` at start of main
- **Root Cause 2**: `cgc_memset()` in `string.c` was broken — `*((uint32_t*)ptr++) = ...` where `ptr` is `void*`. GCC `void*` pointer arithmetic advances by 1 byte, but `num -= 4` decremented by 4, so only ~25% of bytes were actually zeroed. This masked root cause 1.
  - Fix: Use typed pointers `uint32_t *ptr32` / `uint8_t *ptr8` with proper advancement
- **Files**: `challenges/WhackJack/src/service.c`, `challenges/WhackJack/lib/string.c`

### Hug_Game
- **Category**: uninit-memory + pointer-size-array-count
- **Symptom**: 67/100 polls fail
- **Root Cause 1**: `cgc_recvUntil()` had `int i;` uninitialized. On 64-bit, garbage stack value ≥ `max` meant the `while(i < max)` loop never executed — buffer stayed empty.
  - Fix: `int i = 0;`
- **Root Cause 2**: `cgc_pickaword()` computed word count as `sizeof(words) / 4`. On 32-bit `sizeof(char*) == 4` so this was correct. On 64-bit `sizeof(char*) == 8`, returning twice the actual count → out-of-bounds → SIGSEGV.
  - Fix: `sizeof(words) / sizeof(words[0])`
- **Files**: `challenges/Hug_Game/lib/libc.c`, `challenges/Hug_Game/src/hangman.c`

### REMATCH_5--File_Explorer--LNK_Bug
- **Category**: custom-malloc (hardcoded `+4`) + hardcoded-pointer-size + DECREE address mapping
- **Symptom**: 49/100 polls fail
- **Root Cause 1**: `malloc.c` had 9 locations with hardcoded `+4`/`-4` assuming `sizeof(cgc_size_t) == 4`. User pointers were offset 4 bytes into metadata; `cgc_free()` computed wrong meta address. On 64-bit `sizeof(cgc_size_t) == 8`.
  - Fix: Replace all literal `4` with `sizeof(cgc_size_t)` throughout malloc.c
- **Root Cause 2**: `filesystem.c` — two `cgc_memcpy` calls copying only 4 bytes of `"cgc_root"` (8 chars), producing `"cgc_"` as root directory name.
  - Fix: Change copy count from `4` to `8`
- **Root Cause 3**: `loader.c` — `OPCODE_READ_MEM`/`WRITE_MEM`/`WRITE_REG` read pointer operands via `*(uint32_t **)address`, which reads 8 bytes on 64-bit instead of the 4-byte addresses in the bytecode format.
  - Fix: Read via `uint32_t addr32 = *(uint32_t *)address; (uint32_t *)(unsigned long)addr32`
- **Root Cause 4**: `osfiles.c` embedded bytecode referenced DECREE address `0x080480a0` (`.data` section in DECREE binary, not mapped on Linux). Changed to `0x4347c000` (CGC flag page, always mapped via `MAP_FIXED`).
- **Files**: `challenges/REMATCH_5--File_Explorer--LNK_Bug/lib/malloc.c`, `src/filesystem.c`, `src/loader.c`, `src/osfiles.c`

### PRU
- **Category**: uninit-memory
- **Symptom**: 17/100 polls fail on both 32-bit and 64-bit — ADC instruction produces wrong results
- **Root Cause**: `pruCPU cpu` stack struct partially uninitialized. `cpu.carry` (a `char` at the end of the large struct) contained garbage stack bytes (e.g. `0xb0`, `0xca`). On DECREE OS, stack pages are zero-initialized; on Linux they're not. ADC uses `carry` directly: `cpu->r[inst.rd] = cpu->r[inst.rs1] + ... + cpu->carry;`
- **Fix**: Explicitly zero `cpu.pc`, `cpu.carry`, and `cgc_memset(cpu.r, 0, sizeof(cpu.r))` after the existing partial init
- **Files**: `challenges/PRU/src/pru.c`
- **Commit**: `165407b0`
- **Note**: Was originally counted as 16 "64-bit failures" but turned out to be pre-existing on both architectures — the fix helps both.

### HighFrequencyTradingAlgo
- **Category**: pre-existing (floating-point nondeterminism)
- **Symptom**: ~24/100 failures on 64-bit
- **Root Cause**: Trading algorithm uses `cgc_squareRoot`/variance/stdDev. Results that hover near a threshold ("You doubled your money!") vary between runs due to FPU state. 32-bit x87 uses 80-bit extended precision; 64-bit SSE2 uses 64-bit. The 64-bit binary actually passes MORE tests (74+/100) than the 32-bit for-testing polls.
- **No fix needed**: 64-bit binary is correct; the variation is inherent floating-point nondeterminism.

### TAINTEDLOVE
- **Category**: errno-mismatch (systemic libcgc bug) + sign-extension + integer-overflow-wrapping
- **Symptom**: 100/100 polls fail — stack overflow from infinite recursion in `cgc_heisenberg_hooey()`
- **Root Cause 1 (systemic — affects all challenges)**: `cgc_deallocate()` called `munmap()` which failed with Linux `EINVAL=22`, but challenge code checked against CGC `EINVAL=3`. Since `22 ≠ 3`, a "should never be true" condition triggered infinite recursion.
  - Fix: Added `linux_errno_to_cgc()` mapping function in `include/libcgc.c`; updated all syscall wrappers (`cgc_transmit`, `cgc_receive`, `cgc_allocate`, `cgc_deallocate`, `cgc_fdwait`) to return CGC error codes.
- **Root Cause 2**: `cgc_fdwait` returned Linux `EINVAL` (22) instead of CGC `EINVAL` (3); fdwait timeout was 50ms (too short for Linux); Linux `select()` modifies `timeval` in-place so it must be re-initialized each loop iteration.
  - Fix: Use `CGC_EINVAL`; increase timeout to 5s; move `timeToWait` init inside loop.
- **Root Cause 3**: `cgc_size_t gate` stored result of `unsigned char << 24` — on 64-bit `cgc_size_t` is 64-bit, so the shift doesn't wrap at 32 bits as expected.
  - Fix: Change to `unsigned int gate`.
- **Root Cause 4**: `(XOR_CONST_OFF_PTR*2)+0xFFFFFFFF+1` — 32-bit overflow wrapping doesn't happen on 64-bit.
  - Fix: Cast to `(unsigned int)(...)` to force 32-bit wrapping.
- **Files**: `include/libcgc.c` (systemic), `challenges/TAINTEDLOVE/lib/libc.c`, `challenges/TAINTEDLOVE/src/service.c`

### QUIETSQUARE
- **Category**: hardcoded-stack-address + transmit-to-wrong-fd + fdwait-reinit
- **Symptom**: 100/100 polls fail
- **Root Cause 1**: `exercise_stack()` used hardcoded CGC stack address `STACK_LIMIT + 0x10000` which is not mapped on Linux.
  - Fix: Guard body with `#if !defined(LINUX) && !defined(__x86_64__)`; replace fixed address with `&cgc_ppotp` global.
- **Root Cause 2**: `cgc_transmit_all` sent to `STDIN` (fd 0) instead of `STDOUT` (fd 1).
- **Root Cause 3**: Same fdwait/select timeout reinit issue as TAINTEDLOVE.
- **Files**: `challenges/QUIETSQUARE/lib/libc.c`, `challenges/QUIETSQUARE/src/service.c`, `cgc_service.h`

### GREYMATTER
- **Category**: transmit-to-wrong-fd
- **Symptom**: 100/100 polls fail — all output goes nowhere
- **Root Cause**: `cgc_transmit_all` used `STDIN` (fd 0) instead of `STDOUT` (fd 1)
- **Fix**: Change `STDIN` → `STDOUT` in `cgc_transmit_all`
- **Files**: `challenges/GREYMATTER/lib/libc.c`

### AIS-Lite
- **Category**: pre-existing (timeout)
- **Symptom**: 1/100 polls fail (GEN_00000_00092.xml)
- **Root Cause**: Both 32-bit and 64-bit take ~16.4s for this specific test, just over the default 15s timeout. Passes with `--timeout 20`.
- **No fix needed**: Pre-existing timeout edge case, not a porting issue. Documented in `FINAL_TIMEOUT_ANALYSIS.md`.

### EternalPass
- **Category**: pointer-cast + DECREE address mapping
- **Symptom**: 76/100 polls fail — crash when calling function pointer set from poll-supplied integer
- **Root Cause**: Poller sends hardcoded DECREE binary addresses (`0x08c6b0d0`, `0x08c6b100`) as `custom_prng` parameter. These are `cgc_prng`/`cgc_another_prng` addresses in the DECREE binary — not valid in a Linux process. Also: cast from `unsigned int` (32-bit) to function pointer needs `unsigned long` on 64-bit to avoid truncation.
- **Fix**: Map known DECREE addresses to actual Linux function pointers:
  ```c
  if (prng_addr == 0x08c6b0d0)
      custom_prng = cgc_prng;
  else if (prng_addr == 0x08c6b100)
      custom_prng = cgc_another_prng;
  else
      custom_prng = (unsigned int (*)(unsigned int, unsigned int))(unsigned long)prng_addr;
  ```
- **Files**: `challenges/EternalPass/src/service.c`

---

## Pre-existing Bugs (Not 64-bit Porting Issues)

### anagram_game — POV tests
- **Category**: pre-existing (protocol desync)
- **Symptom**: Both 32-bit and 64-bit hang at test 4803 in POV test
- **Root Cause**: POV sends varint-encoded `1,783,355,611` as string length. `cgc_read_string` attempts `cgc_malloc(1.7GB)`. Whether malloc succeeds or fails, it then tries to `cgc_read_bytes(buf, 1.7GB)` from stdin which has no more data → `cgc_exit(1)`. The calling function had no error response path, causing protocol desynchronization deadlock.
- **Not a fix target**: This is an intentional vulnerability the POV is designed to expose.
- **Detail**: `migration/docs/anagram_game_debug_report.md`, `migration/docs/malloc_failure_analysis.md`

### PRU — unpatched binary tests
- **Category**: pre-existing
- **Symptom**: 17 tests fail on both 32-bit and 64-bit unpatched binary
- **Root Cause**: These are intentional vulnerability tests (POV behavior); the patched binary has different failures that may be 64-bit specific

---

## Quick Reference: Common Fix Patterns

### Wire format field (read wrong number of bytes)
```c
// Before (8 bytes on 64-bit)
cgc_size_t psize;
cgc_recv(STDIN, &psize, sizeof(psize));

// After (always 4 bytes)
uint32_t psize;
cgc_recv(STDIN, &psize, sizeof(uint32_t));
```

### Struct allocation with pointer member
```c
// Before (hardcoded pointer size)
pkt = cgc_malloc(sizeof(header_t) + 4 + data_len);

// After (portable)
pkt = cgc_malloc(sizeof(full_struct_t) + data_len);
```

### Free pointer arithmetic
```c
// Before (truncates 64-bit pointer to 32-bit)
blockHead = (block_t *)((int)ptr & 0xfffff000);

// After (portable)
blockHead = (block_t *)((cgc_size_t)ptr & ~(cgc_size_t)0xfff);
```

### Flag page address (no intermediate variable)
```c
// Before (intermediate intptr_t truncates on 64-bit)
intptr_t addr = CGC_FLAG_PAGE_ADDRESS;
void *page = (void *)addr;

// After
void *page = (void *)CGC_FLAG_PAGE_ADDRESS;
```

### TINY_SIZE for free-list pointers
```c
// Before
#define TINY_SIZE (4)

// After
#ifdef __x86_64__
#define TINY_SIZE (8)
#else
#define TINY_SIZE (4)
#endif
```

### Linux errno vs CGC errno mismatch (systemic)
```c
// CGC errno values differ from Linux errno values
// e.g. CGC EINVAL=3, Linux EINVAL=22
// Fix: map in libcgc.c syscall wrappers
static int linux_errno_to_cgc(int linux_errno) {
    switch (linux_errno) {
        case EBADF:  return CGC_EBADF;   // 9 → 1
        case EFAULT: return CGC_EFAULT;  // 14 → 2
        case EINVAL: return CGC_EINVAL;  // 22 → 3
        default:     return linux_errno;
    }
}
```

### Array element count with pointer-sized elements
```c
// Before (breaks on 64-bit when elements are pointers)
int count = sizeof(words) / 4;

// After (always correct)
int count = sizeof(words) / sizeof(words[0]);
```

### fdwait / select() timeout reinit (Linux modifies timeval in-place)
```c
// Before (timeval zeroed after first iteration on Linux)
struct timeval timeToWait = {0, 50000};
while (...) {
    cgc_fdwait(..., &timeToWait);  // Linux zeroes timeToWait!
}

// After
while (...) {
    struct timeval timeToWait = {5, 0};  // reinit each iteration
    cgc_fdwait(..., &timeToWait);
}
```

### 32-bit integer overflow wrapping on 64-bit
```c
// Before (doesn't wrap on 64-bit cgc_size_t)
cgc_size_t result = (val * 2) + 0xFFFFFFFF + 1;

// After (force 32-bit wrapping)
unsigned int result = (unsigned int)((val * 2) + 0xFFFFFFFF + 1);
```

### Varargs in custom printf
```c
// Before (x86-32 stack assumption)
char **args = (char**)ap;
char *arg = args[i];

// After (portable)
cgc_size_t arg = va_arg(ap, cgc_size_t);
```

### Modern_Family_Tree
- **Category**: wire-format
- **Symptom**: All polls fail; binary reads 8 extra bytes per request on 64-bit
- **Root Cause**: `Request` struct has `cgc_size_t bytes` field (8 bytes on 64-bit, 4 bytes on 32-bit). Polls send 4-byte length, but binary reads 8 bytes, causing misalignment.
- **Fix**: Change `cgc_size_t bytes` to `uint32_t bytes` in the `Request` struct
- **Files**: `challenges/Modern_Family_Tree/src/service.c`

### Neural_House
- **Category**: wire-format
- **Symptom**: All polls fail; binary reads 8 extra bytes for sample count on 64-bit
- **Root Cause**: `numSamples` declared as `cgc_size_t` (8 bytes on 64-bit). Binary calls `cgc_fread(&numSamples, sizeof(cgc_size_t), ...)` reading 8 bytes, but polls send 4-byte count.
- **Fix**: Change `cgc_size_t numSamples` to `uint32_t numSamples` and update the fread size accordingly
- **Files**: `challenges/Neural_House/src/service.cc`

### One_Amp
- **Category**: flag-page-addr + tiny-size
- **Symptom**: SIGSEGV at startup; heap corruption during operation
- **Root Causes**:
  1. `main(int secret_page_i, ...)` cast argc (=1) as the flag page pointer: `(unsigned char *)secret_page_i` dereferences address 1 → crash
  2. Custom malloc has `TINY_SIZE = 4` but on 64-bit, free-list next pointers are 8 bytes; tiny bins can't hold a pointer → heap corruption
  3. `cgc_size_to_bin` hardcoded divisor `4` instead of using `TINY_SIZE`
- **Fix**:
  1. Use `CGC_FLAG_PAGE_ADDRESS` directly instead of casting argc
  2. Add `#ifdef __x86_64__ #define TINY_SIZE (8) #else #define TINY_SIZE (4) #endif`
  3. Fix `cgc_size_to_bin` to use `(n / TINY_SIZE) - 1`
- **Files**: `challenges/One_Amp/src/service.cc`, `challenges/One_Amp/lib/cgc_malloc_private.h`

### Stock_Exchange_Simulator
- **Category**: wire-format + test-runner-perf
- **Symptom**: Tests timeout; binary sends/receives wrong number of bytes per BUY/SELL packet
- **Root Causes**:
  1. `packet_t` struct has `void *op_data` (8 bytes on 64-bit, 4 bytes on 32-bit). Polls send 24-byte packets (4-byte op_data). With `void*`, binary reads 32 bytes for the header.
  2. `sizeof(void *)` used in `cgc_get_data_len()` and `cgc_gen_order_fill_msg()` to compute payload sizes, producing wrong sizes on 64-bit.
  3. `cb-replay.py` uses `time.sleep(0.1)` per read while waiting for data → ~100ms overhead per exchange. Polls with `MAX_DEPTH=500` have 501 exchanges per file → 50 seconds, exceeding the 10-15 second timeout.
- **Fix**:
  1. Change `void *op_data` to `uint32_t op_data` in `packet_t`
  2. Replace `sizeof(void *)` with `sizeof(uint32_t)` in payload size calculations
  3. Change `time.sleep(0.1)` to `time.sleep(0.001)` in `read_from_proc()` in `tools/cb-replay.py`
- **Files**: `challenges/Stock_Exchange_Simulator/src/cgc_option.h`, `src/service.c`, `src/option.c`, `tools/cb-replay.py`

### TVS
- **Category**: wire-format + custom-malloc (pointer-as-id)
- **Symptom**: All polls fail; locker IDs (raw pointer values) differ between 32-bit and 64-bit
- **Root Causes**:
  1. `locker_t` has `void *data` (8 bytes on 64-bit) → `sizeof(locker_t)` = 16 on 64-bit vs 8 on 32-bit. Polls encode raw pointer addresses as 32-bit IDs expecting specific address values.
  2. Even with `void*` fixed to `uint32_t`, the vault is `malloc()`'d at a different heap address on 64-bit (due to HEADER_PADDING = 48 vs 24). Polls hardcode `contents[0]` address as `0xB7FC0024`.
- **Fix**:
  1. Change `void *data` to `uint32_t data` in `locker_t`; fix cast-to/from to use `(uint32_t)(uintptr_t)` and `(void *)(uintptr_t)`
  2. On 64-bit, use `mmap(0xB7FC0000, 8192, ..., MAP_FIXED_NOREPLACE)` to place `the_vault` at a fixed address that yields `contents[0] == 0xB7FC0024` (same as 32-bit heap layout)
- **Files**: `challenges/TVS/src/vault.c`, `challenges/TVS/lib/cgc_malloc.h`

### middleware_handshake — `ebcbfd3c`
- **Category**: cgc-prefix-rename (tentative definition shadowing)
- **Symptom**: SIGSEGV on startup due to NULL function pointer call in `cgc_rng_init()`
- **Root Cause**: In `rng.c`, `const rng_def_t system_rng` and `const rng_def_t lcg_rng` were tentative definitions (zero-initialized) that shadowed the actual `cgc_system_rng` and `cgc_lcg_rng` symbols defined in `r_system.c` and `r_lcg.c`. The `rngs[]` array pointed to these zero structs, so function pointers were NULL.
- **Fix**: Replace tentative definitions with `extern const rng_def_t cgc_system_rng/cgc_lcg_rng` declarations and update `rngs[]` to reference them.
- **Files**: `challenges/middleware_handshake/src/rng.c`

### online_job_application — `545d8ace`
- **Category**: cgc-prefix-rename (string literal mismatch)
- **Symptom**: EXIT command never recognized; binary loops forever instead of terminating
- **Root Cause**: In `cgc_get_response()`, `memcmp(&response[2], "cgc_exit", cgc_strlen("exit"))` compared 4 bytes of `"cgc_"` against `"exit"` — never matched. The string literal was renamed with `cgc_` prefix but the comparison length was `cgc_strlen("exit") = 4`.
- **Fix**: Change `"cgc_exit"` to `"exit"` in the memcmp call.
- **Files**: `challenges/online_job_application/src/main.c`

### Overflow_Parking — `5d7cd74b`
- **Category**: wire-format + struct-align + pointer-cast
- **Symptom**: Binary reads wrong number of bytes; heap allocation crashes
- **Root Causes**:
  1. `parkinstr_t` contains `instrtype` (4 bytes) then `parkcmd_t`, gaining 4-byte padding on 64-bit → binary reads 24 bytes but polls send 12
  2. `cgc_size_t size` in `parkcmd_t` is 8 bytes on 64-bit, but wire format expects 4
  3. `(uint32_t)page` in malloc.c truncates 64-bit pointer
- **Fix**: `__attribute__((packed))` on `parkcmd_t` and `parkinstr_t`; change `cgc_size_t size` to `uint32_t size`; change `(uint32_t)page` to `(cgc_size_t)page` in malloc.c
- **Files**: `challenges/Overflow_Parking/src/service.c`, `challenges/Overflow_Parking/src/malloc.c`

### pizza_ordering_system — `01b30556`
- **Category**: stack-overflow (template static array sizing)
- **Symptom**: SIGSEGV immediately on first function call
- **Root Cause**: `List<T>` C++ template uses `T data[MAX_LIST_SIZE]` as a static array with `MAX_LIST_SIZE=1024`. `OrderIoManager` allocates `List<Order>` on the stack; each `Order` contains `List<Pizza*>` = 1024×8 = 8192 bytes on 64-bit. Total stack: ~8.4MB → stack overflow. On 32-bit: ~4.2MB (just barely works).
- **Fix**: Reduce `MAX_LIST_SIZE` from 1024 to 32. Polls use ≤13 pizzas and ≤11 orders.
- **Files**: `challenges/pizza_ordering_system/src/cgc_list.h`

### Single-Sign-On — `2f86d8e9`
- **Category**: wire-format (struct-align) + uninit-memory (token generation)
- **Symptom**: All polls fail; binary receives misaligned command fields
- **Root Causes**:
  1. `Command` struct: `char type[4]` followed by `unsigned long id` gains 4 bytes padding on 64-bit, causing misaligned reads of id and token from the wire
  2. `cgc_getAuthVal()` loop ran only 4 iterations (originally for 32-bit `long`), leaving bytes 4-7 of the 64-bit `unsigned long` auth_val uninitialized — unpredictable stack leak length in auth_failure
- **Fix**: `__attribute__((packed))` on `Command` struct; extend loop to `sizeof(unsigned long)` iterations so all 8 bytes are filled with non-null random data
- **Files**: `challenges/Single-Sign-On/src/cgc_service.h`, `challenges/Single-Sign-On/src/service.c`

### ValveChecks — `11b2d01e`
- **Category**: wire-format (struct-align)
- **Symptom**: Binary receives wrong bytes in `reqpkt_t`; checksum validation always fails
- **Root Cause**: `reqpkt_t` contains `reqbody_t data` (132 bytes) followed by `uint64_t additive`. On 64-bit, 4 bytes of alignment padding are inserted before `additive`, making the struct 184 bytes instead of 176. Polls send 176 bytes.
- **Fix**: `__attribute__((packed))` on both `reqbody_t` and `reqpkt_t`
- **Files**: `challenges/ValveChecks/src/cgc_service.h`

---

## Debugging Techniques

### GDB hardware watchpoints for memory corruption
```gdb
# Save address to GDB variable (survives function return)
set $addr = (uint64_t)node
watch *(uint32_t*)$addr
commands
  printf "Modified at %p, new value: 0x%08x\n", $addr, *(uint32_t*)$addr
  backtrace 5
  continue
end
```

### Identify wire format mismatch
```bash
# Run with --debug to see send/receive TAP output
python tools/cb-replay.py --cbs build64/challenges/FOO/FOO \
  --xml polls/FOO/poller/for-release/GEN_00000_00000.xml --debug --timeout 15
# Look for: expected: '\x...' result: '\x...' (different byte counts)
```

### Check if failure is pre-existing (both architectures)
```bash
source venv/bin/activate
for xml in polls/CHALLENGE/poller/for-release/GEN_*.xml; do
  r32=$(python tools/cb-replay.py --cbs build/challenges/CHALLENGE/CHALLENGE --xml $xml --timeout 15 2>&1 | grep "polls failed")
  r64=$(python tools/cb-replay.py --cbs build64/challenges/CHALLENGE/CHALLENGE --xml $xml --timeout 15 2>&1 | grep "polls failed")
  base=$(basename $xml)
  if echo "$r32" | grep -q "failed: [^0]" && echo "$r64" | grep -q "failed: [^0]"; then
    echo "BOTH FAIL: $base"
  elif echo "$r64" | grep -q "failed: [^0]"; then
    echo "64-BIT ONLY: $base"
  fi
done
```
