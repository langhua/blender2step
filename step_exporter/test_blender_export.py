#!/usr/bin/env python3
"""
测试脚本：验证Blender模型导出功能
"""

import os
import sys
import tempfile
import shutil

# 添加模块路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "lib"))

try:
    import _step_exporter
    print("✓ 成功导入_step_exporter模块")
    print(f"模块版本: {_step_exporter.get_version()}")
except ImportError as e:
    print(f"✗ 导入模块失败: {e}")
    print("当前Python路径:")
    for path in sys.path:
        print(f"  - {path}")
    sys.exit(1)

def create_test_scene_data():
    """
    创建测试场景数据，模拟Blender中生成的模型
    返回与Blender导出时相同格式的数据结构
    """
    test_objects = []
    
    # 1. 立方体（基础测试）
    cube_vertices = [
        [-1, -1, -1], [1, -1, -1], [1, 1, -1], [-1, 1, -1],
        [-1, -1, 1], [1, -1, 1], [1, 1, 1], [-1, 1, 1]
    ]
    cube_faces = [
        [0, 1, 2, 3], [1, 5, 6, 2], [5, 4, 7, 6],
        [4, 0, 3, 7], [3, 2, 6, 7], [4, 5, 1, 0]
    ]
    test_objects.append({
        'name': 'Test_Cube',
        'vertices': cube_vertices,
        'faces': cube_faces
    })
    
    # 2. 球体（曲面测试）
    # 简化球体，使用较少的面
    sphere_vertices = [
        [0, 0, 1], [1, 0, 0], [0, 1, 0], [-1, 0, 0], [0, -1, 0], [0, 0, -1]
    ]
    sphere_faces = [
        [0, 1, 2], [0, 2, 3], [0, 3, 4], [0, 4, 1],
        [5, 2, 1], [5, 3, 2], [5, 4, 3], [5, 1, 4]
    ]
    test_objects.append({
        'name': 'Test_Sphere',
        'vertices': sphere_vertices,
        'faces': sphere_faces
    })
    
    # 3. 圆柱体（圆柱面测试）
    cylinder_vertices = [
        [1, 0, 1], [-1, 0, 1], [0, 1, 1], [0, -1, 1],
        [1, 0, -1], [-1, 0, -1], [0, 1, -1], [0, -1, -1]
    ]
    cylinder_faces = [
        [0, 1, 2], [0, 2, 3], [0, 3, 1],  # 顶面
        [4, 6, 5], [4, 7, 6], [4, 5, 7],  # 底面
        [0, 2, 6, 4], [2, 1, 5, 6],  # 侧面
        [1, 3, 7, 5], [3, 0, 4, 7]
    ]
    test_objects.append({
        'name': 'Test_Cylinder',
        'vertices': cylinder_vertices,
        'faces': cylinder_faces
    })
    
    return test_objects

def test_blender_export():
    """测试从Blender生成模型并导出STEP的功能"""
    print("\n=== 测试Blender模型导出 ===")
    print("模拟Blender中生成模型并导出STEP文件...")
    
    # 创建测试数据
    scene_data = create_test_scene_data()
    print(f"创建了 {len(scene_data)} 个测试对象")
    
    # 导出文件路径
    output_file = os.path.join(os.path.dirname(__file__), "Terminal#121-121_test.step")
    
    try:
        # 使用增强版导出函数，模拟Blender中的导出参数
        result = _step_exporter.export_scene_enhanced(
            output_file,
            scene_data,
            0.001,  # 缩放因子（Blender单位到毫米）
            1,     # 修复几何
            1,     # 创建实体
            1      # 高级BREP
        )
        
        if result:
            print(f"✓ 导出成功: {output_file}")
            print(f"文件大小: {os.path.getsize(output_file)} 字节")
            return True
        else:
            print("✗ 导出失败")
            return False
    except Exception as e:
        print(f"✗ 导出过程中出错: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("=== Terminal#121-121 修复验证测试 ===")
    success = test_blender_export()
    if success:
        print("\n✓ 测试通过！修复已应用。")
        print("现在可以在FreeCAD中测试导出的STEP文件。")
    else:
        print("\n✗ 测试失败，需要进一步调试。")
