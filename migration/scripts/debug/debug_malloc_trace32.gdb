# GDB script to trace cgc_malloc allocations (32-bit)
set pagination off
set confirm off

# Catch crashes
handle SIGSEGV stop print
handle SIGABRT stop print

# Track malloc allocations
break cgc_malloc

commands
  silent
  # On 32-bit, arg is on stack. Finish and check return value
  finish
  printf "cgc_malloc() = %p\n", $eax
  continue
end

# Track free calls
break cgc_free

commands
  silent
  # On 32-bit, first arg is at esp+4
  set $ptr_to_free = *(void**)($esp + 4)
  printf "cgc_free(%p)\n", $ptr_to_free
  continue
end

# Break on vector copy constructor to see context
break cgc_vector.h:54

commands
  silent
  printf "\n=== VECTOR COPY: items[%d] at %p ===\n", i, &items[i]
  x/2xw &items[i]
  continue
end

continue
