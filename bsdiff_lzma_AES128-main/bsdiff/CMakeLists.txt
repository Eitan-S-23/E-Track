cmake_minimum_required(VERSION 3.10)
project(bsdiff C)

# Set C standard
set(CMAKE_C_STANDARD 99)

# Include directories
include_directories(
    ${CMAKE_CURRENT_SOURCE_DIR}
    ${CMAKE_CURRENT_SOURCE_DIR}/bsdiff
    ${CMAKE_CURRENT_SOURCE_DIR}/file
    ${CMAKE_CURRENT_SOURCE_DIR}/user
    ${CMAKE_CURRENT_SOURCE_DIR}/lib
    ${CMAKE_CURRENT_SOURCE_DIR}/lzma
    ${CMAKE_CURRENT_SOURCE_DIR}/AES128_CTR
)

# Source files
set(SOURCES
    main.c
    bsdiff/bsdiff.c
    bsdiff/bsdiff_wrapper.c
    file/vFile.c
    lib/crc32.c
    user/bs_user_interface.c
    lzma/7zAlloc.c
    lzma/7zBuf.c
    lzma/7zCrc.c
    lzma/7zCrcOpt.c
    lzma/7zFile.c
    lzma/7zStream.c
    lzma/Alloc.c
    lzma/CpuArch.c
    lzma/LzFind.c
    lzma/LzFindMt.c
    lzma/LzFindOpt.c
    lzma/LzmaDec.c
    lzma/LzmaEnc.c
    lzma/Threads.c
    AES128_CTR/aes_core.c
)

# Create executable
add_executable(bsdiff ${SOURCES})

# Define preprocessor flags if needed
target_compile_definitions(bsdiff PRIVATE
    _7ZIP_ST
    _WIN32
)

# Output directory
set_target_properties(bsdiff PROPERTIES
    RUNTIME_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/bin"
) 