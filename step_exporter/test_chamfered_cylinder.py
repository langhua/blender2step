#!/usr/bin/env python3
"""
测试脚本：顶部带倒角的圆柱体导出
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

def create_chamfered_cylinder(radius=1.0, height=2.0, chamfer_size=0.1, scale=1000.0, num_segments=64):
    """
    创建顶部带倒角的圆柱体
    
    参数:
        radius: 圆柱半径（Blender单位）
        height: 圆柱高度（Blender单位）
        chamfer_size: 倒角尺寸（Blender单位）
        scale: 缩放因子（Blender单位到毫米）
        num_segments: 圆周分段数
    """
    print(f"  圆柱半径: {radius * scale:.2f} mm")
    print(f"  圆柱高度: {height * scale:.2f} mm")
    print(f"  倒角尺寸: {chamfer_size * scale:.2f} mm")
    print(f"  倒角角度: 45°")
    
    vertices = []
    faces = []
    
    r = radius * scale
    h = height * scale
    c = chamfer_size * scale
    
    # 底部圆周顶点 (z = 0)
    for i in range(num_segments):
        angle = 2 * math.pi * i / num_segments
        x = r * math.cos(angle)
        y = r * math.sin(angle)
        vertices.append([x, y, 0.0])
    
    # 顶部圆周顶点 - 倒角前的位置 (z = h - c)
    for i in range(num_segments):
        angle = 2 * math.pi * i / num_segments
        x = r * math.cos(angle)
        y = r * math.sin(angle)
        vertices.append([x, y, h - c])
    
    # 倒角圆周顶点 (z = h, 半径 = r - c)
    for i in range(num_segments):
        angle = 2 * math.pi * i / num_segments
        x = (r - c) * math.cos(angle)
        y = (r - c) * math.sin(angle)
        vertices.append([x, y, h])
    
    # 顶面中心点
    center_top_idx = len(vertices)
    vertices.append([0, 0, h])
    
    # 底面中心点
    center_bottom_idx = len(vertices)
    vertices.append([0, 0, 0])
    
    # 创建面
    # 1. 底面
    for i in range(num_segments):
        next_i = (i + 1) % num_segments
        faces.append([center_bottom_idx, i, next_i])
    
    # 2. 圆柱侧面（底部到倒角前）
    for i in range(num_segments):
        next_i = (i + 1) % num_segments
        bottom_idx = i
        top_idx = num_segments + i
        next_bottom_idx = next_i
        next_top_idx = num_segments + next_i
        faces.append([bottom_idx, top_idx, next_top_idx, next_bottom_idx])
    
    # 3. 倒角面（斜面）
    for i in range(num_segments):
        next_i = (i + 1) % num_segments
        before_chamfer_idx = num_segments + i
        chamfer_idx = 2 * num_segments + i
        next_before_chamfer_idx = num_segments + next_i
        next_chamfer_idx = 2 * num_segments + next_i
        faces.append([before_chamfer_idx, chamfer_idx, next_chamfer_idx, next_before_chamfer_idx])
    
    # 4. 顶面（倒角后的圆）
    for i in range(num_segments):
        next_i = (i + 1) % num_segments
        chamfer_idx = 2 * num_segments + i
        next_chamfer_idx = 2 * num_segments + next_i
        faces.append([center_top_idx, chamfer_idx, next_chamfer_idx])
    
    return {
        "name": "Chamfered_Cylinder",
        "vertices": vertices,
        "faces": faces,
        "scale": scale
    }

def create_fillet_cylinder(radius=1.0, height=2.0, fillet_radius=0.1, scale=1000.0, num_segments=64, num_fillet_segments=8):
    """
    创建顶部带圆角的圆柱体
    
    参数:
        radius: 圆柱半径（Blender单位）
        height: 圆柱高度（Blender单位）
        fillet_radius: 圆角半径（Blender单位）
        scale: 缩放因子（Blender单位到毫米）
        num_segments: 圆周分段数
        num_fillet_segments: 圆角分段数
    """
    print(f"  圆柱半径: {radius * scale:.2f} mm")
    print(f"  圆柱高度: {height * scale:.2f} mm")
    print(f"  圆角半径: {fillet_radius * scale:.2f} mm")
    
    vertices = []
    faces = []
    
    r = radius * scale
    h = height * scale
    fr = fillet_radius * scale
    
    # 底部圆周顶点 (z = 0)
    for i in range(num_segments):
        angle = 2 * math.pi * i / num_segments
        x = r * math.cos(angle)
        y = r * math.sin(angle)
        vertices.append([x, y, 0.0])
    
    # 圆角前的圆柱侧面顶点 (z = h - fr)
    for i in range(num_segments):
        angle = 2 * math.pi * i / num_segments
        x = r * math.cos(angle)
        y = r * math.sin(angle)
        vertices.append([x, y, h - fr])
    
    # 圆角部分的顶点（多段圆弧）
    fillet_layers = []
    for j in range(num_fillet_segments + 1):
        layer_vertices = []
        t = j / num_fillet_segments
        angle_fillet = math.pi / 2 * t
        
        z_offset = fr * math.sin(angle_fillet)
        r_offset = fr * (1 - math.cos(angle_fillet))
        
        for i in range(num_segments):
            angle = 2 * math.pi * i / num_segments
            x = (r - r_offset) * math.cos(angle)
            y = (r - r_offset) * math.sin(angle)
            vertices.append([x, y, h - fr + z_offset])
            layer_vertices.append(len(vertices) - 1)
        
        fillet_layers.append(layer_vertices)
    
    # 顶面中心点
    center_top_idx = len(vertices)
    vertices.append([0, 0, h])
    
    # 底面中心点
    center_bottom_idx = len(vertices)
    vertices.append([0, 0, 0])
    
    # 创建面
    # 1. 底面
    for i in range(num_segments):
        next_i = (i + 1) % num_segments
        faces.append([center_bottom_idx, i, next_i])
    
    # 2. 圆柱侧面（底部到圆角前）
    for i in range(num_segments):
        next_i = (i + 1) % num_segments
        bottom_idx = i
        top_idx = num_segments + i
        next_bottom_idx = next_i
        next_top_idx = num_segments + next_i
        faces.append([bottom_idx, top_idx, next_top_idx, next_bottom_idx])
    
    # 3. 圆角面（多段圆弧）
    for j in range(num_fillet_segments):
        layer1 = fillet_layers[j]
        layer2 = fillet_layers[j + 1]
        for i in range(num_segments):
            next_i = (i + 1) % num_segments
            v1 = layer1[i]
            v2 = layer2[i]
            v3 = layer2[next_i]
            v4 = layer1[next_i]
            faces.append([v1, v2, v3, v4])
    
    # 4. 顶面
    top_layer = fillet_layers[-1]
    for i in range(num_segments):
        next_i = (i + 1) % num_segments
        faces.append([center_top_idx, top_layer[i], top_layer[next_i]])
    
    return {
        "name": "Fillet_Cylinder",
        "vertices": vertices,
        "faces": faces,
        "scale": scale
    }

def test_export(obj, output_file, description):
    """导出测试"""
    print(f"\n导出 {description}...")
    
    scene_data = [obj]
    
    result = step_exporter.export_scene_enhanced(
        output_file,
        scene_data,
        1.0,
        1,
        1,
        0,
        "AP214IS",
        "mm",
        1,
        0.001,
        0,
        None
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
    print("测试顶部带倒角的圆柱体导出")
    print("="*60)
    
    test_cases = [
        ("斜角圆柱(45度倒角)", lambda: create_chamfered_cylinder(radius=1.0, height=2.0, chamfer_size=0.1)),
        ("圆角圆柱", lambda: create_fillet_cylinder(radius=1.0, height=2.0, fillet_radius=0.1)),
    ]
    
    results = []
    
    for name, create_func in test_cases:
        print(f"\n创建 {name}...")
        obj = create_func()
        
        if obj is None:
            results.append((name, False, "创建失败"))
            continue
        
        output_file = os.path.join(os.path.dirname(__file__), f"test_{name.replace('(', '_').replace(')', '_').replace('度', 'deg')}.step")
        
        success = test_export(obj, output_file, name)
        
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
