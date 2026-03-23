# ASAN build toolchain for CGC challenges
#
# Usage:
#   mkdir build64_asan && cd build64_asan
#   cmake -DCMAKE_TOOLCHAIN_FILE=../cmake/asan.cmake ..
#   cmake --build .
#
# This builds challenge binaries with AddressSanitizer and replaces
# custom allocators (cgc_malloc/cgc_free) with libc malloc/free so
# ASAN can track heap operations.
#
# PoVs are built WITHOUT sanitizers (they use libpov's own allocator).

set(CMAKE_SYSTEM_PROCESSOR amd64)
set(CMAKE_C_COMPILER clang)
set(CMAKE_CXX_COMPILER clang++)

if(WIN32)
    set(CMAKE_ASM_MASM_COMPILER clang)
else(WIN32)
    set(CMAKE_ASM_COMPILER clang)
endif(WIN32)

# ASAN + UBSan flags for challenge binaries (PoVs override below)
set(CMAKE_C_FLAGS_INIT "-O0 -fsanitize=address,undefined -fno-omit-frame-pointer -fno-sanitize-recover=all -g")
set(CMAKE_CXX_FLAGS_INIT "-O0 -fsanitize=address,undefined -fno-omit-frame-pointer -fno-sanitize-recover=all -g")
set(CMAKE_EXE_LINKER_FLAGS_INIT "-fsanitize=address,undefined")
set(CMAKE_SHARED_LINKER_FLAGS_INIT "-fsanitize=address,undefined")

# Enable the ASAN malloc replacement
set(USE_ASAN_MALLOC ON CACHE BOOL "Replace custom allocators with libc malloc for ASAN" FORCE)
