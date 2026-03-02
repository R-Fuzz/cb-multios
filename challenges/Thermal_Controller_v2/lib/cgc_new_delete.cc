/*
 * Override C++ operator new and delete to use cgc_malloc/cgc_free
 * This prevents corruption of system malloc metadata on 64-bit
 */

extern "C" {
#include "cgc_malloc.h"
}

void* operator new(unsigned long size) {
    return cgc_malloc(size);
}

void* operator new[](unsigned long size) {
    return cgc_malloc(size);
}

void operator delete(void* ptr) noexcept {
    cgc_free(ptr);
}

void operator delete[](void* ptr) noexcept {
    cgc_free(ptr);
}

void operator delete(void* ptr, unsigned long) noexcept {
    cgc_free(ptr);
}

void operator delete[](void* ptr, unsigned long) noexcept {
    cgc_free(ptr);
}
