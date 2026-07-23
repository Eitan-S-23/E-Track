if(NOT DEFINED INPUT_FILE OR NOT DEFINED OUTPUT_FILE)
    message(FATAL_ERROR "INPUT_FILE and OUTPUT_FILE are required")
endif()
if(EXISTS "${INPUT_FILE}")
    execute_process(
        COMMAND "${CMAKE_COMMAND}" -E copy_if_different
            "${INPUT_FILE}" "${OUTPUT_FILE}"
        RESULT_VARIABLE COPY_RESULT
    )
    if(NOT COPY_RESULT EQUAL 0)
        message(FATAL_ERROR "Failed to copy ${INPUT_FILE}")
    endif()
endif()
