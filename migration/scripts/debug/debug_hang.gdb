# GDB script for debugging hanging/stuck processes
# Usage: gdb -p <pid> -x debug_hang.gdb

# Catch all signals that indicate crashes
catch signal SIGSEGV SIGABRT SIGBUS SIGFPE SIGILL

# Define commands to run when a signal is caught
commands
  echo \n=== CRASH DETECTED ===\n
  backtrace
  info registers
  echo \n=== END CRASH INFO ===\n
  detach
  quit
end

# Set a breakpoint on cgc_receive to see when it's waiting for input
break cgc_receive
commands
  silent
  printf ">>> cgc_receive called from:\n"
  backtrace 3
  continue
end

# Set a breakpoint on cgc_transmit to see when it's sending output
break cgc_transmit
commands
  silent
  printf ">>> cgc_transmit called from:\n"
  backtrace 3
  continue
end

# Continue execution
echo \n=== GDB attached, breakpoints set, continuing execution ===\n
continue
