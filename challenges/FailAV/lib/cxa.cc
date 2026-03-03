#include "cgc_cstdlib.h"
#include <new>
#include <stddef.h>

extern "C"
{
    void __cxa_pure_virtual()
    {
        cgc__terminate(1);
    }
}

/* Route C++ new/delete through the challenge's custom allocator so that
 * cgc_realloc/cgc_free can safely handle pointers from operator new.
 * Without this, on 64-bit systems, system-malloc addresses exceed the
 * custom allocator's mem_map bounds, causing segfaults. */
void *operator new(size_t size)
{
    void *p = cgc_malloc(size);
    if (!p) cgc__terminate(1);
    return p;
}

void *operator new[](size_t size)
{
    void *p = cgc_malloc(size);
    if (!p) cgc__terminate(1);
    return p;
}

void operator delete(void *p) noexcept
{
    cgc_free(p);
}

void operator delete[](void *p) noexcept
{
    cgc_free(p);
}

void operator delete(void *p, size_t) noexcept
{
    cgc_free(p);
}

void operator delete[](void *p, size_t) noexcept
{
    cgc_free(p);
}
