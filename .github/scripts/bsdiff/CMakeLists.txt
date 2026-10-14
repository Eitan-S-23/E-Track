cmake_minimum_required(VERSION 3.16)
project(firmware_release_bsdiff C)

# Reuse the vendor source list. Its standalone project unconditionally defines
# _WIN32 even on Linux; the release adapter removes only that host selection.
add_subdirectory("${CMAKE_CURRENT_LIST_DIR}/../../../bsdiff_lzma_AES128-main/bsdiff" vendor)
if(NOT WIN32)
    get_target_property(definitions bsdiff COMPILE_DEFINITIONS)
    list(REMOVE_ITEM definitions _WIN32)
    set_target_properties(bsdiff PROPERTIES COMPILE_DEFINITIONS "${definitions}")
endif()
