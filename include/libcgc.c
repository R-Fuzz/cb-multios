/* Copyright 2015 Peter Goodman (peter@trailofbits.com), all rights reserved. */

#define LIBCGC_IMPL
#include "libcgc.h"
#include "ansi_x931_aes128.h"

#include <errno.h>
#include <fcntl.h>
#include <signal.h>
#include <stdio.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <sys/select.h>
#include <sys/types.h>
#include <unistd.h>
#include <err.h>

#define MIN(a, b) (((a) < (b)) ? (a) : (b))
#define MAX(a, b) (((a) < (b)) ? (b) : (a))

/* Map a Linux errno value to a CGC errno value.
 * CGC/DECREE defined its own errno values that differ from Linux:
 *   CGC_EBADF=1, CGC_EFAULT=2, CGC_EINVAL=3, CGC_ENOMEM=4, CGC_ENOSYS=5, CGC_EPIPE=6
 * Challenge binaries use these CGC constants (e.g., EINVAL=3) so syscall
 * wrappers must return CGC error codes, not Linux error codes.
 */
static int linux_errno_to_cgc(int linux_errno) {
  switch (linux_errno) {
    case EBADF:  return CGC_EBADF;
    case EFAULT: return CGC_EFAULT;
    case EINVAL: return CGC_EINVAL;
    case ENOMEM: return CGC_ENOMEM;
    case ENOSYS: return CGC_ENOSYS;
    case EPIPE:  return CGC_EPIPE;
    default:     return linux_errno;
  }
}

/* Terminates the process. */
void cgc__terminate(unsigned int status) {
  exit(status);
  __builtin_unreachable();
}

/* Transmits data from one CGC process to another. */
int cgc_transmit(int fd, const void *buf, cgc_size_t count, cgc_size_t *tx_bytes) {
    const cgc_ssize_t ret = write(fd, buf, count);

    if (ret < 0) {
        return linux_errno_to_cgc(errno);
    } else if (tx_bytes != NULL) {
        *tx_bytes = ret;
    }

    return 0;
}

/* Receives data from another CGC process. */
int cgc_receive(int fd, void *buf, cgc_size_t count, cgc_size_t *rx_bytes) {
    const cgc_ssize_t ret = read(fd, buf, count);

    if (ret < 0) {
        return linux_errno_to_cgc(errno);
    } else if (rx_bytes != NULL) {
        *rx_bytes = ret;
    }

    return 0;
}

/* Marshal a CGC fd set into an OS fd set. */
static int cgc_copy_cgc_fd_set(const cgc_fd_set *cgc_fds, fd_set *os_fds, int *num_fds, int max_fd) {
  /* Only examine bits for fds in [0, max_fd).  On 64-bit, the wider
   * _fd_mask word may contain garbage from uninitialized stack storage
   * in the bits beyond the fds the caller actually set; ignoring those
   * bits prevents spurious EINVAL / EBADF returns. */
  for (unsigned fd = 0; fd < (unsigned)max_fd; ++fd) {
    if (CGC_FD_ISSET(fd, cgc_fds)) {
      // Shouldn't be using an fd greater than the allowed values
      if (fd >= EXPECTED_MAX_FDS) {
          return CGC_EBADF;
      }

      if (fd > NFDBITS) {
        continue;  /* OS set size is too small. */
      }
      FD_SET(fd, os_fds);
      ++*num_fds;
    }
  }
  return 0;
}

/* Marshal an OS fd set into a CGC fd set. */
static void cgc_copy_os_fd_set(const fd_set *os_fds, cgc_fd_set *cgc_fds) {
  for (unsigned fd = 0; fd < MIN(NFDBITS, CGC__NFDBITS); ++fd) {
    if (FD_ISSET(fd, os_fds)) {
      CGC_FD_SET(fd, cgc_fds);
    }
  }
}
int cgc_fdwait(int nfds, cgc_fd_set *readfds, cgc_fd_set *writefds,
               const struct cgc_timeval *timeout, int *readyfds) {

  int ret = cgc_check_timeout(timeout);
  int actual_num_fds = 0;
  struct timeval max_wait_time = {0, 0};
  fd_set read_fds;
  fd_set write_fds;

  if (ret) {
    return ret;
  } else if (0 > nfds || CGC__NFDBITS < nfds) {
    return CGC_EINVAL;
  }

  FD_ZERO(&read_fds);
  FD_ZERO(&write_fds);

  if (readfds) {
    if (0 != (ret = cgc_copy_cgc_fd_set(readfds, &read_fds, &actual_num_fds, nfds))) {
      return ret;
    }
  }

  if (writefds) {
    if (0 != (ret = cgc_copy_cgc_fd_set(writefds, &write_fds, &actual_num_fds, nfds))) {
      return ret;
    }
  }

  /* Note: The strict actual_num_fds == nfds check was removed.
   * On 64-bit, cgc_fd_set uses 64-bit _fd_mask words; uninitialized
   * challenge-side cgc_fd_set variables may have garbage in high bits,
   * causing spurious EINVAL.  The original CGC kernel did not enforce
   * this count, so we omit it here. */

  if (readfds)  CGC_FD_ZERO(readfds);
  if (writefds) CGC_FD_ZERO(writefds);

  if (timeout) {
    max_wait_time.tv_sec = timeout->tv_sec;
    max_wait_time.tv_usec = timeout->tv_usec;
  }

  int num_selected_fds = select(
          nfds,
          (readfds ? &read_fds : NULL),
          (writefds ? &write_fds : NULL),
          NULL,
          (timeout ? &max_wait_time : NULL));

  if (num_selected_fds < 0)
    return linux_errno_to_cgc(errno);

  if (readfds) {
    cgc_copy_os_fd_set(&read_fds, readfds);
  }

  if (writefds) {
    cgc_copy_os_fd_set(&write_fds, writefds);
  }

  if (readyfds) {
    *readyfds = num_selected_fds;
  }

  return 0;
}

