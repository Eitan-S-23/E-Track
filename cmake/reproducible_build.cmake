# Keep Release firmware timestamps stable across clean rebuilds.
set(P2_5_SOURCE_DATE_EPOCH "$ENV{SOURCE_DATE_EPOCH}")
if(P2_5_SOURCE_DATE_EPOCH STREQUAL "")
    if(CMAKE_BUILD_TYPE STREQUAL "Release")
        message(FATAL_ERROR
            "Release firmware builds require SOURCE_DATE_EPOCH (Unix seconds)")
    endif()
else()
    if(NOT P2_5_SOURCE_DATE_EPOCH MATCHES "^[0-9]+$")
        message(FATAL_ERROR "SOURCE_DATE_EPOCH must contain decimal Unix seconds")
    endif()
endif()

string(CONCAT P2_5_REPRODUCIBLE_METADATA
    "schema=p2-5-reproducible-build-v1\n"
    "source_date_epoch=${P2_5_SOURCE_DATE_EPOCH}\n"
    "build_type=${CMAKE_BUILD_TYPE}\n"
    "cmake_version=${CMAKE_VERSION}\n")
file(WRITE "${CMAKE_CURRENT_BINARY_DIR}/reproducible-build.txt"
    "${P2_5_REPRODUCIBLE_METADATA}")

function(p2_5_configure_reproducible_compiler_launchers)
    if(P2_5_SOURCE_DATE_EPOCH STREQUAL "")
        return()
    endif()

    set(P2_5_ENV_LAUNCHER
        "${CMAKE_COMMAND};-E;env;SOURCE_DATE_EPOCH=${P2_5_SOURCE_DATE_EPOCH}")
    if(KEIL_GCC_COMPILER_CACHE)
        list(APPEND P2_5_ENV_LAUNCHER "${KEIL_GCC_COMPILER_CACHE}")
    endif()
    set(CMAKE_C_COMPILER_LAUNCHER "${P2_5_ENV_LAUNCHER}" PARENT_SCOPE)
    set(CMAKE_CXX_COMPILER_LAUNCHER "${P2_5_ENV_LAUNCHER}" PARENT_SCOPE)
    set(CMAKE_ASM_COMPILER_LAUNCHER "${P2_5_ENV_LAUNCHER}" PARENT_SCOPE)
endfunction()
