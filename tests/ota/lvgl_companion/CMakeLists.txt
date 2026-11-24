cmake_minimum_required(VERSION 3.16)
project(companion_modal_test C CXX)

get_filename_component(ROOT "${CMAKE_CURRENT_LIST_DIR}/../../.." ABSOLUTE)
set(DIALPLATE_UI_ROOT "${ROOT}" CACHE PATH "Read-only UI source and resource root")
set(DIALPLATE_VARIANTS "desktop;hardware;fallback" CACHE STRING "Dialplate test variants")
set(LV_CONF_PATH "${CMAKE_CURRENT_LIST_DIR}/lv_conf.h" CACHE STRING "" FORCE)
add_subdirectory("${ROOT}/Simulator/LVGL.Simulator/lvgl" lvgl EXCLUDE_FROM_ALL)

add_library(ui_fonts STATIC
    "${DIALPLATE_UI_ROOT}/USER/App/Resource/Font/font_cn_16.c"
    "${DIALPLATE_UI_ROOT}/USER/App/Resource/Font/font_bahnschrift_13.c"
    "${DIALPLATE_UI_ROOT}/USER/App/Resource/Font/font_bahnschrift_24.c"
    "${DIALPLATE_UI_ROOT}/USER/App/Resource/Font/font_bahnschrift_32.c"
    "${DIALPLATE_UI_ROOT}/USER/App/Resource/Font/font_bahnschrift_48.c"
    "${DIALPLATE_UI_ROOT}/USER/App/Resource/Font/font_bahnschrift_17.c")
target_link_libraries(ui_fonts PUBLIC lvgl)

option(DIALPLATE_ONLY "Build the source-bound Dialplate/display tests" OFF)

if(NOT DIALPLATE_ONLY)
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
else()
    target_compile_definitions(lvgl PUBLIC LV_FONT_MONTSERRAT_8=1 "LV_CONF_PATH=${LV_CONF_PATH}")
    add_library(dialplate_assets STATIC
        "${DIALPLATE_UI_ROOT}/USER/App/Resource/Font/font_agencyb_12.c"
        "${DIALPLATE_UI_ROOT}/USER/App/Resource/Font/font_iconfont_16.c"
        "${DIALPLATE_UI_ROOT}/USER/App/Resource/Font/font_iconfont_20.c"
        "${DIALPLATE_UI_ROOT}/USER/App/Resource/Image/img_src_dialplate_skin.c"
        "${DIALPLATE_UI_ROOT}/USER/App/Resource/Image/img_src_gps_arrow_light.c"
        "${DIALPLATE_UI_ROOT}/USER/App/Resource/Image/img_src_battery.c"
        "${DIALPLATE_UI_ROOT}/USER/App/Resource/Image/img_src_bluetooth.c"
        "${DIALPLATE_UI_ROOT}/USER/App/Resource/Image/img_src_satellite.c")
    target_link_libraries(dialplate_assets PUBLIC ui_fonts lvgl)
    foreach(variant ${DIALPLATE_VARIANTS})
        add_executable(dialplate_${variant}
            "${ROOT}/tests/ota/dialplate_ui_harness.cpp"
            "${DIALPLATE_UI_ROOT}/USER/App/Pages/Dialplate/DialplateView.cpp")
        target_compile_features(dialplate_${variant} PRIVATE cxx_std_11)
        target_compile_options(dialplate_${variant} PRIVATE -Wall -Wextra -Werror)
        target_include_directories(dialplate_${variant} PRIVATE
            "${HARNESS_DIR}" "${DIALPLATE_UI_ROOT}/USER/App"
            "${ROOT}/USER" "${ROOT}/USER/App"
            "${ROOT}/Simulator/LVGL.Simulator")
        target_link_libraries(dialplate_${variant} PRIVATE dialplate_assets lvgl)
        if(NOT DIALPLATE_UI_ROOT STREQUAL ROOT)
            target_compile_definitions(dialplate_${variant} PRIVATE DIALPLATE_REFERENCE=1)
            target_compile_options(dialplate_${variant} PRIVATE
                -include "${HARNESS_DIR}/reference_page_dependencies.h")
        endif()
        if(variant STREQUAL "hardware")
            target_compile_definitions(dialplate_${variant} PRIVATE ARDUINO=111 AT32F435RGT7)
            target_sources(dialplate_${variant} PRIVATE
                "${ROOT}/MDK-ARM_F435/Platform/lv_port/lv_port_disp.cpp")
        elseif(variant STREQUAL "fallback")
            target_compile_definitions(dialplate_${variant} PRIVATE ARDUINO=111)
        endif()
        if(MINGW)
            target_link_options(dialplate_${variant} PRIVATE -static-libgcc -static-libstdc++)
        endif()
    endforeach()
endif()
