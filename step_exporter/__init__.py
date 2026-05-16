"""
STEP Exporter for Blender (Enhanced)
Version 4.1.1 with advanced BREP and solid creation support
"""

bl_info = {
    "name": "STEP Exporter (Enhanced)",
    "author": "Blender STEP Exporter",
    "version": (4, 1, 2),
    "blender": (4, 2, 1),
    "location": "File > Export > STEP (Enhanced)",
    "description": "Export to STEP format with advanced BREP, solid creation and geometry fixing",
    "category": "Import-Export",
}



import sys
import os
import math
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

import bpy
from bpy.types import Operator, Panel
from bpy_extras.io_utils import ExportHelper
from bpy.props import StringProperty, FloatProperty, BoolProperty, EnumProperty

# 进度报告系统
from .progress_report import (
                             start_progress, update_progress, end_progress,
                             register as register_progress, unregister as unregister_progress)

# 全局变量，用于存储导出参数和状态
_export_params = None
_export_stage = 0  # 0=未开始，1=准备数据，2=调用 C++，3=完成
_export_objects = []
_export_objects_data = []
_export_current_index = 0
_cpp_progress = -1.0  # 存储 C++ 回调传递的进度
_export_log_file = None  # 日志文件句柄
_cpp_log_callback = None  # C++日志回调函数

def log_to_file(msg):
    """输出到日志文件"""
    if _export_log_file and not _export_log_file.closed:
        if not msg.endswith("\n"):
            _export_log_file.write(msg + "\n")
        else:
            _export_log_file.write(msg)
        _export_log_file.flush()

# ====================== C++ 模块加载检查 ======================

# 初始化模块状态变量
CPP_MODULE_LOADED = False
step_exporter = None
MODULE_LOAD_ERROR = ""

# 尝试加载 C++ 扩展模块
try:
    # 显式添加当前脚本所在目录到 Python 路径
    script_dir = os.path.dirname(os.path.realpath(__file__))
    if script_dir not in sys.path:
        sys.path.insert(0, script_dir)
    
    # 添加 lib 目录到系统 PATH 环境变量，确保 Windows 能找到依赖的 DLL
    lib_path = os.path.join(script_dir, "lib")
    if os.path.exists(lib_path):
        os.environ["PATH"] = lib_path + ";" + os.environ.get("PATH", "")
        print(f"[STEP Exporter] Added lib path to system PATH: {lib_path}")
    
    # 优先从 lib 子目录导入
    try:
        if os.path.exists(lib_path) and lib_path not in sys.path:
            sys.path.insert(0, lib_path)
        import _step_exporter as step_exporter_lib
        step_exporter = step_exporter_lib
        
        if hasattr(step_exporter, 'get_version'):
            module_version = step_exporter.get_version()
            print(f"[STEP Exporter] [OK] C++ extension module loaded successfully (from lib)")
            print(f"[STEP Exporter] Module version: {module_version}")
            CPP_MODULE_LOADED = True
        else:
            MODULE_LOAD_ERROR = "C++ module from lib missing required functions"
            print(f"[STEP Exporter] ✗ C++ module from lib missing functions")
            
    except ImportError as e2:
        MODULE_LOAD_ERROR = f"ImportError from lib: {str(e2)}"
        print(f"[STEP Exporter] ✗ Failed to import C++ module from lib: {e2}")
        
        # 尝试直接导入作为后备
        try:
            import _step_exporter
            step_exporter = _step_exporter
            
            if hasattr(step_exporter, 'get_version'):
                module_version = step_exporter.get_version()
                print(f"[STEP Exporter] [OK] C++ extension module loaded successfully (direct import)")
                print(f"[STEP Exporter] Module version: {module_version}")
                CPP_MODULE_LOADED = True
            else:
                MODULE_LOAD_ERROR = "C++ module missing required functions"
                print(f"[STEP Exporter] [ERROR] C++ module loaded but missing functions")
                
        except ImportError as e:
            MODULE_LOAD_ERROR = f"ImportError: {str(e)}"
            print(f"[STEP Exporter] [ERROR] Failed to import C++ module directly: {e}")
            
except Exception as e:
    MODULE_LOAD_ERROR = f"Unexpected error: {str(e)}"
    print(f"[STEP Exporter] ✗ Unexpected error loading C++ module: {e}")

# ====================== 导出工作器函数 ======================

def _get_mesh_data_enhanced(obj, context, scale, apply_modifiers=True):
    """获取网格数据（增强版，包含更多检查和信息）"""
    if obj.type != 'MESH':
        return None
    
    import sys
    log_to_file(f"[Python DEBUG] get_mesh_data_enhanced called for object '{obj.name}'")
    sys.stdout.flush()
    mesh = obj.data
    
    # 检查原始顶点坐标
    log_to_file(f"[Python DEBUG] Original mesh vertex count: {len(mesh.vertices)}")
    if len(mesh.vertices) > 0:
        for i in range(min(5, len(mesh.vertices))):
            v = mesh.vertices[i]
            log_to_file(f"[Python DEBUG] Original vertex {i}: ({v.co.x}, {v.co.y}, {v.co.z})")
    
    # 获取最终几何（应用修改器）
    depsgraph = context.evaluated_depsgraph_get() if apply_modifiers else None
    if depsgraph:
        eval_obj = obj.evaluated_get(depsgraph)
        eval_mesh = eval_obj.data
    else:
        eval_obj = obj
        eval_mesh = mesh
    
    # 确保是三角网格
    if not eval_mesh.loop_triangles:
        eval_mesh.calc_loop_triangles()
    
    # 获取顶点（应用世界变换）
    vertices = []
    zero_vertex_count = 0
    for idx, vert in enumerate(eval_mesh.vertices):
        world_co = eval_obj.matrix_world @ vert.co
        vertex_scaled = [round(float(world_co.x) * scale, 12), round(float(world_co.y) * scale, 12), round(float(world_co.z) * scale, 12)]
        vertices.append(vertex_scaled)
        
        # 检查顶点是否为零
        if abs(world_co.x) < 1e-12 and abs(world_co.y) < 1e-12 and abs(world_co.z) < 1e-12:
            zero_vertex_count += 1
        
        # 详细调试前 5 个顶点
        if idx < 5:
            log_to_file(f"[Python DEBUG] Vertex {idx}:")
            log_to_file(f"  Local co: ({vert.co.x}, {vert.co.y}, {vert.co.z})")
            log_to_file(f"  World co: ({world_co.x}, {world_co.y}, {world_co.z})")
            log_to_file(f"  Scaled: ({vertex_scaled[0]}, {vertex_scaled[1]}, {vertex_scaled[2]})")
            log_to_file(f"  Matrix: {eval_obj.matrix_world}")
    
    # 调试：打印统计信息
    log_to_file(f"[Python DEBUG] Object '{obj.name}' vertex analysis:")
    log_to_file(f"  Total vertices: {len(vertices)}")
    log_to_file(f"  Zero world-co vertices: {zero_vertex_count}")
    log_to_file(f"  Scale factor: {scale}")
    log_to_file(f"  Matrix world: {eval_obj.matrix_world}")
    import sys
    sys.stdout.flush()
    
    # 如果所有顶点都为零，打印严重警告
    if zero_vertex_count == len(vertices) and len(vertices) > 0:
        log_to_file(f"[Python WARNING] ALL vertices have zero world coordinates! Check object transform and mesh data.")
        sys.stdout.flush()
    
    # 获取三角面
    faces = []
    for tri in eval_mesh.loop_triangles:
        face_vertices = [tri.vertices[0], tri.vertices[1], tri.vertices[2]]
        faces.append(face_vertices)
    
    # 获取法线
    normals = []
    for tri in eval_mesh.loop_triangles:
        face_normal = tri.normal
        normals.append([float(face_normal.x), float(face_normal.y), float(face_normal.z)])
    
    sys.stdout.flush()
    
    result = {
        'name': obj.name,
        'type': 'mesh',
        'vertices': vertices,
        'faces': faces,
        'normals': normals,
        'matrix_world': list(eval_obj.matrix_world),
    }

    top_fillet_radius = obj.get("step_top_fillet_radius", 0.0)
    if top_fillet_radius > 0:
        result['top_fillet_radius'] = float(top_fillet_radius)

    return result

