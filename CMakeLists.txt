cmake_minimum_required(VERSION 3.20)
project(blender2step LANGUAGES C CXX)

# ====== 1. 设置 vcpkg 工具链 ======
# 禁用 vcpkg manifest 模式
set(VCPKG_MANIFEST_MODE OFF CACHE BOOL "Disable vcpkg manifest mode")

# 尝试使用相对路径
if(EXISTS "${CMAKE_CURRENT_SOURCE_DIR}/vcpkg/scripts/buildsystems/vcpkg.cmake")
    set(CMAKE_TOOLCHAIN_FILE "${CMAKE_CURRENT_SOURCE_DIR}/vcpkg/scripts/buildsystems/vcpkg.cmake" CACHE STRING "Vcpkg toolchain file")
elseif(EXISTS "f:/git/vcpkg/scripts/buildsystems/vcpkg.cmake")
    set(CMAKE_TOOLCHAIN_FILE "f:/git/vcpkg/scripts/buildsystems/vcpkg.cmake" CACHE STRING "Vcpkg toolchain file")
else()
    message(FATAL_ERROR "Could not find vcpkg toolchain file. Please install vcpkg and set the correct path.")
endif()

# 设置C++标准
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# ====== 2. 查找 ZLIB (OpenCASCADE dependency) ======
# Must be done BEFORE find_package(OpenCASCADE) because OpenCASCADE depends on ZLIB
set(ZLIB_LIBRARY "f:/git/blender2step/vcpkg_installed/x64-windows-release/lib/zlib.lib" CACHE FILEPATH "ZLIB library path")
set(ZLIB_INCLUDE_DIR "f:/git/blender2step/vcpkg_installed/x64-windows-release/include" CACHE PATH "ZLIB include path")
set(ZLIB_FOUND TRUE CACHE BOOL "ZLIB found")
# Create imported target for ZLIB
if(NOT TARGET ZLIB::ZLIB)
    add_library(ZLIB::ZLIB UNKNOWN IMPORTED)
    set_target_properties(ZLIB::ZLIB PROPERTIES
        IMPORTED_LOCATION "${ZLIB_LIBRARY}"
        INTERFACE_INCLUDE_DIRECTORIES "${ZLIB_INCLUDE_DIR}"
    )
endif()

# ====== 3. 查找 OpenCASCADE ======
# 设置依赖库路径
set(freetype_DIR "f:/git/blender2step/vcpkg_installed/x64-windows-release/share/freetype" CACHE PATH "freetype config dir")
find_package(freetype CONFIG REQUIRED)
set(OpenCASCADE_DIR "f:/git/blender2step/vcpkg_installed/x64-windows-release/share/opencascade" CACHE PATH "Path to OpenCASCADE config")
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

# ====== 4. 设置 Python 路径 ======
# 使用标准 Python 3.11 头文件和导入库
# 运行时由Blender环境提供python311.dll
set(PYTHON_INCLUDE_DIR "C:/Python311/include")
set(PYTHON_LIBRARY "C:/Python311/libs/python311.lib")

# 禁用 vcpkg 自动检测 Python
set(Python3_EXECUTABLE "" CACHE FILEPATH "Python3 executable")
set(Python3_LIBRARY "" CACHE FILEPATH "Python3 library")
set(Python3_INCLUDE_DIR "" CACHE PATH "Python3 include dir")
set(Python3_ROOT_DIR "" CACHE PATH "Python3 root dir")

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
    # Incremental export functions
    src/step_exporter_incremental.cpp
    # Module initialization
    src/step_exporter_module.cpp
    # STEP converter
    src/step_converter.cpp
    # Rounded box and bottom shell creation
    src/step_exporter_rounded_box.cpp
    # Cylinder detection and reconstruction
    src/cylinder/cylinder_types.h
    src/cylinder/cylinder_detector.h
    src/cylinder/cylinder_detector.cpp
    src/cylinder/cylinder_face_analyzer.h
    src/cylinder/cylinder_face_analyzer.cpp
    src/cylinder/cylinder_cluster_detector.h
    src/cylinder/cylinder_cluster_detector.cpp
    src/cylinder/cylinder_deduplicator.h
    src/cylinder/cylinder_deduplicator.cpp
    src/cylinder/cylinder_geometry.cpp
    src/cylinder/cylinder_utils.cpp
    src/step_exporter_cylinder_reconstruct.cpp
    # Parametric cylinder/cone/hollow creation
    src/step_exporter_cylinder_parametric.cpp
)

# 设置 Python 头文件路径（使用 Blender 自带的 Python 3.11 头文件）
include_directories(
    ${PYTHON_INCLUDE_DIR}
    ${CMAKE_CURRENT_SOURCE_DIR}/include
)

# 设置输出名称
set_target_properties(step_exporter PROPERTIES
    OUTPUT_NAME "_step_exporter"
    PREFIX ""
    SUFFIX ".pyd"
)

add_custom_command(TARGET step_exporter POST_BUILD
    COMMAND ${CMAKE_COMMAND} -E copy_if_different
        "$<TARGET_FILE:step_exporter>"
        "${CMAKE_SOURCE_DIR}/step_exporter/lib/_step_exporter.pyd"
    COMMENT "Copying _step_exporter.pyd to step_exporter/lib/"
)

# ====== 5. 链接库 ======
# Python 扩展模块需要链接 Python 导入库来解析符号
# 运行时由Blender环境提供python311.dll
target_link_libraries(step_exporter
    PRIVATE
        ${OpenCASCADE_LIBRARIES}  # 使用 vcpkg 找到的所有库
        ${PYTHON_LIBRARY}  # Python 导入库，用于解析符号
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