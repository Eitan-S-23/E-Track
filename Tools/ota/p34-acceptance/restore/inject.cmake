function(configure_restore_app)
    get_target_property(sources X_Track_App_GCC SOURCES)
    list(LENGTH sources before_count)
    list(FILTER sources EXCLUDE REGEX "/USER/main[.]cpp$")
    list(LENGTH sources after_count)
    math(EXPR difference "${before_count} - ${after_count}")
    if(NOT difference EQUAL 1)
        message(FATAL_ERROR "Exactly the production App main must be replaced")
    endif()
    set_property(TARGET X_Track_App_GCC PROPERTY SOURCES "${sources}")
    target_sources(X_Track_App_GCC PRIVATE
        "${CMAKE_CURRENT_FUNCTION_LIST_DIR}/restore_main.cpp"
        "${CMAKE_CURRENT_FUNCTION_LIST_DIR}/restore_core.c"
        "D:/github/my/E-Track/.cache/p34-acceptance1/f/boot/src/boot_slot.c")
    target_include_directories(X_Track_App_GCC PRIVATE "${CMAKE_CURRENT_FUNCTION_LIST_DIR}")
endfunction()
cmake_language(DEFER CALL configure_restore_app)