def _get_curve_data_enhanced(obj, context, scale, apply_modifiers=True):
    """获取曲线数据（增强版）- 使用spline数据直接导出曲线"""
    if obj.type != 'CURVE':
        return None
    
    import sys
    import math
    log_to_file(f"[Python DEBUG] get_curve_data_enhanced called for object '{obj.name}'")
    sys.stdout.flush()
    
    curve = obj.data
    
    depsgraph = context.evaluated_depsgraph_get() if apply_modifiers else None
    if depsgraph:
        eval_obj = obj.evaluated_get(depsgraph)
        eval_curve = eval_obj.data
    else:
        eval_obj = obj
        eval_curve = curve
    
    splines_data = []
    
    for spline_idx, spline in enumerate(eval_curve.splines):
        spline_type = spline.type
        log_to_file(f"[Python DEBUG] Processing spline {spline_idx}: type={spline_type}")
        
        order_u = getattr(spline, 'order_u', 4)
        if spline_type == 'NURBS' and order_u < 4:
            order_u = 4
        elif order_u < 3:
            order_u = 4
        
        spline_info = {
            'type': spline_type,
            'order': order_u,
            'resolution_u': spline.resolution_u,
            'use_cyclic_u': spline.use_cyclic_u,
            'use_endpoint_u': spline.use_endpoint_u,
        }
        
        control_points = []
        weights = []
        
        if spline_type == 'POLY' or spline_type == 'NURBS':
            points = spline.points
            for point in points:
                local_co = point.co
                world_co = eval_obj.matrix_world @ local_co.to_3d()
                scaled_co = [round(float(world_co.x) * scale, 12),
                             round(float(world_co.y) * scale, 12),
                             round(float(world_co.z) * scale, 12)]
                control_points.append(scaled_co)
                weights.append(float(point.weight))
            
            spline_info['control_points'] = control_points
            if spline_type == 'NURBS':
                spline_info['weights'] = weights
            else:
                spline_info['weights'] = [1.0] * len(weights)
            
            if spline_type == 'NURBS':
                for attr in ['knots_u', 'knots', 'knot_vector']:
                    if hasattr(spline, attr):
                        val = getattr(spline, attr)
                        if val:
                            spline_info['knots_u'] = [float(k) for k in val]
                            break
                else:
                    num_control_points = len(control_points)
                    order = spline_info['order']
                    if spline_type == 'NURBS' and order < 4:
                        order = 4
                    degree = order - 1
                    num_knots = num_control_points + order
                    
                    if spline.use_cyclic_u:
                        knots = [float(i) for i in range(num_knots)]
                    else:
                        n = num_control_points - 1
                        knots = []
                        for i in range(num_knots):
                            if i < order:
                                knots.append(0.0)
                            elif i >= num_knots - order:
                                knots.append(float(n - degree + 1))
                            else:
                                knots.append(float(i - order + 1))
                    
                    spline_info['knots_u'] = knots
        
        elif spline_type == 'BEZIER':
            points = spline.bezier_points
            close_curve = spline.use_cyclic_u
            original_close_curve = close_curve
            
            control_points = []
            weights = []
            
            num_segments = len(points) - 1 if not close_curve else len(points)
            
            segment_controls = []
            for seg_idx in range(num_segments):
                if close_curve:
                    start_idx = seg_idx
                    end_idx = (seg_idx + 1) % len(points)
                else:
                    start_idx = seg_idx
                    end_idx = seg_idx + 1
                
                bp_start = points[start_idx]
                bp_end = points[end_idx]
                
                seg_points = []
                for bp, handle_attr in [(bp_start, 'co'),
                                        (bp_start, 'handle_right'),
                                        (bp_end, 'handle_left'),
                                        (bp_end, 'co')]:
                    if handle_attr == 'co':
                        local_co = bp.co
                    else:
                        local_co = getattr(bp, handle_attr)
                    world_co = eval_obj.matrix_world @ local_co
                    scaled_co = [round(float(world_co.x) * scale, 12),
                                 round(float(world_co.y) * scale, 12),
                                 round(float(world_co.z) * scale, 12)]
                    seg_points.append(scaled_co)
                segment_controls.append(seg_points)
            
            for seg_idx, seg_points in enumerate(segment_controls):
                if seg_idx == 0:
                    control_points.extend(seg_points)
                    weights.extend([1.0, 1.0, 1.0, 1.0])
                else:
                    control_points.extend(seg_points[1:])
                    weights.extend([1.0, 1.0, 1.0])
            
            if close_curve:
                control_points.append(control_points[0])
                weights.append(weights[0])
                close_curve = False
            
            spline_info['type'] = 'NURBS'
            spline_info['order'] = 4
            spline_info['control_points'] = control_points
            spline_info['weights'] = weights
            spline_info['use_cyclic_u'] = close_curve
            
            n = len(control_points) - 1
            order = 4
            num_knots = n + order + 1
            
            if close_curve:
                degree = order - 1
                unique_knot_count = len(control_points) - degree + 3
                unique_knots = [i / (unique_knot_count - 1) for i in range(unique_knot_count)]
                knots = [0.0] * degree
                knots.extend(unique_knots[1:-1])
                knots.extend([1.0] * degree)
            else:
                knots = []
                for i in range(num_knots):
                    if i < order:
                        knots.append(0.0)
                    elif i > n:
                        knots.append(float(n - order + 2))
                    else:
                        knots.append(float(i - order + 1))
                if knots[-1] > 0:
                    max_knot = knots[-1]
                    knots = [k / max_knot for k in knots]
            
            spline_info['knots_u'] = knots
            
            if "BezierCircle" in obj.name and len(points) == 4 and original_close_curve:
                bezier_points = points
                world_coords = []
                for bp in bezier_points:
                    local_co = bp.co
                    world_co = obj.matrix_world @ local_co
                    scaled_co = [float(world_co.x) * scale, float(world_co.y) * scale, float(world_co.z) * scale]
                    world_coords.append(scaled_co)
                
                center_x = sum(wc[0] for wc in world_coords) / len(world_coords)
                center_y = sum(wc[1] for wc in world_coords) / len(world_coords)
                center_z = sum(wc[2] for wc in world_coords) / len(world_coords)
                radius = max(math.sqrt((wc[0] - center_x)**2 + (wc[1] - center_y)**2 + (wc[2] - center_z)**2) for wc in world_coords)
                
                angles = [0, math.pi/4, math.pi/2, 3*math.pi/4, math.pi, 5*math.pi/4, 3*math.pi/2, 7*math.pi/4, 2*math.pi]
                control_points = []
                for angle in angles:
                    x = center_x + radius * math.cos(angle)
                    y = center_y + radius * math.sin(angle)
                    control_points.append([round(x, 12), round(y, 12), round(center_z, 12)])
                
                sqrt2_over_2 = math.sqrt(2) / 2
                weights = [1.0, sqrt2_over_2, 1.0, sqrt2_over_2, 1.0, sqrt2_over_2, 1.0, sqrt2_over_2, 1.0]
                
                order = 4
                degree = order - 1
                unique_knot_count = len(control_points) - degree + 3
                unique_knots = [i / (unique_knot_count - 1) for i in range(unique_knot_count)]
                knots = [0.0] * degree
                knots.extend(unique_knots[1:-1])
                knots.extend([1.0] * degree)
                
                spline_info['control_points'] = control_points
                spline_info['weights'] = weights
                spline_info['knots_u'] = knots
                spline_info['order'] = 4
                spline_info['use_cyclic_u'] = True
                spline_info['circle_center'] = [center_x, center_y, center_z]
                spline_info['circle_radius'] = radius
        
        splines_data.append(spline_info)
    
    if not splines_data:
        log_to_file(f"[Python] Skipping curve object '{obj.name}': no valid splines.")
        return None
    
    log_to_file(f"[Python] Prepared curve '{obj.name}': {len(splines_data)} splines")
    
    return {
        'name': obj.name,
        'type': 'curve',
        'splines': splines_data,
        'dimensions': curve.dimensions,
        'resolution_u': curve.resolution_u,
        'extrude': float(curve.extrude) * scale,
        'bevel_depth': float(curve.bevel_depth) * scale,
    }

