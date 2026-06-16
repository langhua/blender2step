#!/usr/bin/env python3
"""
测试脚本：验证不同斜率角度的圆柱体和标准圆锥导出功能
"""

import os
import sys
import math

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "lib"))

try:
    import _step_exporter as step_exporter
except ImportError as e:
    print(f"错误: 无法导入_step_exporter模块")
    print(f"请确保模块已正确编译并位于以下路径之一:")
    for path in sys.path:
        print(f"  - {path}")
    sys.exit(1)

def create_tapered_cylinder(taper_angle_deg, bottom_radius=1.0, height=2.0, scale=1000.0):
    """
    创建带指定斜率角度的圆柱体测试数据
    
    参数:
        taper_angle_deg: 斜率角（度）
        bottom_radius: 底部半径（Blender单位）
        height: 高度（Blender单位）
        scale: 缩放因子（Blender单位到毫米）
    """
    taper_angle_rad = math.radians(taper_angle_deg)
    top_radius = bottom_radius - height * math.tan(taper_angle_rad)
    
    if top_radius <= 0:
        print(f"  警告: 斜率角{taper_angle_deg}°太大，顶部半径为负！")
        return None
    
    print(f"  底部半径: {bottom_radius * scale:.2f} mm")
    print(f"  顶部半径: {top_radius * scale:.2f} mm")
    print(f"  高度: {height * scale:.2f} mm")
    print(f"  斜率角: {taper_angle_deg}°")
    print(f"  半径差: {(bottom_radius - top_radius) * scale:.2f} mm")
    
    vertices = []
    num_segments = 64
    
    for i in range(num_segments):
        angle = 2 * math.pi * i / num_segments
        x = bottom_radius * math.cos(angle) * scale
        y = bottom_radius * math.sin(angle) * scale
        z = 0.0
        vertices.append([x, y, z])
    
    for i in range(num_segments):
        angle = 2 * math.pi * i / num_segments
        x = top_radius * math.cos(angle) * scale
        y = top_radius * math.sin(angle) * scale
        z = height * scale
        vertices.append([x, y, z])
    
    faces = []
    
    for i in range(1, num_segments - 1):
        faces.append([0, i, i+1])
    
    offset = num_segments
    for i in range(1, num_segments - 1):
        faces.append([offset, offset + i, offset + i + 1])
    
    for i in range(num_segments):
        next_i = (i + 1) % num_segments
        faces.append([i, next_i, offset + next_i])
        faces.append([i, offset + next_i, offset + i])
    
    return {
        'name': f'Cylinder_Tapered_{taper_angle_deg}deg',
        'vertices': vertices,
        'faces': faces,
        'scale': scale
    }

def create_standard_cone(bottom_radius=1.0, height=2.0, scale=1000.0):
    """
    创建标准圆锥（顶部半径为0）测试数据
    """
    print(f"  底部半径: {bottom_radius * scale:.2f} mm")
    print(f"  顶部半径: 0.00 mm (尖顶)")
    print(f"  高度: {height * scale:.2f} mm")
    print(f"  半顶角: {math.degrees(math.atan(bottom_radius/height)):.2f}°")
    
    vertices = []
    num_segments = 64
    
    for i in range(num_segments):
        angle = 2 * math.pi * i / num_segments
        x = bottom_radius * math.cos(angle) * scale
        y = bottom_radius * math.sin(angle) * scale
        z = 0.0
        vertices.append([x, y, z])
    
    vertices.append([0.0, 0.0, height * scale])
    
    faces = []
    
    for i in range(1, num_segments - 1):
        faces.append([0, i, i+1])
    
    apex = num_segments
    for i in range(num_segments):
        next_i = (i + 1) % num_segments
        faces.append([i, next_i, apex])
    
    return {
        'name': 'Standard_Cone',
        'vertices': vertices,
        'faces': faces,
        'scale': scale
    }

def test_export(scene_data, output_file, description):
    """导出测试"""
    print(f"\n{'='*60}")
    print(f"测试: {description}")
    print(f"{'='*60}")
    
    def progress_callback(progress, message):
        if progress % 20 == 0:
            print(f"  进度: {progress}% - {message}")
    
    result = step_exporter.export_scene_enhanced(
        output_file,
        scene_data,
        1000.0,
        1,
        1,
        1,
        'AP214DIS',
        'MILLIMETER',
        1,
        0.001,
        0,
        progress_callback
    )
    
    if result:
        print(f"  导出成功: {output_file}")
        print(f"  文件大小: {os.path.getsize(output_file)} 字节")
        return True
    else:
        print(f"  导出失败!")
        return False

def main():
    print("="*60)
    print("测试不同斜率角度的圆柱体和标准圆锥导出")
    print("="*60)
    
    test_cases = [
        ("3°斜率圆柱", lambda: create_tapered_cylinder(3.0)),
        ("4°斜率圆柱", lambda: create_tapered_cylinder(4.0)),
        ("5°斜率圆柱", lambda: create_tapered_cylinder(5.0)),
        ("标准圆锥", lambda: create_standard_cone()),
    ]
    
    results = []
    
    for name, create_func in test_cases:
        print(f"\n创建 {name}...")
        obj = create_func()
        
        if obj is None:
            results.append((name, False, "创建失败"))
            continue
        
        output_file = os.path.join(os.path.dirname(__file__), f"test_{name.replace('°', 'deg').replace(' ', '_')}.step")
        
        success = test_export([obj], output_file, name)
        
        if success:
            results.append((name, True, output_file))
        else:
            results.append((name, False, "导出失败"))
    
    print("\n" + "="*60)
    print("测试结果汇总")
    print("="*60)
    
    for name, success, info in results:
        status = "[OK] 成功" if success else "[X] 失败"
        print(f"  {name}: {status}")
        if success:
            print(f"    文件: {info}")

if __name__ == "__main__":
    main()
