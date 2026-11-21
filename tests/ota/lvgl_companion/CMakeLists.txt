cmake_minimum_required(VERSION 3.16)
project(companion_modal_test C CXX)

get_filename_component(ROOT "${CMAKE_CURRENT_LIST_DIR}/../../.." ABSOLUTE)
set(LV_CONF_PATH "${CMAKE_CURRENT_LIST_DIR}/lv_conf.h" CACHE STRING "" FORCE)
add_subdirectory("${ROOT}/Simulator/LVGL.Simulator/lvgl" lvgl EXCLUDE_FROM_ALL)

add_library(ui_fonts STATIC
    "${ROOT}/USER/App/Resource/Font/font_cn_16.c"
    "${ROOT}/USER/App/Resource/Font/font_bahnschrift_13.c"
    "${ROOT}/USER/App/Resource/Font/font_bahnschrift_24.c"
    "${ROOT}/USER/App/Resource/Font/font_bahnschrift_48.c"
    "${ROOT}/USER/App/Resource/Font/font_bahnschrift_17.c")
target_link_libraries(ui_fonts PUBLIC lvgl)

foreach(variant original candidate)
    add_executable(${variant} "${HARNESS_DIR}/${variant}.cpp")
    target_compile_features(${variant} PRIVATE cxx_std_11)
    target_compile_options(${variant} PRIVATE -Wall -Wextra -Werror)
    target_include_directories(${variant} PRIVATE "${ROOT}/USER/App")
    target_link_libraries(${variant} PRIVATE ui_fonts lvgl)
    if(MINGW)
        target_link_options(${variant} PRIVATE -static-libgcc -static-libstdc++)
    endif()
endforeach()
