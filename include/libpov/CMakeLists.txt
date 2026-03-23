file(GLOB srcs *.c)
add_library(pov ${srcs})

target_compile_definitions(pov PUBLIC -DNPATCHED)
if(NOT WIN32)
    target_compile_options(pov PUBLIC
        -pedantic
        -fno-builtin
        -O0
    )
endif()

# libpov has its own custom allocator that ASAN can't track.
# Disable ASAN instrumentation so PoVs don't crash in libpov internals.
if(USE_ASAN_MALLOC)
    target_compile_options(pov PRIVATE -fno-sanitize=address,undefined)
endif()

target_include_directories(pov PUBLIC ${CMAKE_CURRENT_SOURCE_DIR})
target_link_libraries(pov LINK_PUBLIC cgc)
