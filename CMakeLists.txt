cmake_minimum_required(VERSION 3.20)
project(blender2step LANGUAGES C CXX)

# 设置C++标准
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# ====== 1. Python配置 - 使用 find_package 自动查找 ======
# 让 CMake 自动查找 Python
find_package(Python 3.11 REQUIRED COMPONENTS Interpreter Development)

message(STATUS "Python found:")
message(STATUS "  Include dirs: ${Python_INCLUDE_DIRS}")
message(STATUS "  Library: ${Python_LIBRARIES}")
message(STATUS "  Library dirs: ${Python_LIBRARY_DIRS}")
message(STATUS "  Executable: ${Python_EXECUTABLE}")

include_directories(${Python_INCLUDE_DIRS})
link_directories(${Python_LIBRARY_DIRS})

# ====== 2. OpenCASCADE 配置 ======
set(OPEN_CASCADE_ROOT "F:/opencascade-7.9.3-vc14-64-with-debug-combined/opencascade-7.9.3-vc14-64")
set(OCC_LIB_DIR "${OPEN_CASCADE_ROOT}/win64/vc14/lib")
set(OCC_INC_DIR "${OPEN_CASCADE_ROOT}/inc")

# 包含目录
include_directories(
    ${OCC_INC_DIR}
    ${CMAKE_CURRENT_SOURCE_DIR}/include
)

# 库目录
link_directories(${OCC_LIB_DIR})

# 检查关键库文件
set(REQUIRED_OCC_LIBS
    TKernel
    TKDESTEP
    TKMath
    TKG3d
    TKPrim
    TKBRep
    TKTopAlgo
    TKShHealing
    TKMesh
    TKXSBase
    TKService
    TKV3d
    TKG2d
    TKGeomBase
    TKBO
    TKBool
    TKOffset
    TKFillet
)

# 收集存在的库
set(OCC_LIBS)
foreach(LIB_NAME ${REQUIRED_OCC_LIBS})
    set(LIB_PATH "${OCC_LIB_DIR}/${LIB_NAME}.lib")
    if(EXISTS ${LIB_PATH})
        list(APPEND OCC_LIBS ${LIB_PATH})
        message(STATUS "Found: ${LIB_NAME}.lib")
    else()
        message(WARNING "Not found: ${LIB_PATH}")
    endif()
endforeach()

# ====== 3. 添加编译定义 ======
# 必须添加这些定义以确保正确的链接
add_definitions(
    -D_CRT_SECURE_NO_WARNINGS
    -D_WINDOWS
    -D_USRDLL
    -DSTEPEXPORTER_EXPORTS
)

# ====== 4. 创建目标 ======
# 源文件列表
set(SOURCES
    src/step_exporter.cpp
    src/step_converter.cpp
)

# 创建共享库
add_library(step_exporter SHARED ${SOURCES})

# 设置输出属性
set_target_properties(step_exporter PROPERTIES
    OUTPUT_NAME "step_exporter"
    PREFIX ""
    SUFFIX ".pyd"
    DEBUG_POSTFIX "_d"  # Debug 版本添加 _d 后缀
)

# ====== 5. 链接库 ======
# 注意链接顺序：先 OpenCASCADE 库，再 Python 库
target_link_libraries(step_exporter
    ${OCC_LIBS}
    ${Python_LIBRARIES}
    kernel32.lib
    user32.lib
    gdi32.lib
    winspool.lib
    shell32.lib
    ole32.lib
    oleaut32.lib
    uuid.lib
    comdlg32.lib
    advapi32.lib
    ws2_32.lib
)

# ====== 6. 编译选项 ======
if(MSVC)
    target_compile_options(step_exporter PRIVATE
        /W3
        /EHsc
        /MP  # 多处理器编译
    )
    
    if(CMAKE_BUILD_TYPE STREQUAL "Debug")
        target_compile_options(step_exporter PRIVATE
            /MDd
            /Zi
            /Od
        )
    else()
        target_compile_options(step_exporter PRIVATE
            /MD
            /O2
        )
    endif()
endif()

# ====== 7. 复制 DLL 到输出目录 ======
set(OCC_BIN_DIR "${OPEN_CASCADE_ROOT}/win64/vc14/bin")

# 创建复制 DLL 的命令
if(EXISTS ${OCC_BIN_DIR})
    add_custom_command(TARGET step_exporter POST_BUILD
        COMMAND ${CMAKE_COMMAND} -E echo "Copying required DLLs..."
    )
    
    # 列出需要复制的关键 DLL
    set(REQUIRED_DLLS
        TKernel.dll
        TKDESTEP.dll
        TKMath.dll
        TKG3d.dll
        TKPrim.dll
        TKBRep.dll
        TKTopAlgo.dll
        TKShHealing.dll
    )
    
    foreach(DLL_NAME ${REQUIRED_DLLS})
        set(DLL_PATH "${OCC_BIN_DIR}/${DLL_NAME}")
        if(EXISTS ${DLL_PATH})
            add_custom_command(TARGET step_exporter POST_BUILD
                COMMAND ${CMAKE_COMMAND} -E copy_if_different
                    "${DLL_PATH}"
                    $<TARGET_FILE_DIR:step_exporter>
                COMMENT "Copying ${DLL_NAME}"
            )
        endif()
    endforeach()
endif()