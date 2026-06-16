#!/usr/bin/env python3
"""
测试脚本：验证带2°斜率的圆柱体导出功能
"""

import os
import sys
import math

# 添加模块路径
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "lib"))

try:
    import _step_exporter
    print("成功导入_step_exporter模块")
    print(f"模块版本: {_step_exporter.get_version()}")
except ImportError as e:
    print(f"导入模块失败: {e}")
    print("当前Python路径:")
    for path in sys.path:
        print(f"  - {path}")
    sys.exit(1)

def create_tapered_cylinder_data():
    """
    创建带2°斜率的圆柱体的测试数据
    """
    test_objects = []
    
    # 带2°斜率的圆柱体
    # 半顶角 = 2°，tan(α) = (r1 - r2) / height
    bottom_radius = 1.0
    height = 2.0
    taper_angle_deg = 2.0  # 斜率角（度）
    taper_angle_rad = math.radians(taper_angle_deg)
    # 正确计算顶部半径：r2 = r1 - height * tan(α)
    top_radius = bottom_radius - height * math.tan(taper_angle_rad)
    scale = 1000.0  # 缩放因子（Blender单位到毫米）
    
    print(f"  底部半径: {bottom_radius * scale:.2f} mm")
    print(f"  顶部半径: {top_radius * scale:.2f} mm")
    print(f"  高度: {height * scale:.2f} mm")
    print(f"  斜率角: {taper_angle_deg}°")
    print(f"  半径差: {(bottom_radius - top_radius) * scale:.2f} mm")
    
    # 生成顶点
    vertices = []
    num_segments = 64  # 增加分段数以获得更平滑的圆锥面
    
    # 底部圆
    for i in range(num_segments):
        angle = 2 * math.pi * i / num_segments
        x = bottom_radius * math.cos(angle) * scale
        y = bottom_radius * math.sin(angle) * scale
        z = 0.0
        vertices.append([x, y, z])
    
    # 顶部圆
    for i in range(num_segments):
        angle = 2 * math.pi * i / num_segments
        x = top_radius * math.cos(angle) * scale
        y = top_radius * math.sin(angle) * scale
        z = height * scale
        vertices.append([x, y, z])
    
    # 生成面
    faces = []
    
    # 底部端面
    for i in range(1, num_segments - 1):
        faces.append([0, i, i+1])
    
    # 顶部端面
    offset = num_segments
    for i in range(1, num_segments - 1):
        faces.append([offset, offset + i, offset + i + 1])
    
    # 侧面（使用三角形）
    for i in range(num_segments):
        next_i = (i + 1) % num_segments
        # 每个四边形分割为两个三角形
        faces.append([i, next_i, offset + next_i])
        faces.append([i, offset + next_i, offset + i])
    
    test_objects.append({
        'name': 'Cylinder_Tapered_2deg',
        'vertices': vertices,
        'faces': faces,
        'scale': 1000.0  # 添加缩放因子
    })
    
    return test_objects

def test_tapered_cylinder_export():
    """测试带2°斜率的圆柱体导出功能"""
    print("\n=== 测试带2°斜率的圆柱体导出 ===")
    print("创建带2°斜率的圆柱体模型...")
    
    # 创建测试数据
    scene_data = create_tapered_cylinder_data()
    print(f"创建了 {len(scene_data)} 个测试对象")
    
    # 导出文件路径
    output_file = os.path.join(os.path.dirname(__file__), "test_tapered_cylinder.step")
    
    try:
        # 定义进度回调函数
        def progress_callback(progress):
            print(f"导出进度: {progress:.1f}%")
        
        # 使用增强版导出函数
        result = _step_exporter.export_scene_enhanced(
            output_file,
            scene_data,
            1000.0,  # 缩放因子（Blender单位到毫米）
            1,     # 修复几何
            1,     # 创建实体
            1,     # 高级BREP
            'AP214DIS',  # STEP schema
            'MILLIMETER',  # 单位
            1,     # 启用日志
            0.001,  # 缝合容差
            0,     # 创建爆炸图（0表示缝合在一起）
            progress_callback
        )
        
        if result:
            print(f"导出成功: {output_file}")
            print(f"文件大小: {os.path.getsize(output_file)} 字节")
            return True
        else:
            print("导出失败")
            return False
    except Exception as e:
        print(f"导出过程中出错: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("=== 测试带2°斜率的圆柱体导出 ===")
    success = test_tapered_cylinder_export()
    if success:
        print("\n测试通过！导出成功。")
        print("现在可以在FreeCAD中测试导出的STEP文件。")
    else:
        print("\n测试失败，需要进一步调试。")
