# GDB script to examine uninitialized memory in vector<CString> copy constructor
set pagination off
set confirm off

# Catch crashes
handle SIGSEGV stop print
handle SIGABRT stop print

# Break right before the problematic assignment
break cgc_vector.h:54

commands
  silent
  printf "\n=== vector copy constructor, about to assign ===\n"
  printf "i = %d\n", i
  printf "this->items[i] address = %p\n", &items[i]

  # Examine the uninitialized memory (32-bit: CString is 8 bytes)
  printf "Uninitialized memory (8 bytes):\n"
  x/2xw &items[i]

  printf "other.items[i] address = %p\n", &other.items[i]
  printf "other.items[i] content:\n"
  x/2xw &other.items[i]

  continue
end

continue
