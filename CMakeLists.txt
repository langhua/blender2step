cmake_minimum_required(VERSION 3.20)
project(blender2step LANGUAGES C CXX)

# ====== 1. 设置 vcpkg 工具链 ======
set(CMAKE_TOOLCHAIN_FILE "F:/git/vcpkg/scripts/buildsystems/vcpkg.cmake" CACHE STRING "Vcpkg toolchain file")

# 设置C++标准
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# ====== 2. 查找 OpenCASCADE ======
# 使用 vcpkg 提供的 CONFIG 模式
set(OpenCASCADE_DIR "f:/git/blender2step/vcpkg_installed/x64-windows/share/opencascade" CACHE PATH "Path to OpenCASCADE config")
# 优先使用静态库
set(OpenCASCADE_USE_STATIC_LIBS ON)
find_package(OpenCASCADE CONFIG REQUIRED)

# 打印找到的库
message(STATUS "OpenCASCADE found via vcpkg:")
message(STATUS "  Include dirs: ${OpenCASCADE_INCLUDE_DIRS}")
message(STATUS "  Libraries: ${OpenCASCADE_LIBRARIES}")

# 检查是否有 TKSTEP 或 TKDESTEP
foreach(LIB ${OpenCASCADE_LIBRARIES})
    if(LIB MATCHES "TKSTEP" OR LIB MATCHES "TKDESTEP")
        message(STATUS "  Found STEP library: ${LIB}")
    endif()
endforeach()

# ====== 3. 设置 Python 路径 ======
set(PYTHON_INCLUDE_DIR "C:/Python311/include")
set(PYTHON_LIBRARY "C:/Python311/libs/python311.lib")

include_directories(
    ${PYTHON_INCLUDE_DIR}
    ${CMAKE_CURRENT_SOURCE_DIR}/include
)

# ====== 4. 创建库 ======
add_library(step_exporter SHARED
    # Basic shape functions (split from step_exporter_basic.cpp)
    src/step_exporter_fix_shape.cpp
    src/step_exporter_create_shape_from_mesh.cpp
    src/step_exporter_create_solid_from_mesh.cpp
    # Curve shape functions
    src/step_exporter_curve.cpp
    src/step_exporter_curve_dict.cpp
    src/step_exporter_curve_poly.cpp
    src/step_exporter_curve_bezier.cpp
    src/step_exporter_curve_nurbs.cpp
    src/step_exporter_curve_common.cpp
    # Shape fixing functions
    src/step_exporter_shape_fix.cpp
    # Export functions
    src/step_exporter_export_scene.cpp
    src/step_exporter_export_enhanced_parse.cpp
    src/step_exporter_export_enhanced_progress.cpp
    src/step_exporter_export_enhanced_writer.cpp
    src/step_exporter_export_enhanced_objects.cpp
    src/step_exporter_export_enhanced_transfer.cpp
    src/step_exporter_export_enhanced.cpp
    # Module initialization
    src/step_exporter_module.cpp
    # STEP converter
    src/step_converter.cpp
    # Cylinder surface reconstruction
    src/step_exporter_cylinder_reconstruct.cpp
)

# 设置输出名称
set_target_properties(step_exporter PROPERTIES
    OUTPUT_NAME "_step_exporter"
    PREFIX ""
    SUFFIX ".pyd"
)

find_package(Python3 COMPONENTS Development REQUIRED)
target_include_directories(step_exporter PRIVATE ${Python3_INCLUDE_DIRS})

# ====== 5. 链接库 ======
# 方法1：使用 vcpkg 提供的库列表（推荐）
target_link_libraries(step_exporter
    PRIVATE
        ${OpenCASCADE_LIBRARIES}  # 使用 vcpkg 找到的所有库
        ${PYTHON_LIBRARY}
        ${Python3_LIBRARIES}
    PUBLIC
        # Windows 系统库
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
        /MD
        /utf-8  # 关键：强制使用 UTF-8 编码
    )
    
    target_compile_definitions(step_exporter PRIVATE
        -D_CRT_SECURE_NO_WARNINGS
        -D_SILENCE_ALL_CXX17_DEPRECATION_WARNINGS
    )
endif()