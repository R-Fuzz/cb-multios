# GDB script to trace cgc_malloc allocations and detect reuse
set pagination off
set confirm off

# Catch crashes
handle SIGSEGV stop print
handle SIGABRT stop print

# Track malloc allocations
break cgc_malloc

commands
  silent
  # Call the function and capture return value
  finish
  printf "cgc_malloc() returned: %p (size was in $rdi on entry)\n", $rax
  continue
end

# Track free calls
break cgc_free

commands
  silent
  printf "cgc_free(%p)\n", $rdi
  continue
end

# Break on vector copy constructor to see context
break cgc_vector.h:54

commands
  silent
  printf "\n=== VECTOR COPY: items[%d] at %p (uninit memory) ===\n", i, &items[i]
  x/2xg &items[i]
  continue
end

continue
