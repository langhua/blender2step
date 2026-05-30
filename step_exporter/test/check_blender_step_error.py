"""
Blender 网格 vs STEP 导出模型 - 尺寸误差检测工具

功能：
1. 从 Blender 获取网格的边界框尺寸
2. 从 STEP 文件提取几何尺寸
3. 计算并报告尺寸差异

用法：
  在 Blender Python 控制台中运行：
  exec(open(r"F:\git\blender2step\step_exporter\test\check_blender_step_error.py").read())
  check_error()
  
  或指定 STEP 文件：
  check_error(step_file=r"path\to\model.step")
"""

import bpy
import os
import re
import math
from mathutils import Vector

def get_blender_mesh_dimensions(obj=None):
    """获取 Blender 网格对象的边界框尺寸"""
    if obj is None:
        obj = bpy.context.active_object
    
    if obj is None or obj.type != 'MESH':
        print("错误：请选择一个网格对象")
        return None
    
    # 获取评估后的对象（应用修改器）
    depsgraph = bpy.context.evaluated_depsgraph_get()
    eval_obj = obj.evaluated_get(depsgraph)
    mesh = eval_obj.data
    
    # 计算世界坐标系中的边界框
    bbox_corners = [obj.matrix_world @ Vector(corner) for corner in obj.bound_box]
    
    min_x = min(v.x for v in bbox_corners)
    max_x = max(v.x for v in bbox_corners)
    min_y = min(v.y for v in bbox_corners)
    max_y = max(v.y for v in bbox_corners)
    min_z = min(v.z for v in bbox_corners)
    max_z = max(v.z for v in bbox_corners)
    
    dimensions = {
        'name': obj.name,
        'min': (min_x, min_y, min_z),
        'max': (max_x, max_y, max_z),
        'size': (max_x - min_x, max_y - min_y, max_z - min_z),
        'center': ((min_x + max_x) / 2, (min_y + max_y) / 2, (min_z + max_z) / 2)
    }
    
    return dimensions

