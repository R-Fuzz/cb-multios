# Simple malloc/free tracer - just count and track patterns
set pagination off
set confirm off

# Catch crashes
handle SIGSEGV stop print
handle SIGABRT stop print

# Count mallocs
set $malloc_count = 0
set $free_count = 0

# Track malloc returns
break cgc_malloc
commands
  silent
  finish
  set $malloc_count = $malloc_count + 1
  printf "[%d] cgc_malloc() = %p\n", $malloc_count, $eax
  continue
end

# Track free - examine memory at the pointer to see if it looks like heap
break cgc_free
commands
  silent
  # Read first argument from stack (esp+4 after call, but we're at entry so it's esp+4)
  finish
  set $free_count = $free_count + 1
  printf "[%d] cgc_free() returned\n", $free_count
  continue
end

# Show vector copy with memory contents
break cgc_vector.h:52
commands
  silent
  printf "\n=== VECTOR COPY CONSTRUCTOR: allocating items array ===\n"
  printf "size = %d, will call cgc_malloc(%d bytes)\n", size, sizeof(T) * size
  continue
end

break cgc_vector.h:54
commands
  silent
  printf "=== VECTOR COPY: assigning items[%d] ===\n", i
  printf "items[%d] at %p, content: ", i, &items[i]
  x/2xw &items[i]
  continue
end

continue
