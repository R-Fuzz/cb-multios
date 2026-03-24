/*
 * ASAN-compatible replacement for CGC custom allocators.
 *
 * When building with -DUSE_ASAN_MALLOC, the build system excludes per-challenge
 * custom allocators (lib/malloc.c, lib/malloc_common.c, lib/free.c, etc.) and
 * links this file instead. This lets AddressSanitizer track heap allocations
 * and detect use-after-free, heap-buffer-overflow, double-free, etc.
 */

#include <stdlib.h>
#include <string.h>
#include <malloc.h>

typedef unsigned long cgc_size_t;

void *cgc_malloc(cgc_size_t size)
{
    return malloc((size_t)size);
}

void cgc_free(void *ptr)
{
    free(ptr);
}

void *cgc_calloc(cgc_size_t count, cgc_size_t size)
{
    return calloc((size_t)count, (size_t)size);
}

void *cgc_realloc(void *ptr, cgc_size_t size)
{
    return realloc(ptr, (size_t)size);
}

cgc_size_t cgc_malloc_size(void *heap, void *ptr)
{
    (void)heap;
    if (!ptr)
        return 0;
    return (cgc_size_t)malloc_usable_size(ptr);
}

/*
 * Intercept cgc_allocate/cgc_deallocate so ASAN can track buffers
 * that challenges allocate via the CGC syscall-level allocator.
 * Without this, cgc_allocate goes through mmap and ASAN has no
 * shadow metadata, so overflows manifest as SEGV instead of
 * heap-buffer-overflow.
 */
int cgc_allocate(cgc_size_t length, int is_executable, void **addr)
{
    (void)is_executable;
    void *p = calloc(1, (size_t)length);
    if (!p)
        return -1;
    if (addr)
        *addr = p;
    return 0;
}

int cgc_deallocate(void *addr, cgc_size_t length)
{
    (void)length;
    free(addr);
    return 0;
}