/* Going to ignore `is_executable`. It's not really used in the official CGC
 * challenges, and if it were used, then JITed code would likely be 32-bit, and
 * ideally, this code will also work on 64-bit.
 */
int cgc_allocate(cgc_size_t length, int is_executable, void **addr) {
  int page_perms = PROT_READ | PROT_WRITE;
  if (is_executable)
    page_perms |= PROT_EXEC;

  int mmap_flags = MAP_ANONYMOUS | MAP_PRIVATE;

  /* On 64-bit systems, some challenges use custom allocators that assume
   * addresses fit in 32-bit space. Use MAP_32BIT to keep allocations
   * in the lower 2GB range, which is compatible with 32-bit address
   * space assumptions.
   * However, MAP_32BIT limits the total range to 2GB, so very large
   * allocations (>= 512MB) cannot use MAP_32BIT. For those, fall back
   * to unrestricted mmap after trying MAP_32BIT first.
   */
#if defined(__x86_64__) || defined(__aarch64__) || defined(__LP64__)
  #ifdef MAP_32BIT
    mmap_flags |= MAP_32BIT;
  #endif
#endif

  void *return_address = mmap(NULL, length, page_perms, mmap_flags, -1, 0);

#if defined(__x86_64__) || defined(__aarch64__) || defined(__LP64__)
  #ifdef MAP_32BIT
  /* If MAP_32BIT allocation failed (e.g., large allocation that doesn't fit
   * in the 2GB range), retry without MAP_32BIT. */
  if (return_address == MAP_FAILED && (mmap_flags & MAP_32BIT)) {
    mmap_flags &= ~MAP_32BIT;
    return_address = mmap(NULL, length, page_perms, mmap_flags, -1, 0);
  }
  #endif
#endif

  if (return_address == MAP_FAILED) {
    return linux_errno_to_cgc(errno);
  }

  if (addr)
    *addr = return_address;

  memset(return_address, 0, length);

  return 0;
}

/* Deallocate some range of memory and mark the pages as free. */
int cgc_deallocate(void *addr, cgc_size_t length) {

  const int ret = munmap(addr, length);

  if (ret < 0) {
    return linux_errno_to_cgc(errno);
  }

  return 0;
}


static cgc_prng *cgc_internal_prng = NULL;
/**
 * Initializes the prng for use with cgc_random and the flag page
 */
static void cgc_try_init_prng() {
    // Don't reinitialize
    if (cgc_internal_prng != NULL) return;

    uint8_t prng_seed[BLOCK_SIZE * 3] = {
        0x73, 0x65, 0x65, 0x64, 0x73, 0x65, 0x65, 0x64, 0x73, 0x65, 0x65, 0x64,
        0x73, 0x65, 0x65, 0x64, 0x30, 0x31, 0x32, 0x33, 0x34, 0x35, 0x36, 0x37,
        0x38, 0x39, 0x61, 0x62, 0x63, 0x64, 0x65, 0x66, 0x00, 0x00, 0x00, 0x00,
        0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00
    }; // Default seed, definitely not random

    // This will be hex encoded
    const char *prng_seed_hex = getenv("seed");
    if (prng_seed_hex != NULL && strlen(prng_seed_hex) == (BLOCK_SIZE * 3) * 2) {
        // Convert the hex encoded seed to a normal string
        const char *pos = prng_seed_hex;
        for(int i = 0; i < BLOCK_SIZE * 3; ++i) {
            sscanf(pos, "%2hhx", &prng_seed[i]);
            pos += 2;
        }
    }


    // Create the prng
    cgc_internal_prng = (cgc_prng *) malloc(sizeof(cgc_prng));
    cgc_aes_state *seed = (cgc_aes_state *) prng_seed;
    __libcgc_init_prng(cgc_internal_prng, seed);
}

int cgc_random(void *buf, cgc_size_t count, cgc_size_t *rnd_bytes) {
    // Get random bytes from the prng
    cgc_try_init_prng();
    cgc_aes_get_bytes(cgc_internal_prng, count, buf);

    if (rnd_bytes)
      *rnd_bytes = count;

    return 0;
}

static void __attribute__ ((constructor)) cgc_initialize_flag_page(void) {
  void *mmap_addr = mmap(CGC_FLAG_PAGE_ADDRESS, PAGE_SIZE,
                         PROT_READ | PROT_WRITE,
                         MAP_FIXED | MAP_PRIVATE | MAP_ANONYMOUS,
                         -1, 0);

  if (mmap_addr != CGC_FLAG_PAGE_ADDRESS) {
    err(1, "[!] Failed to map the flag page");
  }

  // Fill the flag page with bytes from the prng
  cgc_try_init_prng();
  cgc_aes_get_bytes(cgc_internal_prng, PAGE_SIZE, mmap_addr);
}

