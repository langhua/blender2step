#!/usr/bin/env python3
"""
测试脚本：验证体积为0的形状导出修复
"""

import os
import sys

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

def create_test_shapes():
    """
    创建测试形状，包括体积为0的平面
    """
    test_objects = []
    
    # 1. 立方体（有体积）
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
    
    # 2. 平面（体积为0）
    plane_vertices = [
        [-1, -1, 0], [1, -1, 0], [1, 1, 0], [-1, 1, 0]
    ]
    plane_faces = [
        [0, 1, 2, 3]
    ]
    test_objects.append({
        'name': 'Test_Plane',  # 这个是体积为0的平面
        'vertices': plane_vertices,
        'faces': plane_faces
    })
    
    # 3. 网格（可能体积为0）
    grid_vertices = []
    grid_faces = []
    
    # 创建10x10网格
    for i in range(11):
        for j in range(11):
            x = (i - 5) * 0.2
            y = (j - 5) * 0.2
            grid_vertices.append([x, y, 0])
    
    # 创建网格面
    for i in range(10):
        for j in range(10):
            idx0 = i * 11 + j
            idx1 = i * 11 + (j + 1)
            idx2 = (i + 1) * 11 + (j + 1)
            idx3 = (i + 1) * 11 + j
            grid_faces.append([idx0, idx1, idx2, idx3])
    
    test_objects.append({
        'name': 'Test_Grid',  # 这个是体积为0的网格
        'vertices': grid_vertices,
        'faces': grid_faces
    })
    
    return test_objects

def test_volume_zero_export():
    """
    测试体积为0的形状导出
    """
    print("\n=== 测试体积为0的形状导出 ===")
    
    # 创建测试数据
    scene_data = create_test_shapes()
    print(f"创建了 {len(scene_data)} 个测试对象")
    for i, obj in enumerate(scene_data):
        print(f"  {i+1}. {obj['name']}: {len(obj['vertices'])} 顶点, {len(obj['faces'])} 面")
    
    # 导出文件路径
    output_file = os.path.join(os.path.dirname(__file__), "volume_zero_test.step")
    
    try:
        # 使用增强版导出函数
        result = _step_exporter.export_scene_enhanced(
            output_file,
            scene_data,
            1.0,  # 缩放因子
            1,     # 修复几何
            1,     # 创建实体
            1      # 高级BREP
        )
        
        if result:
            print(f"\n✓ 导出成功: {output_file}")
            print(f"文件大小: {os.path.getsize(output_file)} 字节")
            return True
        else:
            print("\n✗ 导出失败")
            return False
    except Exception as e:
        print(f"\n✗ 导出过程中出错: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("=== 体积为0形状导出修复测试 ===")
    success = test_volume_zero_export()
    if success:
        print("\n✓ 测试通过！修复已应用。")
        print("体积为0的形状（如平面和网格）现在可以正确导出。")
    else:
        print("\n✗ 测试失败，需要进一步调试。")
