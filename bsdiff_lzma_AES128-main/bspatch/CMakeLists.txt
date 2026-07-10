cmake_minimum_required(VERSION 3.10)
project(bspatch C)

# Set C standard
set(CMAKE_C_STANDARD 99)

# Include directories
include_directories(
    ${CMAKE_CURRENT_SOURCE_DIR}
    ${CMAKE_CURRENT_SOURCE_DIR}/bspatch
    ${CMAKE_CURRENT_SOURCE_DIR}/file
    ${CMAKE_CURRENT_SOURCE_DIR}/user
    ${CMAKE_CURRENT_SOURCE_DIR}/lib
    ${CMAKE_CURRENT_SOURCE_DIR}/lzma
    ${CMAKE_CURRENT_SOURCE_DIR}/AES128_CTR
)

# Source files
set(SOURCES
    main.c
    bspatch/bspatch.c
    file/vFile.c
    user/interface.c
    lib/crc32.c
    lzma/lzma_decompress.c
    file/vFile.c
    lzma/7zFile.c
    lzma/LzmaDec.c
    lzma/LzFind.c
    user/interface.c
    lib/crc32.c
    AES128_CTR/aes_core.c
)

# Create executable
add_executable(bspatch ${SOURCES})

# Define preprocessor flags if needed
target_compile_definitions(bspatch PRIVATE
    _7ZIP_ST
    _WIN32
    bspatch_debug=1
)

# Output directory
set_target_properties(bspatch PROPERTIES
    RUNTIME_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/bin"
) 