def _analyze_bottom_shell_from_mesh(obj, context, scale):
    """
    从 mesh 分析识别是否为底壳类型，并测量所有参数
    
    返回:
        dict: 包含底壳参数的字典，如果不是底壳则返回 None
    """
    if obj.type != 'MESH':
        return None
    
    import bmesh
    from collections import defaultdict
    
    log_to_file(f"[STEP Exporter] Analyzing mesh for bottom shell: {obj.name}")
    
    depsgraph = context.evaluated_depsgraph_get()
    eval_obj = obj.evaluated_get(depsgraph)
    mesh_data = eval_obj.data
    
    bm = bmesh.new()
    bm.from_mesh(mesh_data)
    bm.verts.ensure_lookup_table()
    
    vertices = bm.verts
    if len(vertices) < 100:
        log_to_file(f"[STEP Exporter] Too few vertices ({len(vertices)}), not a bottom shell")
        bm.free()
        return None
    
    z_layers = defaultdict(list)
    for v in vertices:
        z_key = round(v.co.z / 0.01) * 0.01
        z_layers[z_key].append(v)
    
    sorted_z_levels = sorted(z_layers.keys())
    
    if len(sorted_z_levels) < 5:
        log_to_file(f"[STEP Exporter] Not enough z-levels ({len(sorted_z_levels)}), not a bottom shell")
        bm.free()
        return None
    
    min_z = sorted_z_levels[0]
    max_z = sorted_z_levels[-1]
    total_height = max_z - min_z
    
    log_to_file(f"[STEP Exporter] z=[{min_z:.3f}, {max_z:.3f}], height={total_height:.3f}, levels={len(sorted_z_levels)}")
    
    bottom_z = sorted_z_levels[0]
    bottom_verts = z_layers[bottom_z]
    top_z = sorted_z_levels[-1]
    top_verts = z_layers[top_z]
    
    if len(bottom_verts) < 50 or len(top_verts) < 50:
        log_to_file(f"[STEP Exporter] No clear bottom/top planes, not a bottom shell")
        bm.free()
        return None
    
    total_levels = len(sorted_z_levels)
    outer_wall_start_z = None
    
    for i in range(1, len(sorted_z_levels)):
        gap = sorted_z_levels[i] - sorted_z_levels[i-1]
        levels_after = total_levels - i
        if levels_after < total_levels * 0.25 and gap > 0.1:
            outer_wall_start_z = sorted_z_levels[i-1]
            break
    
    if outer_wall_start_z is None:
        outer_wall_start_z = sorted_z_levels[-2] if len(sorted_z_levels) > 1 else sorted_z_levels[-1]
    
    outer_fillet_radius = outer_wall_start_z - bottom_z
    
    inner_bottom_z = None
    max_vertex_count = 0
    
    for z_level in sorted_z_levels[1:]:
        if z_level > bottom_z + 0.5 and z_level < outer_wall_start_z:
            vertex_count = len(z_layers[z_level])
            if vertex_count > max_vertex_count:
                max_vertex_count = vertex_count
                inner_bottom_z = z_level
    
    if inner_bottom_z is None:
        log_to_file(f"[STEP Exporter] Could not find inner bottom, not a bottom shell")
        bm.free()
        return None
    
    inner_wall_start_z = None
    max_gap = 0
    
    for i in range(1, len(sorted_z_levels)):
        if sorted_z_levels[i-1] >= inner_bottom_z:
            gap = sorted_z_levels[i] - sorted_z_levels[i-1]
            if gap > max_gap:
                max_gap = gap
                inner_wall_start_z = sorted_z_levels[i-1]
    
    if inner_wall_start_z is None:
        inner_wall_start_z = outer_wall_start_z
    
    inner_fillet_radius = inner_wall_start_z - inner_bottom_z
    
    outer_wall_verts = z_layers.get(outer_wall_start_z, bottom_verts)
    outer_x_coords = [v.co.x for v in outer_wall_verts]
    outer_y_coords = [v.co.y for v in outer_wall_verts]
    
    width = max(outer_x_coords) - min(outer_x_coords)
    depth = max(outer_y_coords) - min(outer_y_coords)
    outer_height = total_height
    bottom_thickness = inner_bottom_z - bottom_z
    
    inner_bottom_verts = z_layers[inner_bottom_z]
    center_nearby = [v for v in inner_bottom_verts if abs(v.co.x) < width * 0.1 and abs(v.co.y) < depth * 0.1]
    if len(center_nearby) < 1:
        log_to_file(f"[STEP Exporter] Inner bottom has no center vertices (ring, not face), not a bottom shell")
        bm.free()
        return None
    
    if inner_bottom_z > min_z + total_height * 0.4:
        log_to_file(f"[STEP Exporter] Inner bottom too high (z={inner_bottom_z:.1f}, {inner_bottom_z - min_z:.1f}/{total_height:.1f}), not a bottom shell")
        bm.free()
        return None
    
    half_w = width / 2
    half_d = depth / 2
    
    corner_radius = 0.0
    corner_verts = [v for v in outer_wall_verts if abs(v.co.x) > half_w * 0.6 and abs(v.co.y) > half_d * 0.6]
    if corner_verts:
        for v in corner_verts:
            dx = half_w - abs(v.co.x)
            dy = half_d - abs(v.co.y)
            if dx > 0 and dy > 0:
                dist = math.sqrt(dx*dx + dy*dy)
                if dist > corner_radius:
                    corner_radius = dist
        corner_radius = corner_radius * 1.05
    if corner_radius < 1.0:
        corner_radius = min(width, depth) * 0.2
    
    outer_dists = [math.sqrt(v.co.x**2 + v.co.y**2) for v in outer_wall_verts]
    if outer_dists:
        min_dist = min(outer_dists)
        max_dist = max(outer_dists)
        if max_dist > 0 and min_dist / max_dist > 0.85:
            log_to_file(f"[STEP Exporter] Cross-section too circular (ratio={min_dist/max_dist:.2f}), not a bottom shell")
            bm.free()
            return None
    
    wall_thickness = 2.0
    
    top_verts = z_layers.get(max_z, [])
    if top_verts:
        flat_x_outer = max(abs(v.co.x) for v in top_verts if abs(v.co.y) < depth * 0.15)
        flat_x_inner = max(abs(v.co.x) for v in top_verts if abs(v.co.y) < depth * 0.15 and abs(v.co.x) < half_w * 0.98)
        flat_y_outer = max(abs(v.co.y) for v in top_verts if abs(v.co.x) < width * 0.15)
        flat_y_inner = max(abs(v.co.y) for v in top_verts if abs(v.co.x) < width * 0.15 and abs(v.co.y) < half_d * 0.98)
        
        if flat_x_inner > 0 and flat_y_inner > 0:
            wall_thickness_x = flat_x_outer - flat_x_inner
            wall_thickness_y = flat_y_outer - flat_y_inner
            wall_thickness = (wall_thickness_x + wall_thickness_y) / 2
    
    if wall_thickness < 0.5:
        wall_thickness = 2.0
    
    log_to_file(f"[STEP Exporter] Detected bottom shell: {width:.1f}x{depth:.1f} h={outer_height:.1f} bt={bottom_thickness:.1f} wt={wall_thickness:.1f} cr={corner_radius:.1f} ofr={outer_fillet_radius:.1f} ifr={inner_fillet_radius:.1f}")
    
    bm.free()
    
    return {
        'width': width,
        'depth': depth,
        'outer_height': outer_height,
        'bottom_thickness': bottom_thickness,
        'wall_thickness': wall_thickness,
        'corner_radius': corner_radius,
        'outer_fillet_radius': outer_fillet_radius,
        'inner_fillet_radius': inner_fillet_radius,
    }