def parse_step_file_dimensions(step_file, scale_factor=1.0):
    """解析 STEP 文件并提取边界框尺寸
    
    参数：
        step_file: STEP 文件路径
        scale_factor: 缩放因子（如果 STEP 文件使用了缩放）
    """
    if not os.path.exists(step_file):
        print(f"错误：STEP 文件不存在: {step_file}")
        return None
    
    with open(step_file, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()
    
    # 提取所有 CARTESIAN_POINT 坐标
    point_pattern = r'#(\d+)\s*=\s*CARTESIAN_POINT\s*\([^)]*,\s*\(\s*([-+]?\d*\.?\d+(?:[eE][-+]?\d+)?)\s*,\s*([-+]?\d*\.?\d+(?:[eE][-+]?\d+)?)\s*,\s*([-+]?\d*\.?\d+(?:[eE][-+]?\d+)?)\s*\)'
    
    points = []
    for match in re.finditer(point_pattern, content):
        x = float(match.group(2)) * scale_factor
        y = float(match.group(3)) * scale_factor
        z = float(match.group(4)) * scale_factor
        points.append((x, y, z))
    
    if not points:
        print("警告：未在 STEP 文件中找到坐标点")
        return None
    
    # 计算边界框
    min_x = min(p[0] for p in points)
    max_x = max(p[0] for p in points)
    min_y = min(p[1] for p in points)
    max_y = max(p[1] for p in points)
    min_z = min(p[2] for p in points)
    max_z = max(p[2] for p in points)
    
    # 统计曲面类型
    surface_types = {
        'PLANE': len(re.findall(r'PLANE\s*\(', content)),
        'CYLINDRICAL': len(re.findall(r'CYLINDRICAL_SURFACE\s*\(', content)),
        'CONICAL': len(re.findall(r'CONICAL_SURFACE\s*\(', content)),
        'SPHERICAL': len(re.findall(r'SPHERICAL_SURFACE\s*\(', content)),
        'TOROIDAL': len(re.findall(r'TOROIDAL_SURFACE\s*\(', content)),
        'BSPLINE': len(re.findall(r'BSPLINE_SURFACE', content)),
    }
    
    dimensions = {
        'file': os.path.basename(step_file),
        'min': (min_x, min_y, min_z),
        'max': (max_x, max_y, max_z),
        'size': (max_x - min_x, max_y - min_y, max_z - min_z),
        'center': ((min_x + max_x) / 2, (min_y + max_y) / 2, (min_z + max_z) / 2),
        'point_count': len(points),
        'surface_types': surface_types
    }
    
    return dimensions

def calculate_error(blender_dims, step_dims, unit='mm'):
    """计算 Blender 网格与 STEP 模型之间的尺寸误差"""
    if blender_dims is None or step_dims is None:
        print("错误：无法计算误差，缺少尺寸数据")
        return None
    
    blender_size = blender_dims['size']
    step_size = step_dims['size']
    
    # 计算绝对误差
    abs_errors = tuple(abs(b - s) for b, s in zip(blender_size, step_size))
    
    # 计算相对误差（百分比）
    rel_errors = tuple(
        (abs(b - s) / b * 100) if b != 0 else 0 
        for b, s in zip(blender_size, step_size)
    )
    
    # 计算中心位置偏差
    center_error = math.sqrt(sum(
        (b - s) ** 2 
        for b, s in zip(blender_dims['center'], step_dims['center'])
    ))
    
    # 最大误差
    max_abs_error = max(abs_errors)
    max_rel_error = max(rel_errors)
    
    error_report = {
        'blender': blender_dims,
        'step': step_dims,
        'absolute_errors': {
            'X': abs_errors[0],
            'Y': abs_errors[1],
            'Z': abs_errors[2],
            'max': max_abs_error
        },
        'relative_errors': {
            'X': rel_errors[0],
            'Y': rel_errors[1],
            'Z': rel_errors[2],
            'max': max_rel_error
        },
        'center_error': center_error,
        'unit': unit
    }
    
    return error_report

def print_error_report(error_report):
    """打印格式化的误差报告"""
    if error_report is None:
        print("错误：无效的误差报告")
        return
    
    blender = error_report['blender']
    step = error_report['step']
    abs_err = error_report['absolute_errors']
    rel_err = error_report['relative_errors']
    unit = error_report['unit']
    
    print("\n" + "="*80)
    print("Blender 网格 vs STEP 模型 - 尺寸误差报告")
    print("="*80)
    
    print(f"\nBlender 模型: {blender['name']}")
    print(f"STEP 文件: {step['file']}")
    
    print(f"\n{'维度':<10} {'Blender':<15} {'STEP':<15} {'绝对误差':<15} {'相对误差':<15}")
    print("-"*80)
    
    for i, axis in enumerate(['X', 'Y', 'Z']):
        print(f"{axis:<10} {blender['size'][i]:<15.4f} {step['size'][i]:<15.4f} "
              f"{abs_err[axis]:<15.6f} {rel_err[axis]:<15.4f}%")
    
    print("-"*80)
    print(f"{'最大误差':<10} {'':<15} {'':<15} {abs_err['max']:<15.6f} {rel_err['max']:<15.4f}%")
    print(f"中心位置偏差: {error_report['center_error']:.6f} {unit}")
    
    # 打印 STEP 文件信息
    print(f"\nSTEP 文件详细信息:")
    print(f"  顶点数量: {step['point_count']}")
    print(f"  曲面类型统计:")
    for surf_type, count in step['surface_types'].items():
        if count > 0:
            print(f"    {surf_type}: {count}")
    
    # 误差评估
    print(f"\n误差评估:")
    if abs_err['max'] < 0.001:
        print("  ✓ 优秀 - 最大误差 < 0.001 mm")
    elif abs_err['max'] < 0.01:
        print("  ✓ 良好 - 最大误差 < 0.01 mm")
    elif abs_err['max'] < 0.1:
        print("  ⚠ 可接受 - 最大误差 < 0.1 mm")
    elif abs_err['max'] < 1.0:
        print("  ⚠ 注意 - 最大误差 < 1.0 mm")
    else:
        print("  ✗ 较差 - 最大误差 >= 1.0 mm")
    
    print("="*80 + "\n")

def check_error(step_file=None, obj=None, scale=1.0):
    """主函数：检查 Blender 网格与 STEP 模型的误差
    
    参数：
        step_file: STEP 文件路径（可选，默认查找最新的 .step 文件）
        obj: Blender 对象（可选，默认使用活动对象）
        scale: 缩放因子（Blender 单位到 STEP 单位的转换，默认 1.0）
    """
    print("\n" + "="*80)
    print("开始检查 Blender 网格与 STEP 模型的尺寸误差")
    print("="*80)
    
    # 1. 获取 Blender 网格尺寸
    print("\n步骤 1: 获取 Blender 网格尺寸...")
    blender_dims = get_blender_mesh_dimensions(obj)
    if blender_dims is None:
        return None
    
    print(f"  对象: {blender_dims['name']}")
    print(f"  尺寸 (X, Y, Z): {blender_dims['size']}")
    
    # 2. 查找或验证 STEP 文件
    if step_file is None:
        # 查找工作目录中的 STEP 文件
        test_dir = r"F:\git\blender2step\step_exporter\test"
        step_files = [f for f in os.listdir(test_dir) if f.endswith('.step')]
        if step_files:
            step_files.sort(key=lambda f: os.path.getmtime(os.path.join(test_dir, f)), reverse=True)
            step_file = os.path.join(test_dir, step_files[0])
            print(f"\n  使用最新的 STEP 文件: {step_file}")
        else:
            print("\n  错误：未找到 STEP 文件")
            print("  请先导出 STEP 文件，或指定文件路径")
            return None
    
    # 3. 解析 STEP 文件尺寸
    print(f"\n步骤 2: 解析 STEP 文件...")
    step_dims = parse_step_file_dimensions(step_file, scale_factor=scale)
    if step_dims is None:
        return None
    
    print(f"  文件: {step_dims['file']}")
    print(f"  尺寸 (X, Y, Z): {step_dims['size']}")
    print(f"  顶点数量: {step_dims['point_count']}")
    
    # 4. 计算误差
    print(f"\n步骤 3: 计算尺寸误差...")
    error_report = calculate_error(blender_dims, step_dims)
    
    # 5. 打印报告
    print_error_report(error_report)
    
    return error_report

def export_and_check(filename=None, scale=1000.0):
    """导出当前对象为 STEP 并立即检查误差
    
    参数：
        filename: 输出文件名（可选）
        scale: 缩放因子（默认 1000.0，即 Blender 单位转毫米）
    """
    import sys
    sys.path.insert(0, r"F:\git\blender2step\step_exporter")
    
    obj = bpy.context.active_object
    if obj is None or obj.type != 'MESH':
        print("错误：请选择一个网格对象")
        return None
    
    # 生成文件名
    if filename is None:
        filename = f"{obj.name}_error_check.step"
    
    if not filename.endswith('.step'):
        filename += '.step'
    
    output_path = os.path.join(r"F:\git\blender2step\step_exporter\test", filename)
    
    # 获取网格数据
    depsgraph = bpy.context.evaluated_depsgraph_get()
    eval_obj = obj.evaluated_get(depsgraph)
    mesh = eval_obj.data
    
    vertices = []
    for vert in mesh.vertices:
        world_co = eval_obj.matrix_world @ vert.co
        vertices.append([float(world_co.x) * scale, float(world_co.y) * scale, float(world_co.z) * scale])
    
    mesh.calc_loop_triangles()
    faces = []
    for tri in mesh.loop_triangles:
        faces.append(list(tri.vertices))
    
    obj_data = {
        'name': obj.name,
        'type': 'mesh',
        'vertices': vertices,
        'faces': faces,
    }
    
    # 导出 STEP
    print(f"\n导出 STEP 文件: {output_path}")
    try:
        import _step_exporter as cpp_exporter
        
        result = cpp_exporter.export_scene_enhanced(
            output_path,
            [obj_data],
            scale,
            1,  # fix_geometry
            1,  # create_solid
            1,  # advanced_brep
            2,  # step_schema (AP214IS)
            2,  # unit (MILLIMETER)
            0.001,  # sewing_tolerance
            1  # enable_logging
        )
        
        if result:
            print(f"✓ 导出成功")
            # 立即检查误差
            return check_error(step_file=output_path, obj=obj, scale=1.0)
        else:
            print("✗ 导出失败")
            return None
            
    except Exception as e:
        print(f"✗ 导出过程中出错: {e}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == '__main__':
    # 如果在 Blender 外部运行，需要指定文件
    print("此脚本应在 Blender Python 控制台中运行")
    print("用法: exec(open(r'F:\\git\\blender2step\\step_exporter\\test\\check_blender_step_error.py').read())")
    print("      check_error()")
    print("      或 export_and_check() 直接导出并检查")
