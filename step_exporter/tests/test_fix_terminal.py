#!/usr/bin/env python3
"""
测试脚本：验证Terminal#68-68修复
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

# 创建一个简单的立方体网格数据
def create_cube_mesh():
    """创建一个简单的立方体网格数据"""
    # 8个顶点
    vertices = [
        [-1, -1, -1],
        [1, -1, -1],
        [1, 1, -1],
        [-1, 1, -1],
        [-1, -1, 1],
        [1, -1, 1],
        [1, 1, 1],
        [-1, 1, 1]
    ]
    
    # 6个面，每个面4个顶点
    faces = [
        [0, 1, 2, 3],  # 前面
        [1, 5, 6, 2],  # 右面
        [5, 4, 7, 6],  # 后面
        [4, 0, 3, 7],  # 左面
        [3, 2, 6, 7],  # 上面
        [4, 5, 1, 0]   # 下面
    ]
    
    return vertices, faces

def test_export():
    """测试导出功能"""
    print("\n开始测试导出...")
    
    # 创建测试数据
    vertices, faces = create_cube_mesh()
    test_data = [{
        'name': 'TestCube',
        'vertices': vertices,
        'faces': faces
    }]
    
    # 导出文件路径
    output_file = os.path.join(os.path.dirname(__file__), "Terminal#68-68_test.step")
    
    try:
        # 使用增强版导出函数
        result = _step_exporter.export_scene_enhanced(
            output_file,
            test_data,
            1.0,  # 缩放因子
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
    print("=== Terminal#68-68 修复验证测试 ===")
    success = test_export()
    if success:
        print("\n✓ 测试通过！修复已应用。")
        print("现在可以在FreeCAD中测试导出的STEP文件。")
    else:
        print("\n✗ 测试失败，需要进一步调试。")