def _export_worker_timer():
    """导出工作器，在 timer 中运行，分阶段执行"""
    global _export_params, _export_stage, _export_objects, _export_objects_data, _export_current_index, _export_log_file
    
    if not _export_params:
        return None
    
    try:
        params = _export_params
        context = params['context']
        
        # 阶段 1: 准备数据（一次性处理所有对象）
        if _export_stage == 1:
            log_to_file(f"\n[STEP Exporter] Stage 1: Preparing data...")
            
            if params['unit'] == 'mm':
                scale = 1000.0
            else:
                scale = 1.0
            
            for idx, obj in enumerate(_export_objects):
                log_to_file(f"[Python DEBUG] Processing object {idx}: '{obj.name}' (type: {obj.type})")
                
                obj_data = None
                if obj.type == 'MESH':
                    obj_data = _get_mesh_data_enhanced(obj, context, scale, params['apply_modifiers'])
                elif obj.type == 'CURVE':
                    obj_data = _get_curve_data_enhanced(obj, context, scale, params['apply_modifiers'])
                
                if obj_data:
                    _export_objects_data.append(obj_data)
                
                object_progress = ((idx + 1) / len(_export_objects)) * 20
                update_progress(object_progress, f"正在处理对象 {idx+1}/{len(_export_objects)}", context)
            
            _export_stage = 2
            log_to_file(f"[STEP Exporter] Data preparation complete: {len(_export_objects_data)} objects")
            return 0.1
        
        # 阶段 2: 初始化增量导出
        elif _export_stage == 2:
            log_to_file(f"\n[STEP Exporter] Stage 2: Initializing incremental export...")
            
            step_unit = 'MILLIMETER' if params['unit'] == 'mm' else 'METER'
            sew_tolerance_m = params['sew_tolerance']
            
            # 创建日志回调函数，供C++调用以写入日志文件
            global _cpp_log_callback
            _cpp_log_callback = lambda msg: log_to_file(msg)
            
            success = step_exporter.init_incremental_export(
                params['filepath'],
                len(_export_objects_data),
                params['scale'],
                1 if params['fix_geometry'] else 0,
                1 if params['create_solid'] else 0,
                1 if params['advanced_brep'] else 0,
                params['step_schema'],
                step_unit,
                1 if params['enable_logging'] else 0,
                sew_tolerance_m,
                _cpp_log_callback
            )
            
            if not success:
                log_to_file(f"[STEP Exporter] Failed to initialize incremental export")
                update_progress(100, "导出失败", context)
                end_progress(context)
                return None
            
            _export_current_index = 0
            _export_stage = 3
            log_to_file(f"[STEP Exporter] Incremental export initialized")
            return 0.1  # 立即进入下一阶段
        
        # 阶段 3: 逐个添加对象到导出（异步模式）
        elif _export_stage == 3:
            if _export_current_index >= len(_export_objects_data):
                # 所有对象已处理完成，进入阶段 4
                _export_stage = 4
                log_to_file(f"[STEP Exporter] All objects processed, finalizing export...")
                return 0.1
            
            # 创建回调函数更新进度
            def callback(progress):
                # 映射进度：20-100%
                mapped_progress = 20.0 + (progress / 100.0) * 80.0
                update_progress(mapped_progress, f"正在导出对象 {_export_current_index+1}/{len(_export_objects_data)}", context)
            
            obj_data = _export_objects_data[_export_current_index]
            log_to_file(f"[STEP Exporter] Adding object {_export_current_index+1}/{len(_export_objects_data)}: {obj_data.get('name', 'Unknown')}")
            
            success = step_exporter.add_object_to_export(obj_data, callback)
            
            if not success:
                log_to_file(f"[STEP Exporter] Failed to add object {_export_current_index+1}")
            
            _export_current_index += 1
            
            # 更新进度：基于已完成对象数量计算百分比
            # 第一个对象完成后：1/9 = 11.1%，映射到 20-100% 范围 = 20 + 11.1% * 80 = 28.9%
            # 第九个对象完成后：9/9 = 100%，映射到 20-100% 范围 = 20 + 100% * 80 = 100%
            object_progress = (_export_current_index / len(_export_objects_data)) * 80 + 20
            update_progress(object_progress, f"已导出对象 {_export_current_index}/{len(_export_objects_data)}", context)
            
            # 返回 timer 继续处理下一个对象
            return 0.1
        
        # 阶段 4: 完成导出并写入文件
        elif _export_stage == 4:
            log_to_file(f"\n[STEP Exporter] Stage 4: Finalizing export...")
            
            success = step_exporter.finalize_incremental_export()
            
            _export_stage = 5
            
            # 更新进度为 100%
            update_progress(100, "导出完成", context)
            
            # 结束进度条
            end_progress(context)
            
            if success:
                log_to_file(f"[STEP Exporter] Successfully exported {len(_export_objects_data)} object(s)")
            else:
                log_to_file(f"[STEP Exporter] Export failed")
            
            # 关闭日志文件
            if _export_log_file and not _export_log_file.closed:
                _export_log_file.close()
            
            return None  # 停止 timer
        
        # 初始调用，设置阶段 1
        if _export_stage == 0:
            # 打开日志文件
            log_filepath = params['filepath'] + ".log"
            try:
                _export_log_file = open(log_filepath, 'w', encoding='utf-8')
            except Exception as e:
                print(f"[STEP Exporter] Failed to open log file: {e}")
                _export_log_file = None
            
            _export_stage = 1
            return 0.1
            
    except Exception as e:
        error_msg = str(e)
        log_to_file(f"[STEP Exporter] Export error: {error_msg}")
        import traceback
        traceback.print_exc()
        end_progress(context)
        if _export_log_file and not _export_log_file.closed:
            _export_log_file.close()
        return None

# ====================== 导出操作类 ======================

