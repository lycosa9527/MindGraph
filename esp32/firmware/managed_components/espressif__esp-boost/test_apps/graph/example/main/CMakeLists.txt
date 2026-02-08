file(GLOB_RECURSE C_SRCS "*.c")
file(GLOB_RECURSE CPP_SRCS "*.cpp")

idf_component_register(
    SRCS ${C_SRCS} ${CPP_SRCS}
    INCLUDE_DIRS .
    WHOLE_ARCHIVE
)

target_compile_options(${COMPONENT_LIB}
    PRIVATE 
    $<$<COMPILE_LANGUAGE:CXX>:
        -Wno-unused-but-set-variable -Wno-unused-variable
        -Wno-catch-value -Wno-error=catch-value=
        -Wno-unused-function
        -Wno-error=maybe-uninitialized -Wno-maybe-uninitialized -Wno-uninitialized
        -Wno-sized-deallocation
        -Wno-deprecated-declarations -Wno-deprecated-copy
    >
)
