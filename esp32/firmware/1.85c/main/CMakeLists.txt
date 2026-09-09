file(GLOB_RECURSE SRCS "${CMAKE_CURRENT_LIST_DIR}/*.cpp" "${CMAKE_CURRENT_LIST_DIR}/*.c")
set(EMBEDDED_FILES "")

idf_component_register(
    SRCS ${SRCS}
    INCLUDE_DIRS "."
    EMBED_TXTFILES ${EMBEDDED_FILES}
)

get_property(brookesia_runtime_app_stage_targets GLOBAL PROPERTY BROOKESIA_RUNTIME_APP_STAGE_TARGETS)
if(brookesia_runtime_app_stage_targets)
    list(REMOVE_DUPLICATES brookesia_runtime_app_stage_targets)
endif()
get_property(brookesia_system_super_stage_targets GLOBAL PROPERTY BROOKESIA_SYSTEM_SUPER_STAGE_TARGETS)
if(brookesia_system_super_stage_targets)
    list(REMOVE_DUPLICATES brookesia_system_super_stage_targets)
endif()

set(ROUND_UI_OVERLAY "${CMAKE_CURRENT_LIST_DIR}/../round_ui")
set(LITTLEFS_ROOT "${CMAKE_CURRENT_LIST_DIR}/../littlefs")
execute_process(
    COMMAND python3 "${ROUND_UI_OVERLAY}/patch_super_launcher.py"
    RESULT_VARIABLE ROUND_LAUNCHER_PATCH
)
if(NOT ROUND_LAUNCHER_PATCH EQUAL 0)
    message(FATAL_ERROR "round launcher C++ patch failed")
endif()
execute_process(
    COMMAND python3 "${ROUND_UI_OVERLAY}/patch_super_keyboard.py"
    RESULT_VARIABLE ROUND_KEYBOARD_PATCH
)
if(NOT ROUND_KEYBOARD_PATCH EQUAL 0)
    message(FATAL_ERROR "round keyboard C++ patch failed")
endif()
add_custom_target(
    mindgraph_round_ui
    COMMAND python3 "${ROUND_UI_OVERLAY}/apply_round_ui.py"
            --littlefs "${LITTLEFS_ROOT}"
            --overlay "${ROUND_UI_OVERLAY}"
    DEPENDS ${brookesia_runtime_app_stage_targets} ${brookesia_system_super_stage_targets}
    COMMENT "Apply 360x360 round Super/Settings overlay"
    VERBATIM
)

# `littlefs_create_partition_image` is only defined when the joltwallet/littlefs
# component is pulled into the build. That dependency is conditional (see
# brookesia_hal_adaptor: it requires the storage device + littlefs Kconfig options),
# so guard the call to avoid a hard configure error when littlefs is absent.
if(COMMAND littlefs_create_partition_image)
    littlefs_create_partition_image(
        littlefs_data
        ../littlefs
        FLASH_IN_PROJECT
        DEPENDS ${brookesia_runtime_app_stage_targets} ${brookesia_system_super_stage_targets} mindgraph_round_ui
    )
else()
    message(WARNING
        "littlefs_create_partition_image is not available (joltwallet/littlefs not in build); "
        "skipping littlefs_data image generation. Enable "
        "BROOKESIA_HAL_ADAPTOR_ENABLE_STORAGE_DEVICE / *_FILE_SYSTEM_IMPL / *_ENABLE_LITTLEFS "
        "if the littlefs partition is needed.")
endif()