class STEP_EXPORTER_OT_export_enhanced(Operator, ExportHelper):
    """Export to STEP format with advanced BREP and solid creation"""
    bl_idname = "export_scene.step_enhanced"
    bl_label = "Export STEP (Enhanced)"
    bl_description = "Export to STEP format with advanced BREP representation"
    bl_options = {'PRESET', 'UNDO'}
    
    filename_ext = ".step"
    filter_glob: StringProperty(
        default="*.step;*.stp",
        options={'HIDDEN'},
    ) # type: ignore
    
    # 基本参数
    unit: EnumProperty(
        name="Export Unit",
        description="Unit for exported STEP file",
        items=[
            ('mm', "毫米 (mm)", "Export in millimeters (1 Blender unit = 1 mm)"),
            ('m', "米 (m)", "Export in meters (1 Blender unit = 1 m)"),
        ],
        default='mm',
    ) # type: ignore
    
    fix_geometry: BoolProperty(
        name="Fix Geometry",
        description="Enable geometry fixing (repair gaps, small edges, etc.)",
        default=True,
    ) # type: ignore
    
    # 高级 BREP 参数
    create_solid: BoolProperty(
        name="Create Solid",
        description="Attempt to create solid bodies instead of surfaces. Yields better compatibility with CAD software",
        default=True,
    ) # type: ignore
    
    advanced_brep: BoolProperty(
        name="Advanced BREP",
        description="Use advanced BREP representation (includes PCURVE, parametric surfaces). Recommended for best compatibility",
        default=True,
    ) # type: ignore
    
    create_exploded_view: BoolProperty(
        name="Create Exploded View",
        description="Create an exploded view with separated cone face, bottom face, and top face",
        default=False,
    ) # type: ignore
    
    step_schema: EnumProperty(
        name="STEP Schema",
        description="STEP application protocol",
        items=[
            ('AP214DIS', "AP214DIS", "ISO 10303-214 DIS version: Draft International Standard (default)"),
            ('AP214CD', "AP214CD", "ISO 10303-214 Conformance Class D: Core data for automotive mechanical design processes"),
            ('AP214IS', "AP214IS", "ISO 10303-214 IS version: International Standard"),
            ('AP203', "AP203", "ISO 10303-203: Configuration controlled 3D designs of mechanical parts and assemblies (widely supported)"),
            ('AP242DIS', "AP242DIS", "ISO 10303-242 DIS version: Managed model-based 3D engineering"),
        ],
        default='AP214DIS',
    ) # type: ignore
    
    sew_tolerance: FloatProperty(
        name="Sewing Tolerance",
        description="Tolerance for sewing faces together (in meters, will be converted to mm internally). Smaller values = more precise but slower",
        default=0.001,
        min=0.000001,  # 1 micron minimum
        max=1.0,
        precision=6,
        subtype='DISTANCE',
    ) # type: ignore
    
    use_selected: BoolProperty(
        name="Selected Only",
        description="Export only selected objects",
        default=False,
    ) # type: ignore
    
    apply_modifiers: BoolProperty(
        name="Apply Modifiers",
        description="Apply all modifiers before export",
        default=True,
    ) # type: ignore
    
    enable_logging: BoolProperty(
        name="Enable Logging",
        description="Enable detailed logging to console",
        default=True,
    ) # type: ignore
    
    def draw(self, context):
        layout = self.layout
        
        # 状态信息
        box = layout.box()
        box.label(text="Module Status", icon='INFO')
        if CPP_MODULE_LOADED and step_exporter:
            try:
                version = step_exporter.get_version()
                box.label(text=f"C++ module v{version} loaded", icon='CHECKMARK')
            except:
                box.label(text="C++ module loaded", icon='CHECKMARK')
        else:
            box.label(text="C++ extension not loaded", icon='ERROR')
            if MODULE_LOAD_ERROR:
                box.label(text=f"Error: {MODULE_LOAD_ERROR[:50]}...", icon='ERROR')
            box.label(text="Check system console for details", icon='ERROR')
        
        # 基本设置
        box = layout.box()
        box.label(text="Basic Settings", icon='SETTINGS')
        box.prop(self, "unit")
        box.prop(self, "fix_geometry")
        box.prop(self, "use_selected")
        box.prop(self, "apply_modifiers")
        box.prop(self, "enable_logging")
        
        # 高级 BREP 设置
        box = layout.box()
        box.label(text="Advanced BREP & Solid Creation", icon='MOD_SOLIDIFY')
        box.prop(self, "create_solid")
        box.prop(self, "advanced_brep")
        box.prop(self, "create_exploded_view")
        box.prop(self, "step_schema")
        box.prop(self, "sew_tolerance")
        

    
    def execute(self, context):
        if not CPP_MODULE_LOADED or not step_exporter:
            self.report({'ERROR'}, "C++ extension module '_step_exporter' not loaded. Check console for details.")
            return {'CANCELLED'}
        
        # 启动进度条显示
        log_to_file(f"[STEP Exporter] === Calling start_progress ===")
        start_progress(context)
        
        # 启动 modal operator 来显示进度条
        log_to_file(f"[STEP Exporter] === Checking if bpy.ops.step_exporter exists ===")
        if hasattr(bpy.ops, 'step_exporter'):
            log_to_file(f"[STEP Exporter] bpy.ops.step_exporter exists")
            if hasattr(bpy.ops.step_exporter, 'progress_report'):
                log_to_file(f"[STEP Exporter] bpy.ops.step_exporter.progress_report exists")
                try:
                    log_to_file(f"[STEP Exporter] === Calling progress_report operator ===")
                    result = getattr(getattr(bpy.ops, 'step_exporter'), 'progress_report')('INVOKE_DEFAULT')
                    log_to_file(f"[STEP Exporter] progress_report operator called, result: {result}")
                except Exception as e:
                    log_to_file(f"[STEP Exporter] Error calling progress_report: {e}")
                    import traceback
                    traceback.print_exc()
            else:
                log_to_file(f"[STEP Exporter] ERROR: bpy.ops.step_exporter.progress_report does NOT exist!")
        else:
            log_to_file(f"[STEP Exporter] ERROR: bpy.ops.step_exporter does NOT exist!")
        
        # 将导出参数存储到全局变量
        global _export_params, _export_stage, _export_objects, _export_objects_data, _export_current_index, _export_log_file
        
        # 确定要导出的对象列表
        if self.use_selected and context.selected_objects:
            _export_objects = [obj for obj in context.selected_objects if obj.type in ('MESH', 'CURVE')]
        else:
            _export_objects = [obj for obj in context.scene.objects if obj.type in ('MESH', 'CURVE')]
        
        # 根据选择的单位确定缩放值
        if self.unit == 'mm':
            scale = 1000.0
        else:
            scale = 1.0
        
        step_unit = 'MILLIMETER' if self.unit == 'mm' else 'METER'
        
        # 检测底壳对象，使用参数化导出（直接导出，不走timer）
        bottom_shell_params = None
        for obj in _export_objects:
            if obj.type == 'MESH':
                shell_params = _analyze_bottom_shell_from_mesh(obj, context, scale)
                if shell_params:
                    bottom_shell_params = shell_params
                    break
        
        if bottom_shell_params:
            log_to_file(f"[STEP Exporter] Found bottom shell, using parametric export")
            update_progress(10, "检测到底壳，正在参数化导出...", context)
            success = step_exporter.export_bottom_shell_filleted_step(
                self.filepath,
                bottom_shell_params['width'],
                bottom_shell_params['depth'],
                bottom_shell_params['outer_height'],
                bottom_shell_params['bottom_thickness'],
                bottom_shell_params['wall_thickness'],
                bottom_shell_params['corner_radius'],
                bottom_shell_params['outer_fillet_radius'],
                bottom_shell_params['inner_fillet_radius'],
                self.step_schema,
                step_unit,
                1 if self.enable_logging else 0
            )
            if success:
                update_progress(100, "底壳导出完成", context)
                self.report({'INFO'}, f"Parametric bottom shell exported to {self.filepath}")
            else:
                update_progress(100, "底壳导出失败", context)
                self.report({'ERROR'}, "Parametric bottom shell export failed")
            end_progress(context)
            return {'FINISHED'} if success else {'CANCELLED'}
        
        _export_params = {
            'filepath': self.filepath,
            'use_selected': self.use_selected,
            'unit': self.unit,
            'fix_geometry': self.fix_geometry,
            'create_solid': self.create_solid,
            'advanced_brep': self.advanced_brep,
            'step_schema': self.step_schema,
            'sew_tolerance': self.sew_tolerance,
            'enable_logging': self.enable_logging,
            'apply_modifiers': self.apply_modifiers,
            'context': context,
            'scale': scale
        }
        
        # 重置状态
        _export_stage = 0
        _export_objects_data = []
        _export_current_index = 0
        _export_log_file = None
        
        log_to_file(f"[STEP Exporter] === Registering timer ===")
        log_to_file(f"[STEP Exporter] Objects to export: {len(_export_objects)}")
        
        # 将导出工作交给 timer，这样 modal operator 可以正常处理事件
        bpy.app.timers.register(_export_worker_timer)
        
        # 立即返回，让 Blender 处理事件循环
        return {'FINISHED'}
    
    def get_mesh_data_enhanced(self, obj, context, scale, apply_modifiers=True):
        """获取网格数据（增强版，包含更多检查和信息）"""
        if obj.type != 'MESH':
            return None
        
        import sys
        log_to_file(f"[Python DEBUG] get_mesh_data_enhanced called for object '{obj.name}'")
        sys.stdout.flush()
        mesh = obj.data
        
        # 检查原始顶点坐标
        log_to_file(f"[Python DEBUG] Original mesh vertex count: {len(mesh.vertices)}")
        if len(mesh.vertices) > 0:
            for i in range(min(5, len(mesh.vertices))):
                v = mesh.vertices[i]
                log_to_file(f"[Python DEBUG] Original vertex {i}: ({v.co.x}, {v.co.y}, {v.co.z})")
        
        # 获取最终几何（应用修改器）
        depsgraph = context.evaluated_depsgraph_get() if apply_modifiers else None
        if depsgraph:
            eval_obj = obj.evaluated_get(depsgraph)
            eval_mesh = eval_obj.data
        else:
            eval_obj = obj
            eval_mesh = mesh
        
        # 确保是三角网格
        if not eval_mesh.loop_triangles:
            eval_mesh.calc_loop_triangles()
        
        # 获取顶点（应用世界变换）
        vertices = []
        zero_vertex_count = 0
        for idx, vert in enumerate(eval_mesh.vertices):
            world_co = eval_obj.matrix_world @ vert.co
            vertex_scaled = [round(float(world_co.x) * scale, 12), round(float(world_co.y) * scale, 12), round(float(world_co.z) * scale, 12)]
            vertices.append(vertex_scaled)
            
            # 检查顶点是否为零
            if abs(world_co.x) < 1e-12 and abs(world_co.y) < 1e-12 and abs(world_co.z) < 1e-12:
                zero_vertex_count += 1
            
            # 详细调试前5个顶点
            if idx < 5:
                log_to_file(f"[Python DEBUG] Vertex {idx}:")
                log_to_file(f"  Local co: ({vert.co.x}, {vert.co.y}, {vert.co.z})")
                log_to_file(f"  World co: ({world_co.x}, {world_co.y}, {world_co.z})")
                log_to_file(f"  Scaled: ({vertex_scaled[0]}, {vertex_scaled[1]}, {vertex_scaled[2]})")
                log_to_file(f"  Matrix: {eval_obj.matrix_world}")
        
        # 调试：打印统计信息
        log_to_file(f"[Python DEBUG] Object '{obj.name}' vertex analysis:")
        log_to_file(f"  Total vertices: {len(vertices)}")
        log_to_file(f"  Zero world-co vertices: {zero_vertex_count}")
        log_to_file(f"  Scale factor: {scale}")
        log_to_file(f"  Matrix world: {eval_obj.matrix_world}")
        import sys
        sys.stdout.flush()
        
        # 如果所有顶点都为零，打印严重警告
        if zero_vertex_count == len(vertices) and len(vertices) > 0:
            log_to_file(f"[Python WARNING] ALL vertices have zero world coordinates! Check object transform and mesh data.")
            sys.stdout.flush()
        
        # 获取三角面
        faces = []
        for tri in eval_mesh.loop_triangles:
            face_indices = list(tri.vertices)
            if len(face_indices) >= 3:
                faces.append(face_indices)
        
        # 简单的流形检查
        if len(vertices) == 0 or len(faces) == 0:
            log_to_file(f"[Python] Skipping object '{obj.name}': no valid geometry.")
            return None
        
        log_to_file(f"[Python] Prepared '{obj.name}': {len(vertices)} vertices, {len(faces)} faces")
        
        return {
            'name': obj.name,
            'vertices': vertices,
            'faces': faces,
            'type': 'mesh'
        }

    def get_curve_data_enhanced(self, obj, context, scale, apply_modifiers=True):
        """获取曲线数据（贝塞尔曲线、NURBS曲线等）"""
        if obj.type != 'CURVE':
            return None
        
        import sys
        log_to_file(f"[Python DEBUG] get_curve_data_enhanced called for object '{obj.name}'")
        sys.stdout.flush()
        curve = obj.data
        
        # 获取最终几何（应用修改器）
        depsgraph = context.evaluated_depsgraph_get() if apply_modifiers else None
        if depsgraph:
            eval_obj = obj.evaluated_get(depsgraph)
            eval_curve = eval_obj.data
        else:
            eval_obj = obj
            eval_curve = curve
        
        splines_data = []
        
        for spline_idx, spline in enumerate(eval_curve.splines):
            spline_type = spline.type  # 'POLY', 'BEZIER', 'NURBS'
            log_to_file(f"[Python DEBUG] Processing spline {spline_idx}: type={spline_type}")
            
            # 确保order至少为2（NURBS的order_u可能返回0）
            # 对于NURBS，order必须 >= 4（degree >= 3）以匹配C++端期望
            order_u = getattr(spline, 'order_u', 4)
            if spline_type == 'NURBS' and order_u < 4:
                order_u = 4  # NURBS order至少为4（degree 3）
                log_to_file(f"[Python DEBUG] Fixed invalid order for {spline_type}, using order={order_u}")
            elif order_u < 3:  # 其他曲线类型至少为3
                order_u = 4
                log_to_file(f"[Python DEBUG] Fixed invalid order for {spline_type}, using order={order_u}")
            
            spline_info = {
                'type': spline_type,
                'order': order_u,
                'resolution_u': spline.resolution_u,
                'use_cyclic_u': spline.use_cyclic_u,
                'use_endpoint_u': spline.use_endpoint_u,
            }
            log_to_file(f"[Python DEBUG] Spline info: type={spline_info['type']}, order={spline_info['order']}, use_cyclic_u={spline_info['use_cyclic_u']}")
            
            # 获取控制点（应用世界变换）
            control_points = []
            weights = []
            
            if spline_type == 'POLY' or spline_type == 'NURBS':
                points = spline.points
                for point_idx, point in enumerate(points):
                    # Blender中的点坐标是4D: (x, y, z, w)，其中w是权重（对于NURBS）
                    local_co = point.co
                    world_co = eval_obj.matrix_world @ local_co.to_3d()
                    scaled_co = [round(float(world_co.x) * scale, 12), 
                                 round(float(world_co.y) * scale, 12), 
                                 round(float(world_co.z) * scale, 12)]
                    control_points.append(scaled_co)
                    weights.append(float(point.weight))
                
                # 设置控制点和权重
                spline_info['control_points'] = control_points
                if spline_type == 'NURBS':
                    spline_info['weights'] = weights
                else:
                    # 对于POLY曲线，权重全部设为1.0
                    spline_info['weights'] = [1.0] * len(weights)
                
                # 对于NURBS曲线，尝试获取节点向量
                if spline_type == 'NURBS':
                    for attr in ['knots_u', 'knots', 'knot_vector']:
                        if hasattr(spline, attr):
                            val = getattr(spline, attr)
                            if val:
                                spline_info['knots_u'] = [float(k) for k in val]
                                log_to_file(f"[Python DEBUG] NURBS knots from {attr}: {spline_info['knots_u']}")
                                break
                    else:
                        log_to_file(f"[Python DEBUG] No knots attribute found for NURBS, using periodic knots for closed NURBS")
                        # 修正节点向量计算以匹配C++端期望
                        # C++端期望：num_knots = control_points.size() + order
                        num_control_points = len(control_points)
                        # 使用已修正的order（确保至少为4）
                        order = spline_info['order']
                        if spline_type == 'NURBS' and order < 4:
                            order = 4
                            log_to_file(f"[Python DEBUG] Adjusted order to {order} for NURBS circle")
                        degree = order - 1
                        num_knots = num_control_points + order  # 与C++端一致
                        log_to_file(f"[Python DEBUG] NURBS circle: control_points={num_control_points}, order={order}, num_knots={num_knots}")
                        
                        if spline.use_cyclic_u:
                            # 周期性NURBS：均匀节点向量 [0, 1, 2, ..., num_knots-1]
                            knots = [float(i) for i in range(num_knots)]
                            log_to_file(f"[Python DEBUG] Computed PERIODIC knots for closed NURBS: {knots} (count={num_knots})")
                        else:
                            # 开放NURBS：准均匀节点向量
                            # 节点数量 = num_control_points + order
                            # 前 order 个节点为 0，后 order 个节点为 n-degree+1，中间均匀分布
                            n = num_control_points - 1
                            knots = []
                            for i in range(num_knots):
                                if i < order:
                                    knots.append(0.0)
                                elif i >= num_knots - order:
                                    knots.append(float(n - degree + 1))
                                else:
                                    knots.append(float(i - order + 1))
                            log_to_file(f"[Python DEBUG] Computed UNIFORM knots for open NURBS: {knots} (count={num_knots})")
                        
                        spline_info['knots_u'] = knots
            
            elif spline_type == 'BEZIER':
                # 将贝塞尔曲线转换为NURBS曲线，正确传递手柄信息
                points = spline.bezier_points
                close_curve = spline.use_cyclic_u
                original_close_curve = close_curve  # 保存原始闭合状态
                log_to_file(f"[Python DEBUG] Bezier curve with {len(points)} control points, closed: {close_curve}")
                
                # 调试：打印第一个点的属性
                if points:
                    bp0 = points[0]
                    log_to_file(f"[Python DEBUG] BezierSplinePoint attributes: {[attr for attr in dir(bp0) if not attr.startswith('__')]}")
                
                # 初始化控制点和权重列表
                control_points = []
                weights = []
                
                # 段数：开放曲线为n-1，闭合曲线为n
                num_segments = len(points) - 1 if not close_curve else len(points)
                
                # 收集每个贝塞尔段的4个控制点
                segment_controls = []  # 每个元素是4个控制点的列表
                for seg_idx in range(num_segments):
                    # 获取当前段的起点和终点索引
                    if close_curve:
                        start_idx = seg_idx
                        end_idx = (seg_idx + 1) % len(points)
                    else:
                        start_idx = seg_idx
                        end_idx = seg_idx + 1
                    
                    bp_start = points[start_idx]
                    bp_end = points[end_idx]
                    
                    # 四个控制点：起点、起点右手柄、终点左手柄、终点
                    seg_points = []
                    for bp, handle_attr in [(bp_start, 'co'),
                                            (bp_start, 'handle_right'),
                                            (bp_end, 'handle_left'),
                                            (bp_end, 'co')]:
                        if handle_attr == 'co':
                            local_co = bp.co
                        else:
                            local_co = getattr(bp, handle_attr)
                        world_co = eval_obj.matrix_world @ local_co
                        scaled_co = [round(float(world_co.x) * scale, 12),
                                     round(float(world_co.y) * scale, 12),
                                     round(float(world_co.z) * scale, 12)]
                        seg_points.append(scaled_co)
                    segment_controls.append(seg_points)
                
                # 构建总控制点列表：第一个段添加所有4个点，后续段只添加后3个点（避免重复起点）
                for seg_idx, seg_points in enumerate(segment_controls):
                    if seg_idx == 0:
                        control_points.extend(seg_points)
                        weights.extend([1.0, 1.0, 1.0, 1.0])
                    else:
                        # 跳过第一个点（与上一段最后一个点相同）
                        control_points.extend(seg_points[1:])
                        weights.extend([1.0, 1.0, 1.0])
                
                # 对于闭合曲线，不添加额外控制点，但添加第一个控制点作为最后一个控制点以实现闭合
                if close_curve:
                    # 添加第一个控制点作为最后一个控制点，使曲线闭合
                    control_points.append(control_points[0])
                    weights.append(weights[0])
                    # 不标记为周期性曲线，使用开放曲线算法
                    close_curve = False
                
                # 设置NURBS参数
                spline_info['type'] = 'NURBS'
                spline_info['order'] = 4  # 三次贝塞尔曲线
                spline_info['control_points'] = control_points
                spline_info['weights'] = weights
                spline_info['use_cyclic_u'] = close_curve
                
                # 计算节点向量
                # 使用准均匀节点向量算法，与NURBS曲线保持一致
                # 控制点数量 = n+1, 阶数 = order, 节点数量 = n+order+1
                n = len(control_points) - 1
                order = 4  # 三次贝塞尔曲线
                num_knots = n + order + 1
                
                # 根据曲线是否闭合选择节点向量算法
                if close_curve:
                    # 对于闭合曲线，生成均匀节点向量，适合周期性B样条曲线
                    # 阶数 = order，度数 = order - 1
                    degree = order - 1
                    # 不同节点值数量 = 控制点数 - 度数 + 3
                    unique_knot_count = len(control_points) - degree + 3
                    # 生成从0到1的均匀节点值（包括0和1）
                    unique_knots = [i / (unique_knot_count - 1) for i in range(unique_knot_count)]
                    # 构建完整节点向量：前degree个节点为0，中间节点为unique_knots[1:-1]，后degree个节点为1
                    knots = [0.0] * degree  # 前degree个节点为0
                    knots.extend(unique_knots[1:-1])  # 中间节点，排除首尾
                    knots.extend([1.0] * degree)  # 后degree个节点为1
                    log_to_file(f"[Python DEBUG] Generated uniform knots for closed curve: {knots}")
                else:
                    # 对于开放曲线，使用准均匀节点向量：两端重复order次，中间均匀分布
                    knots = []
                    for i in range(num_knots):
                        if i < order:
                            knots.append(0.0)
                        elif i > n:
                            knots.append(float(n - order + 2))
                        else:
                            knots.append(float(i - order + 1))
                    
                    # 归一化节点向量到范围[0,1]
                    if knots[-1] > 0:
                        max_knot = knots[-1]
                        knots = [k / max_knot for k in knots]
                
                spline_info['knots_u'] = knots
                log_to_file(f"[Python DEBUG] Converted Bezier to NURBS: {len(control_points)} control points, {len(knots)} knots, closed: {close_curve}, n={n}, order={order}")
                
                # 特殊处理：有理贝塞尔圆 - 生成有理NURBS圆
                if "BezierCircle" in obj.name and len(points) == 4 and original_close_curve:
                    log_to_file(f"[Python DEBUG] Generating rational NURBS circle for {obj.name}")
                    # 计算世界坐标下的圆心和半径（从贝塞尔控制点估算）
                    # 使用原始贝塞尔控制点的世界坐标平均值作为圆心
                    bezier_points = points
                    world_coords = []
                    log_to_file(f"[Python DEBUG] eval_obj.matrix_world: {eval_obj.matrix_world}")
                    log_to_file(f"[Python DEBUG] obj.matrix_world: {obj.matrix_world}")
                    for bp in bezier_points:
                        local_co = bp.co
                        world_co = obj.matrix_world @ local_co
                        scaled_co = [float(world_co.x) * scale, float(world_co.y) * scale, float(world_co.z) * scale]
                        world_coords.append(scaled_co)
                        log_to_file(f"[Python DEBUG] Local co: {local_co}, world co: {world_co}, scaled: {scaled_co}")
                    
                    # 计算圆心（世界坐标平均值）
                    center_x = sum(wc[0] for wc in world_coords) / len(world_coords)
                    center_y = sum(wc[1] for wc in world_coords) / len(world_coords)
                    center_z = sum(wc[2] for wc in world_coords) / len(world_coords)
                    # 半径：最大距离（世界坐标）
                    radius = max(math.sqrt((wc[0] - center_x)**2 + (wc[1] - center_y)**2 + (wc[2] - center_z)**2) for wc in world_coords)
                    
                    # 标准NURBS圆控制点（9个点），使用周期性NURBS表示
                    # 角度：0°, 45°, 90°, 135°, 180°, 225°, 270°, 315°, 360°（不重复0°）
                    angles = [0, math.pi/4, math.pi/2, 3*math.pi/4, math.pi, 5*math.pi/4, 3*math.pi/2, 7*math.pi/4, 2*math.pi]
                    # 控制点坐标（在世界坐标系中的圆上）
                    control_points = []
                    for angle in angles:
                        x = center_x + radius * math.cos(angle)
                        y = center_y + radius * math.sin(angle)
                        control_points.append([round(x, 12), round(y, 12), round(center_z, 12)])
                    
                    # 权重：1, √2/2, 1, √2/2, 1, √2/2, 1, √2/2, 1
                    sqrt2_over_2 = math.sqrt(2) / 2
                    weights = [1.0, sqrt2_over_2, 1.0, sqrt2_over_2, 1.0, sqrt2_over_2, 1.0, sqrt2_over_2, 1.0]
                    
                    # 为周期性NURBS圆生成节点向量
                    # 使用与普通闭合曲线相同的均匀节点向量算法
                    order = 4
                    degree = order - 1  # 3
                    # 不同节点值数量 = 控制点数 - 度数 + 3
                    unique_knot_count = len(control_points) - degree + 3  # 9 - 3 + 3 = 9
                    # 生成从0到1的均匀节点值（包括0和1）
                    unique_knots = [i / (unique_knot_count - 1) for i in range(unique_knot_count)]
                    # 构建完整节点向量：前degree个节点为0，中间节点为unique_knots[1:-1]，后degree个节点为1
                    knots = [0.0] * degree  # 前degree个节点为0
                    knots.extend(unique_knots[1:-1])  # 中间节点，排除首尾
                    knots.extend([1.0] * degree)  # 后degree个节点为1
                    log_to_file(f"[Python DEBUG] Generated uniform knots for periodic NURBS circle: {knots}")
                    
                    # 替换控制点、权重、节点向量和阶数
                    spline_info['control_points'] = control_points
                    spline_info['weights'] = weights
                    spline_info['knots_u'] = knots
                    spline_info['order'] = 4
                    spline_info['use_cyclic_u'] = True  # 恢复为周期性曲线
                    
                    log_to_file(f"[Python DEBUG] Generated rational NURBS circle with {len(control_points)}control points")
                    log_to_file(f"[Python DEBUG] World center: ({center_x}, {center_y}, {center_z}), radius: {radius}")
                    log_to_file(f"[Python DEBUG] Weights: {weights}")
                    log_to_file(f"[Python DEBUG] Knots: {knots}")
                    log_to_file(f"[Python DEBUG] use_cyclic_u set to: {spline_info['use_cyclic_u']}")
                    # 添加圆心和半径信息，以便C++代码可以创建解析圆
                    spline_info['circle_center'] = [center_x, center_y, center_z]
                    spline_info['circle_radius'] = radius
            
                log_to_file(f"[Python DEBUG] NURBS weights: {weights}")
                log_to_file(f"[Python DEBUG] NURBS order_u: {spline.order_u}")
                # 调试：打印spline的所有属性
                log_to_file(f"[Python DEBUG] Spline attributes: {[attr for attr in dir(spline) if not attr.startswith('__')]}")
                # 检查knots相关属性，仅当spline_info中还没有knots_u时
                if 'knots_u' not in spline_info:
                    for attr in ['knots_u', 'knots', 'knots_u', 'knot_vector']:
                        if hasattr(spline, attr):
                            val = getattr(spline, attr)
                            log_to_file(f"[Python DEBUG] Found attribute {attr}: {val}")
                            if val:
                                spline_info['knots_u'] = [float(k) for k in val]
                                log_to_file(f"[Python DEBUG] NURBS knots_u: {spline_info['knots_u']}")
                                break
                    else:
                        log_to_file(f"[Python DEBUG] No knots attribute found, using default knots")
                        # 尝试计算默认节点向量
                        # 对于闭合（周期性）NURBS，使用均匀节点向量
                        n = len(control_points) - 1
                        # NURBS order 必须 ≥ 3 (degree ≥ 2)
                        order = max(3, getattr(spline, 'order_u', 4))
                        
                        if spline.use_cyclic_u:
                            # 周期性NURBS：均匀节点，长度 = n + order
                            # 例如：9个控制点，order=4 -> 节点数=13 (0到12)
                            num_knots = n + order
                            knots = [float(i) for i in range(num_knots)]
                        else:
                            # 开放NURBS：准均匀节点，两端重复
                            num_knots = n + order + 1
                            knots = []
                            for i in range(num_knots):
                                if i < order:
                                    knots.append(0.0)
                                elif i > n:
                                    knots.append(float(n - order + 2))
                                else:
                                    knots.append(float(i - order + 1))
                        
                        spline_info['knots_u'] = knots
                        log_to_file(f"[Python DEBUG] Computed {'periodic' if spline.use_cyclic_u else 'uniform'} knots: {knots}")
                else:
                    log_to_file(f"[Python DEBUG] Using pre-set knots_u from special handling")
            
            splines_data.append(spline_info)
        
        if not splines_data:
            log_to_file(f"[Python] Skipping curve object '{obj.name}': no valid splines.")
            return None
        
        log_to_file(f"[Python] Prepared curve '{obj.name}': {len(splines_data)} splines, extrude={curve.extrude}, bevel={curve.bevel_depth}")
        
        return {
            'name': obj.name,
            'type': 'curve',
            'splines': splines_data,
            'dimensions': curve.dimensions,
            'resolution_u': curve.resolution_u,
            # 挤出信息（用于C++端构建3D实体）
            # 注意：挤出深度和倒角深度也需要应用缩放，以保持与控制点坐标的一致性
            'extrude': float(curve.extrude) * scale,
            'bevel_depth': float(curve.bevel_depth) * scale,
            'bevel_resolution': int(curve.bevel_resolution),
            'use_fill_caps': bool(curve.use_fill_caps),
            # 变换矩阵
            'matrix_world': [list(row) for row in eval_obj.matrix_world],
        }

