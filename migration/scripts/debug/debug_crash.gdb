# GDB script for automatic crash detection and backtrace
# Usage: gdb -p <pid> -x debug_crash.gdb

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

# Continue execution
continue
