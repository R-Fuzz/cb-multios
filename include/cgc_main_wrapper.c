/* CGC/DECREE main() wrapper
 *
 * In DECREE (CGC's OS), the first argument to main() (argc) held the
 * address of the flag page. On standard Linux, argc is the argument count.
 * This wrapper intercepts main() via --wrap=main and passes
 * CGC_FLAG_PAGE_ADDRESS as argc to maintain compatibility with challenges
 * that use secret_page_i as a pointer to the flag page.
 *
 * This wrapper also clears a large region of stack before calling main()
 * to ensure that stack-allocated buffers in main() start with zeroed content.
 * In the original DECREE/CGC environment, stack pages were zero-initialized.
 * On Linux, startup code (including AES-based PRNG initialization for the
 * flag page) may leave non-zero bytes in the stack area that main() will use.
 * Challenges that rely on zero-initialized stack buffers need this clearing.
 */
#include "libcgc.h"
#include <stdint.h>
#include <string.h>

extern int __real_main(int argc, char *argv[]);

/* Zero a region of stack below the current frame to simulate the DECREE
 * behavior of zero-initialized stack pages.  128 KB covers the largest
 * stack-allocated buffer any challenge binary uses (MAX_DATA_SIZE=32768 in
 * Headscratch) plus generous overhead for other local variables. */
static void __attribute__((noinline)) cgc_clear_stack(void) {
    volatile char buf[131072];  /* 128 KB */
    memset((void *)buf, 0, sizeof(buf));
    /* Prevent the compiler from optimizing away the memset by using a barrier */
    __asm__ volatile ("" : : "r"(buf) : "memory");
}

int __wrap_main(int argc, char *argv[]) {
    /* Zero the stack area that main() will use, simulating DECREE's
     * zero-initialized stack behavior. */
    cgc_clear_stack();
    /* Pass CGC_FLAG_PAGE_ADDRESS as argc, matching DECREE convention */
    return __real_main((int)(intptr_t)CGC_FLAG_PAGE_ADDRESS, argv);
}
