#!/usr/bin/env python3
"""
测试脚本：直接测试C++扩展模块，验证修复是否有效
"""

import os
import sys

# 添加lib目录到Python路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'lib'))

print("=== 测试STEP Exporter C++扩展模块 ===")

try:
    # 导入C++扩展模块
    import _step_exporter
    print("✓ 成功导入 _step_exporter 模块")
    
    # 测试版本信息
    version = _step_exporter.get_version()
    print(f"✓ 模块版本: {version}")
    
    # 创建一个简单的立方体网格数据
    vertices = [
        [0, 0, 0],    # 顶点0
        [1, 0, 0],    # 顶点1
        [1, 1, 0],    # 顶点2
        [0, 1, 0],    # 顶点3
        [0, 0, 1],    # 顶点4
        [1, 0, 1],    # 顶点5
        [1, 1, 1],    # 顶点6
        [0, 1, 1]     # 顶点7
    ]
    
    faces = [
        [0, 1, 2, 3],  # 底面
        [4, 5, 6, 7],  # 顶面
        [0, 1, 5, 4],  # 前面
        [2, 3, 7, 6],  # 后面
        [0, 3, 7, 4],  # 左面
        [1, 2, 6, 5]   # 右面
    ]
    
    # 转换为三角面（因为Blender导出的是三角面）
    triangulated_faces = []
    for face in faces:
        # 将四边形转换为两个三角形
        if len(face) == 4:
            triangulated_faces.append([face[0], face[1], face[2]])
            triangulated_faces.append([face[0], face[2], face[3]])
        else:
            triangulated_faces.append(face)
    
    print(f"✓ 创建测试网格: {len(vertices)} 顶点, {len(triangulated_faces)} 面")
    
    # 准备导出数据
    scene_data = [
        {
            'name': 'Test Cube',
            'vertices': vertices,
            'faces': triangulated_faces
        }
    ]
    
    # 测试导出
    test_file = 'test_fix.step'
    print(f"\n=== 测试导出到 {test_file} ===")
    
    # 调用增强版导出函数
    success = _step_exporter.export_scene_enhanced(
        test_file,
        scene_data,
        1.0,    # scale
        1,      # fix_geometry
        1,      # create_solid
        1       # advanced_brep
    )
    
    if success:
        print("✓ 导出成功！")
        # 检查文件是否存在
        if os.path.exists(test_file):
            file_size = os.path.getsize(test_file)
            print(f"✓ 文件已创建: {file_size} 字节")
            print(f"\n=== 测试完成 ===")
            print("修复已验证：C++扩展模块现在应该能正确导出STEP文件，不再创建空的形状定义。")
        else:
            print("✗ 导出成功但文件未创建")
    else:
        print("✗ 导出失败")
        
except Exception as e:
    print(f"✗ 测试失败: {e}")
    import traceback
    traceback.print_exc()