# ====================== 菜单函数 ======================

def menu_func_export_enhanced(self, context):
    self.layout.operator(STEP_EXPORTER_OT_export_enhanced.bl_idname, text="STEP Enhanced (.step)")

# ====================== 面板类 ======================

class STEP_EXPORTER_PT_main_panel(Panel):
    bl_label = "STEP Exporter"
    bl_idname = "STEP_EXPORTER_PT_main_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "STEP Export"
    
    def draw(self, context):
        layout = self.layout
        
        # 状态显示
        box = layout.box()
        box.label(text="Module Status", icon='INFO')
        
        if CPP_MODULE_LOADED and step_exporter:
            try:
                version = step_exporter.get_version()
                box.label(text=f"✓ Module v{version} loaded", icon='CHECKMARK')
                box.label(text=f"✓ OpenCASCADE 7.7.2 ready", icon='CHECKMARK')
            except:
                box.label(text="✓ C++ module loaded", icon='CHECKMARK')
        else:
            box.label(text="✗ C++ extension not loaded", icon='ERROR')
            box.label(text="Check system console", icon='ERROR')
        
        # 快速导出按钮
        layout.separator()
        if CPP_MODULE_LOADED:
            col = layout.column(align=True)
            col.operator("export_scene.step_enhanced", text="Quick Export (Enhanced)", icon='EXPORT')
        else:
            box = layout.box()
            box.label(text="C++ module required", icon='ERROR')
            box.label(text="Compile and install first")

# ====================== 注册与注销 ======================

classes = [
    STEP_EXPORTER_OT_export_enhanced,
    STEP_EXPORTER_PT_main_panel,
]

def register():
    # 注册所有类
    for cls in classes:
        bpy.utils.register_class(cls)
    
    # 注册进度报告系统（包含场景属性和 header 绘制）
    register_progress()
    
    # 添加到导出菜单
    bpy.types.TOPBAR_MT_file_export.append(menu_func_export_enhanced)
    
    print("[STEP Exporter] Enhanced plugin registered successfully")

def unregister():
    # 从导出菜单移除
    bpy.types.TOPBAR_MT_file_export.remove(menu_func_export_enhanced)
    
    # 注销进度条场景属性（progress_report.py 中已处理 header 恢复）
    if hasattr(bpy.types.Scene, 'step_progress_indicator'):
        del bpy.types.Scene.step_progress_indicator
    if hasattr(bpy.types.Scene, 'step_progress_indicator_text'):
        del bpy.types.Scene.step_progress_indicator_text
    
    # 注销进度报告系统
    unregister_progress()
    
    # 注销所有类
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    
    print("[STEP Exporter] Plugin unregistered")

# 直接运行时的测试
if __name__ == "__main__":
    # 清理之前的注册（如果存在）
    try:
        unregister()
    except:
        pass
    
    # 重新注册
    register()