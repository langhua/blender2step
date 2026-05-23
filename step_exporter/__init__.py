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
import bmesh
from mathutils import Vector
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
_log_buffer = []  # 日志缓冲区（文件打开前的消息暂存于此）
_cpp_log_callback = None  # C++日志回调函数
_bottom_shell_export_data = None  # 底壳参数化导出数据

def log_to_file(msg):
    """输出到日志文件和console（同步输出）"""
    if not msg.endswith("\n"):
        msg = msg + "\n"
    
    # 始终输出到console
    print(msg, end='')
    
    # 同时写入step日志文件
    if _export_log_file and not _export_log_file.closed:
        _export_log_file.write(msg)
        _export_log_file.flush()
    else:
        # 文件未打开，暂存到缓冲区
        _log_buffer.append(msg)

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
        log_to_file(f"[STEP Exporter] Added lib path to system PATH: {lib_path}")
    
    # 优先从 lib 子目录导入
    try:
        if os.path.exists(lib_path) and lib_path not in sys.path:
            sys.path.insert(0, lib_path)
        import _step_exporter as step_exporter_lib
        step_exporter = step_exporter_lib
        
        if hasattr(step_exporter, 'get_version'):
            module_version = step_exporter.get_version()
            log_to_file(f"[STEP Exporter] [OK] C++ extension module loaded successfully (from lib)")
            log_to_file(f"[STEP Exporter] Module version: {module_version}")
            CPP_MODULE_LOADED = True
        else:
            MODULE_LOAD_ERROR = "C++ module from lib missing required functions"
            log_to_file(f"[STEP Exporter] [WARN] C++ module from lib missing functions")
            
    except ImportError as e2:
        MODULE_LOAD_ERROR = f"ImportError from lib: {str(e2)}"
        log_to_file(f"[STEP Exporter] [ERROR] Failed to import C++ module from lib: {e2}")
        
        # 尝试直接导入作为后备
        try:
            import _step_exporter
            step_exporter = _step_exporter
            
            if hasattr(step_exporter, 'get_version'):
                module_version = step_exporter.get_version()
                log_to_file(f"[STEP Exporter] [OK] C++ extension module loaded successfully (direct import)")
                log_to_file(f"[STEP Exporter] Module version: {module_version}")
                CPP_MODULE_LOADED = True
            else:
                MODULE_LOAD_ERROR = "C++ module missing required functions"
                log_to_file(f"[STEP Exporter] [ERROR] C++ module loaded but missing functions")
                
        except ImportError as e:
            MODULE_LOAD_ERROR = f"ImportError: {str(e)}"
            log_to_file(f"[STEP Exporter] [ERROR] Failed to import C++ module directly: {e}")
            
except Exception as e:
    MODULE_LOAD_ERROR = f"Unexpected error: {str(e)}"
    log_to_file(f"[STEP Exporter] [ERROR] Unexpected error loading C++ module: {e}")

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
    
    if len(sorted_z_levels) < 2:
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
    
    # 从底部顶点计算物体中心和尺寸
    bottom_x_coords = [v.co.x for v in bottom_verts]
    bottom_y_coords = [v.co.y for v in bottom_verts]
    obj_center_x = (max(bottom_x_coords) + min(bottom_x_coords)) / 2.0
    obj_center_y = (max(bottom_y_coords) + min(bottom_y_coords)) / 2.0
    width = max(bottom_x_coords) - min(bottom_x_coords)
    depth = max(bottom_y_coords) - min(bottom_y_coords)
    half_w = width / 2.0
    half_d = depth / 2.0
    log_to_file(f"[STEP Exporter] Shell center=({obj_center_x:.1f},{obj_center_y:.1f}), size={width:.1f}x{depth:.1f}")
    
    # 找到外层垂直壁开始的位置（外圆角结束处）
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
    log_to_file(f"[STEP Exporter] outer_wall_start_z={outer_wall_start_z:.2f}, outer_fillet={outer_fillet_radius:.2f}")
    
    # ===== 提取外壁顶点坐标用于后续分析（然后释放 bmesh）=====
    try:
        outer_wall_verts_coords = [(v.co.x, v.co.y, v.co.z) for v in z_layers.get(outer_wall_start_z, bottom_verts)]
        log_to_file(f"[STEP Exporter] outer_wall_verts at z={outer_wall_start_z:.2f}: {len(outer_wall_verts_coords)} vertices")
    except Exception as e:
        log_to_file(f"[STEP Exporter] ERROR extracting outer wall coords: {e}")
        return None
    
    # ===== 找到具有最大外轮廓的z层用于角点检测 =====
    # 在底壳模型中，底部因圆角（fillet）而收缩，真正的全尺寸外轮廓在更高的z层
    # 扫描所有z层，找到顶点到中心距离最大的层（即外轮廓最完整的层）
    corner_detect_verts_coords = None
    corner_detect_z = None
    max_outer_dist_overall = 0.0
    for z_level in sorted_z_levels:
        verts_at_z = z_layers.get(z_level, [])
        if len(verts_at_z) < 20:
            continue
        coords = [(v.co.x, v.co.y, v.co.z) for v in verts_at_z]
        dists = [math.sqrt((x - obj_center_x)**2 + (y - obj_center_y)**2) for x, y, z in coords]
        if dists:
            max_d_at_z = max(dists)
            if max_d_at_z > max_outer_dist_overall:
                max_outer_dist_overall = max_d_at_z
                corner_detect_verts_coords = coords
                corner_detect_z = z_level
    if corner_detect_verts_coords is None:
        corner_detect_verts_coords = [(v.co.x, v.co.y, v.co.z) for v in bottom_verts]
        corner_detect_z = bottom_z
    log_to_file(f"[STEP Exporter] Corner detect z-level: z={corner_detect_z:.2f}, max_outer_dist={max_outer_dist_overall:.1f}, verts={len(corner_detect_verts_coords)}")
    
    # ===== 从最大外轮廓顶点重新计算宽度和深度 =====
    # half_w/half_d 应从全尺寸外轮廓计算，而非收缩的底部
    max_contour_x = max(x for x, y, z in corner_detect_verts_coords)
    min_contour_x = min(x for x, y, z in corner_detect_verts_coords)
    max_contour_y = max(y for x, y, z in corner_detect_verts_coords)
    min_contour_y = min(y for x, y, z in corner_detect_verts_coords)
    full_width = max_contour_x - min_contour_x
    full_depth = max_contour_y - min_contour_y
    half_w_corner = full_width / 2.0
    half_d_corner = full_depth / 2.0
    log_to_file(f"[STEP Exporter] Contour dimensions from full profile: {full_width:.1f}x{full_depth:.1f} (vs bottom: {width:.1f}x{depth:.1f})")
    
    # 用全尺寸更新 width/depth（后续传递给C++）
    width = full_width
    depth = full_depth
    half_w = half_w_corner
    half_d = half_d_corner
    
    # 中间层顶点用于壁厚检测
    mid_z_target = bottom_z + total_height * 0.5
    mid_z = min(sorted_z_levels, key=lambda z: abs(z - mid_z_target))
    mid_verts_coords = [(v.co.x, v.co.y, v.co.z) for v in z_layers.get(mid_z, [])]
    
    # ===== Z层分析找内腔底部 =====
    # 在底部z层和外部壁起始z层之间，找顶点数最多的z层作为内腔底面
    inner_bottom_z = None
    bottom_thickness = 2.0
    
    search_upper_z = outer_wall_start_z if outer_wall_start_z else max_z
    
    max_inner_vert_count = 0
    for z_level in sorted_z_levels:
        if z_level > bottom_z + 0.3 and z_level < search_upper_z - 0.3:
            count = len(z_layers[z_level])
            if count > max_inner_vert_count and count >= 20:
                max_inner_vert_count = count
                inner_bottom_z = z_level
    
    if inner_bottom_z is not None:
        bottom_thickness = inner_bottom_z - bottom_z
        log_to_file(f"[STEP Exporter] Inner bottom via Z-layer: z={inner_bottom_z:.2f}, bottom_thickness={bottom_thickness:.2f}, verts={max_inner_vert_count}")
    else:
        # Z层分析失败（布尔运算后的2层网格），使用默认底部厚度
        log_to_file(f"[STEP Exporter] Inner bottom not found via Z-layer (levels={len(sorted_z_levels)}), using default bottom_thickness={bottom_thickness:.1f}")
        inner_bottom_z = bottom_z + bottom_thickness
    
    # 保存底部顶点数，用于后续孔检测
    bottom_vert_count_before_free = len(bottom_verts)
    bottom_vert_coords = [(v.co.x, v.co.y, v.co.z) for v in bottom_verts]
    
    # ===== 圆形检测：如果底部外轮廓是圆形，说明是圆柱/空心圆柱，不是底壳 =====
    # 底壳底部是圆角矩形（拐角处半径小，边长处半径大），std/mean 较大
    # 圆柱/空心圆柱底部是正圆，外轮廓所有顶点到中心距离相同，std/mean 很小
    bottom_all_dists = [math.sqrt((x - obj_center_x)**2 + (y - obj_center_y)**2) 
                        for x, y, z in bottom_vert_coords]
    if bottom_all_dists:
        max_bd = max(bottom_all_dists)
        # 仅保留外圈顶点（最外层 15%），排除内孔顶点
        outer_bottom_dists = [d for d in bottom_all_dists if d > max_bd * 0.85]
        if len(outer_bottom_dists) >= 8:
            mean_obd = sum(outer_bottom_dists) / len(outer_bottom_dists)
            std_obd = math.sqrt(sum((d - mean_obd)**2 for d in outer_bottom_dists) / len(outer_bottom_dists))
            circularity = std_obd / mean_obd if mean_obd > 0 else 1.0
            log_to_file(f"[STEP Exporter] Bottom circularity check: circ={circularity:.4f} (n_outer={len(outer_bottom_dists)})")
            if circularity < 0.02:
                log_to_file(f"[STEP Exporter] Bottom outer contour is circular, not a bottom shell -> skipping to cylinder detection")
                bm.free()
                return None
    
    # 释放 BMesh（所有 z_layers 中的 BMVert 引用现在无效）
    bm.free()
    
    # outer_height = 使用实际网格Z向高度 (top_z, bottom_z 已在前面定义)
    outer_height = max(top_z - bottom_z, 8.0)
    
    if outer_fillet_radius > outer_height * 0.5:
        outer_fillet_radius = 0.0
    
    inner_fillet_radius = 0.0
    
    # ===== 角圆角检测（用最大外轮廓层的坐标）=====
    corner_radius = 0.0
    
    # 过滤到仅最外层轮廓顶点（排除内轮廓和填充顶点）
    outer_dists = [math.sqrt((x - obj_center_x)**2 + (y - obj_center_y)**2) 
                   for x, y, z in corner_detect_verts_coords]
    if outer_dists:
        max_d = max(outer_dists)
        # 仅保留距离中心最远的顶点（外轮廓），排除内侧墙壁顶点
        outer_contour_only = [(x, y) for (x, y, z), d in zip(corner_detect_verts_coords, outer_dists) 
                             if d > max_d * 0.85]
        log_to_file(f"[STEP Exporter] Outer contour filter: {len(outer_contour_only)}/{len(corner_detect_verts_coords)} vertices (max_d={max_d:.1f})")
    else:
        outer_contour_only = [(x, y) for x, y, z in corner_detect_verts_coords]
    
    corner_verts = [(x, y) for x, y in outer_contour_only 
                    if abs(x - obj_center_x) > half_w * 0.6 
                    and abs(y - obj_center_y) > half_d * 0.6]
    log_to_file(f"[STEP Exporter] corner_verts filter: hw={half_w:.1f} hd={half_d:.1f} found={len(corner_verts)} from {len(outer_contour_only)}")
    if corner_verts:
        radii = []
        for cx, cy in corner_verts:
            dx = half_w - abs(cx - obj_center_x)
            dy = half_d - abs(cy - obj_center_y)
            if dx > 0 and dy > 0:
                # 圆角半径精确公式：对于圆角矩形角弧上的点，
                # R = dx + dy + sqrt(2*dx*dy)
                r = dx + dy + math.sqrt(2 * dx * dy)
                radii.append(r)
        if radii:
            radii.sort()
            log_to_file(f"[STEP Exporter] Raw corner radii: min={radii[0]:.2f} max={radii[-1]:.2f} median={radii[len(radii)//2]:.2f}")
            # 使用中位数代替75%分位数，外轮廓顶点产生的值应一致
            corner_radius = radii[len(radii) // 2]
            log_to_file(f"[STEP Exporter] Corner radius computed from {len(radii)} verts (median): {corner_radius:.2f}")
    if corner_radius < 1.0:
        corner_radius = min(width, depth) * 0.2
        log_to_file(f"[STEP Exporter] Corner radius fallback: {corner_radius:.2f}")
    
    # ===== 圆形截面检查 =====
    outer_dists = [math.sqrt((x - obj_center_x)**2 + (y - obj_center_y)**2) for x, y, z in corner_detect_verts_coords]
    if outer_dists:
        min_d, max_d = min(outer_dists), max(outer_dists)
        if max_d > 0 and min_d / max_d > 0.85:
            log_to_file(f"[STEP Exporter] Cross-section too circular, not a bottom shell")
            return None
    
    # ===== 壁厚检测 =====
    wall_thickness = 2.0
    if mid_verts_coords:
        flat_x_outer_vals = [abs(x - obj_center_x) for x, y, z in mid_verts_coords 
                            if abs(y - obj_center_y) < depth * 0.15]
        flat_x_inner_vals = [abs(x - obj_center_x) for x, y, z in mid_verts_coords 
                            if abs(y - obj_center_y) < depth * 0.15 
                            and abs(x - obj_center_x) < half_w * 0.98]
        flat_y_outer_vals = [abs(y - obj_center_y) for x, y, z in mid_verts_coords 
                            if abs(x - obj_center_x) < width * 0.15]
        flat_y_inner_vals = [abs(y - obj_center_y) for x, y, z in mid_verts_coords 
                            if abs(x - obj_center_x) < width * 0.15 
                            and abs(y - obj_center_y) < half_d * 0.98]
        
        fxo = max(flat_x_outer_vals) if flat_x_outer_vals else 0
        fxi = max(flat_x_inner_vals) if flat_x_inner_vals else 0
        fyo = max(flat_y_outer_vals) if flat_y_outer_vals else 0
        fyi = max(flat_y_inner_vals) if flat_y_inner_vals else 0
        
        if fxi > 0 and fyi > 0:
            wall_thickness = ((fxo - fxi) + (fyo - fyi)) / 2
    
    if wall_thickness < 0.5:
        wall_thickness = 2.0
    
    log_to_file(f"[STEP Exporter] Detected bottom shell: {width:.1f}x{depth:.1f} h={outer_height:.1f} bt={bottom_thickness:.1f} wt={wall_thickness:.1f} cr={corner_radius:.1f} ofr={outer_fillet_radius:.1f} ifr={inner_fillet_radius:.1f}")
    
    # ===== 检测螺丝孔：用底层顶点数判断 =====
    # 带孔的底壳在底部z层有大量额外顶点（孔边界三角化产生），无孔底壳底部顶点较少
    has_holes = False
    hole_radius_detected = 1.5
    hole_offset_x = 25.0
    hole_offset_y = 20.0
    
    bottom_vert_count = bottom_vert_count_before_free
    
    # 无孔底壳约257顶点，带孔约636顶点。用阈值300区分
    if bottom_vert_count > 400:
        has_holes = True
        log_to_file(f"[STEP Exporter] Has holes detected (bottom_verts={bottom_vert_count})")
        
        # 自动检测孔位置：分析底部顶点在四个象限的聚簇分布
        ocx, ocy = obj_center_x, obj_center_y
        q_pp, q_pn, q_np, q_nn = [], [], [], []
        for bx, by, bz in bottom_vert_coords:
            dx = bx - ocx
            dy = by - ocy
            if dx > 0 and dy > 0:
                q_pp.append((dx, dy))
            elif dx > 0 and dy < 0:
                q_pn.append((dx, dy))
            elif dx < 0 and dy > 0:
                q_np.append((dx, dy))
            elif dx < 0 and dy < 0:
                q_nn.append((dx, dy))
        
        hole_cx_vals = []
        hole_cy_vals = []
        hole_radius_vals = []
        
        for q in [q_pp, q_pn, q_np, q_nn]:
            if len(q) < 10:
                continue
            # 按距离中心排序
            q_radii = sorted([(math.sqrt(x*x + y*y), x, y) for x, y in q])
            
            # ===== 方法1: 间隙检测（内外簇之间的最大间隙）=====
            best_gap = 0
            best_idx = len(q_radii) // 2
            search_start = max(1, len(q_radii) // 4)
            search_end = min(len(q_radii) - 1, 3 * len(q_radii) // 4)
            for i in range(search_start, search_end):
                gap = q_radii[i][0] - q_radii[i-1][0]
                if gap > best_gap:
                    best_gap = gap
                    best_idx = i
            
            gap_detected = best_gap > 2.0
            
            if gap_detected:
                # 间隙检测成功：内簇为孔边界顶点
                inner = [(x, y) for r, x, y in q_radii[:best_idx]]
                if inner:
                    hole_cx_vals.append(abs(sum(x for x, y in inner) / len(inner)))
                    hole_cy_vals.append(abs(sum(y for x, y in inner) / len(inner)))
                    cx_q = sum(x for x, y in inner) / len(inner)
                    cy_q = sum(y for x, y in inner) / len(inner)
                    r_q = sum(math.sqrt((x - cx_q)**2 + (y - cy_q)**2) for x, y in inner) / len(inner)
                    hole_radius_vals.append(r_q)
            else:
                # ===== 方法2: 滑动窗口密度聚类（间隙检测失败时）=====
                # 滑动窗口找空间最紧凑的簇（最小位置方差），而非最短半径
                # 孔边界顶点形成一个紧密的圆形簇，内部三角化点分散但半径更小
                window_size = max(4, min(len(q_radii) // 6, 12))
                best_cluster = None
                best_variance = float('inf')
                for i in range(len(q_radii) - window_size + 1):
                    window_pts = [(x, y) for r, x, y in q_radii[i:i+window_size]]
                    cx_w = sum(x for x, y in window_pts) / window_size
                    cy_w = sum(y for x, y in window_pts) / window_size
                    variance = sum((x - cx_w)**2 + (y - cy_w)**2 for x, y in window_pts) / window_size
                    if variance < best_variance:
                        best_variance = variance
                        best_cluster = window_pts
                
                if best_cluster and best_variance < 25.0:
                    hole_cx_vals.append(abs(sum(x for x, y in best_cluster) / len(best_cluster)))
                    hole_cy_vals.append(abs(sum(y for x, y in best_cluster) / len(best_cluster)))
                    log_to_file(f"[STEP Exporter] Quadrant gap detection failed (best_gap={best_gap:.2f}), density cluster found (variance={best_variance:.2f})")
                else:
                    log_to_file(f"[STEP Exporter] Quadrant gap/cluster detection both failed (best_gap={best_gap:.2f}, best_variance={best_variance:.2f})")
        
        if hole_cx_vals and hole_cy_vals:
            hole_cx = sum(hole_cx_vals) / len(hole_cx_vals)
            hole_cy = sum(hole_cy_vals) / len(hole_cy_vals)
            hole_offset_x = half_w - hole_cx
            hole_offset_y = half_d - hole_cy
            if hole_radius_vals:
                hole_radius_detected = sum(hole_radius_vals) / len(hole_radius_vals)
            log_to_file(f"[STEP Exporter] Auto-detected hole positions: cx={hole_cx:.1f}, cy={hole_cy:.1f}, r={hole_radius_detected:.2f}, offset=({hole_offset_x:.1f},{hole_offset_y:.1f})")
            
            # ===== 检测结果质量验证：簇半径过大说明检测到了错误的内簇 =====
            # 孔半径通常 ≤ 4.0mm，如果检测到的簇半径 > 6.0，则间隙检测可能包含了桥接顶点
            if hole_radius_detected > 6.0:
                log_to_file(f"[STEP Exporter] WARNING: Detected cluster radius ({hole_radius_detected:.2f}) too large, detection likely wrong. Discarding.")
                hole_cx_vals = []
                hole_cy_vals = []
        
        # ===== 合理性检查：检测到的孔偏移必须在合理范围内 =====
        # hole_offset_x 应满足: 5.0 <= offset <= half_w - 5.0 (孔不能太靠边或太靠中心)
        # hole_offset_y 应满足: 5.0 <= offset <= half_d - 5.0
        fallback_offset_x = max(5.0, min(half_w * 0.5, half_w - 5.0))
        fallback_offset_y = max(5.0, min(half_d * 0.5, half_d - 5.0))
        log_to_file(f"[STEP Exporter] Fallback hole offsets: ({fallback_offset_x:.1f}, {fallback_offset_y:.1f}) based on half_w={half_w:.1f}, half_d={half_d:.1f}")
        
        if not hole_cx_vals or not hole_cy_vals:
            # 检测完全失败，使用尺寸比例回退值
            hole_offset_x = fallback_offset_x
            hole_offset_y = fallback_offset_y
            log_to_file(f"[STEP Exporter] Hole detection failed, using fallback offsets: ({hole_offset_x:.1f}, {hole_offset_y:.1f})")
        else:
            # 独立检查每个偏移量（不用 elif 链，确保两个都修正）
            x_fixed = False
            y_fixed = False
            if hole_offset_x < 5.0 or hole_offset_x > half_w - 5.0:
                hole_offset_x = fallback_offset_x
                x_fixed = True
            if hole_offset_y < 5.0 or hole_offset_y > half_d - 5.0:
                hole_offset_y = fallback_offset_y
                y_fixed = True
            if x_fixed or y_fixed:
                log_to_file(f"[STEP Exporter] Hole offset out of range corrected: x={x_fixed} y={y_fixed}, final=({hole_offset_x:.1f},{hole_offset_y:.1f})")
    else:
        log_to_file(f"[STEP Exporter] No holes detected (bottom_verts={bottom_vert_count})")
    
    params = {
        'width': width,
        'depth': depth,
        'outer_height': outer_height,
        'bottom_thickness': bottom_thickness,
        'wall_thickness': wall_thickness,
        'corner_radius': corner_radius,
        'outer_fillet_radius': outer_fillet_radius,
        'inner_fillet_radius': inner_fillet_radius,
        'step_height': 1.0,
        'pos_x': obj.location.x,
        'pos_y': obj.location.y,
        'pos_z': obj.location.z,
    }
    
    if has_holes:
        params['has_holes'] = True
        params['hole_radius'] = hole_radius_detected
        params['hole_offset_x'] = hole_offset_x
        params['hole_offset_y'] = hole_offset_y
        log_to_file(f"[STEP Exporter] Final hole params: radius={hole_radius_detected:.2f}, offset=({hole_offset_x:.1f},{hole_offset_y:.1f}), half_w={half_w:.1f}, half_d={half_d:.1f}")
    
    return params


def _analyze_cylinder_from_mesh(obj, context, scale):
    """
    从 mesh 分析识别是否为圆柱/圆锥/空心圆柱类型，并测量所有参数
    
    返回:
        dict: 包含圆柱参数的字典，如果不是圆柱则返回 None
        {
            'type': 'cylinder' | 'cone' | 'hollow_cylinder' | 'hollow_cone',
            'radius': float,          # 圆柱体半径
            'height': float,          # 高度
            'bottom_radius': float,   # 圆锥底部半径
            'top_radius': float,      # 圆锥顶部半径
            'outer_radius': float,    # 空心圆柱外半径
            'inner_radius': float,    # 空心圆柱内半径
            'pos_x': float,
            'pos_y': float,
            'pos_z': float,
        }
    """
    if obj.type != 'MESH':
        return None
    
    import bmesh
    import math
    from collections import defaultdict
    
    log_to_file(f"[STEP Exporter] Analyzing mesh for cylinder: {obj.name}")

    # 如果有台阶内孔定制属性，使用定制参数直接返回（跳过 mesh 分析）
    if obj.get('step_stepped_hole'):
        log_to_file(f"[STEP Exporter]   -> stepped hole custom property detected, using direct params")
        try:
            out_br = obj.get('step_outer_bottom_radius', 25.0)
            out_tr = obj.get('step_outer_top_radius', 22.91)
            h = obj.get('step_height', 60.0)
            sh_r = obj.get('step_small_hole_radius', 2.0)
            sh_h = obj.get('step_small_hole_height', 2.0)
            taper_deg = obj.get('step_inner_taper_deg', 2.0)
            inner_tr = sh_r  # inner top = small hole radius
            inner_br = inner_tr + (h - sh_h) * math.tan(math.radians(taper_deg))
            return {
                'obj_type': 'cone_stepped_hole',
                'outer_bottom_radius': out_br,
                'outer_top_radius': out_tr,
                'height': h,
                'small_hole_radius': sh_r,
                'small_hole_height': sh_h,
                'inner_taper_deg': taper_deg,
                'inner_min_diameter': obj.get('step_inner_min_diameter', 4.0),
                'inner_bottom_radius': inner_br,
                'inner_top_radius': inner_tr,
                'pos_x': obj.location.x,
                'pos_y': obj.location.y,
                'pos_z': obj.location.z,
                'top_feature': None,
                'top_feature_size': 0.0,
                'bottom_feature': None,
                'bottom_feature_size': 0.0,
            }
        except Exception as e:
            log_to_file(f"[STEP Exporter]   -> stepped hole param error: {e}, falling through to mesh analysis")

    depsgraph = context.evaluated_depsgraph_get()
    eval_obj = obj.evaluated_get(depsgraph)
    mesh_data = eval_obj.data
    
    bm = bmesh.new()
    bm.from_mesh(mesh_data)
    bm.verts.ensure_lookup_table()
    
    vertices = bm.verts
    if len(vertices) < 20:
        log_to_file(f"[STEP Exporter] Too few vertices ({len(vertices)}), not a cylinder")
        bm.free()
        return None
    
    # 收集所有顶点的原始坐标
    all_verts = [(v.co.x, v.co.y, v.co.z) for v in vertices]
    
    # 按 Z 坐标分组
    z_layers = defaultdict(list)
    for x, y, z in all_verts:
        z_key = round(z / 0.05) * 0.05
        z_layers[z_key].append((x, y))
    
    sorted_z = sorted(z_layers.keys())
    if len(sorted_z) < 2:
        log_to_file(f"[STEP Exporter] Not enough z-levels ({len(sorted_z)}), not a cylinder")
        bm.free()
        return None
    
    # 过滤掉包含顶点数过少的层（如中心点）
    filtered_sorted_z = [zl for zl in sorted_z if len(z_layers[zl]) >= 4]
    if len(filtered_sorted_z) < 2:
        log_to_file(f"[STEP Exporter] Not enough rich z-levels ({len(filtered_sorted_z)}), not a cylinder")
        bm.free()
        return None
    
    sorted_z = filtered_sorted_z
    
    min_z = sorted_z[0]
    max_z = sorted_z[-1]
    height = max_z - min_z
    
    # 计算中心轴 - 使用底层（最干净的切面）来计算中心
    # 这样即使顶部有倒角/圆角也不影响中心计算
    bottom_z = sorted_z[0]
    top_z = sorted_z[-1]
    
    bottom_pts = z_layers[bottom_z]
    center_x = sum(p[0] for p in bottom_pts) / len(bottom_pts)
    center_y = sum(p[1] for p in bottom_pts) / len(bottom_pts)
    
    # 分析每层的半径分布
    
    def compute_radii(layer_pts):
        """计算层内各点到中心的距离"""
        return [math.sqrt((p[0] - center_x)**2 + (p[1] - center_y)**2) for p in layer_pts]
    
    bottom_radii = compute_radii(z_layers[bottom_z])
    top_radii = compute_radii(z_layers[top_z])
    
    if len(bottom_radii) < 4 or len(top_radii) < 4:
        log_to_file(f"[STEP Exporter] Too few points at bottom/top")
        bm.free()
        return None
    
    # 使用中位数作为半径估计（比均值更抗噪）
    bottom_radii_sorted = sorted(bottom_radii)
    top_radii_sorted = sorted(top_radii)
    
    mid_idx_b = len(bottom_radii_sorted) // 2
    mid_idx_t = len(top_radii_sorted) // 2
    
    bottom_radius = bottom_radii_sorted[mid_idx_b]
    top_radius = top_radii_sorted[mid_idx_t]
    
    # 提前检测是否为空心结构（两圈顶点：外圈+内圈）
    # 如果半径分布有两簇，说明是空心圆柱
    def has_two_clusters(radii_sorted):
        n = len(radii_sorted)
        if n < 16:
            return False, radii_sorted
        # 检查最大值和最小值之间是否有明显 gap
        min_r = radii_sorted[0]
        max_r = radii_sorted[-1]
        if max_r - min_r < max_r * 0.15:
            return False, radii_sorted
        # 找最佳分割点：在半径排序序列中找最大 gap
        best_gap = 0
        best_split = n // 2
        for i in range(n // 4, 3 * n // 4):
            gap = radii_sorted[i] - radii_sorted[i - 1]
            if gap > best_gap:
                best_gap = gap
                best_split = i
        if best_gap > max_r * 0.08:
            return True, radii_sorted[best_split:]  # 返回外圈（较大的值）
        return False, radii_sorted
    
    bottom_is_hollow, bottom_outer_radii = has_two_clusters(bottom_radii_sorted)
    top_is_hollow, top_outer_radii = has_two_clusters(top_radii_sorted)
    might_be_hollow = bottom_is_hollow or top_is_hollow
    
    # 如果是空心结构，用外圈半径重新计算
    if might_be_hollow:
        bo_sorted = sorted(bottom_outer_radii)
        to_sorted = sorted(top_outer_radii)
        bottom_radius = bo_sorted[len(bo_sorted) // 2]
        top_radius = to_sorted[len(to_sorted) // 2]
    
    # 修复：当底部有清晰两簇但顶部因地貌/倒角失去了簇结构时，
    # 从顶部向下扫描，找到最靠近bevel的两簇层来修正top_radius
    # （向下扫描找到的第一个两簇层最接近bevel底部，半径最准）
    if bottom_is_hollow and not top_is_hollow:
        for scan_idx in range(len(sorted_z) - 2, len(sorted_z) // 3, -1):
            scan_zl = sorted_z[scan_idx]
            scan_radii = sorted(compute_radii(z_layers[scan_zl]))
            scan_is_cluster, scan_outer = has_two_clusters(scan_radii)
            if scan_is_cluster:
                so_sorted = sorted(scan_outer)
                top_radius = so_sorted[len(so_sorted) // 2]
                top_outer_radii = scan_outer  # 同时更新用于后续STD检查
                top_is_hollow = True  # 标记为已找到簇，避免STD检查用错数据
                log_to_file(f"[STEP Exporter] Corrected top_radius via cluster scan at z={scan_zl:.2f}: {top_radius:.3f}")
                break
    
    # 半径标准差判断是否为规则圆形
    def radius_std(radii):
        mean_r = sum(radii) / len(radii)
        variance = sum((r - mean_r)**2 for r in radii) / len(radii)
        return math.sqrt(variance)
    
    # 用外圈半径计算标准差（如果空心）
    std_b = radius_std(bottom_outer_radii if might_be_hollow else bottom_radii)
    std_t = radius_std(top_outer_radii if might_be_hollow else top_radii)
    
    # 标准差不大于平均半径的 15% 才认为是规则圆柱
    if std_b > bottom_radius * 0.15 or std_t > top_radius * 0.15:
        log_to_file(f"[STEP Exporter] Radius variance too high: std_b={std_b:.3f} std_t={std_t:.3f}")
        bm.free()
        return None
    
    # 半径不能太小
    if bottom_radius < 0.1 or top_radius < 0.1:
        log_to_file(f"[STEP Exporter] Radius too small: b={bottom_radius:.3f} t={top_radius:.3f}")
        bm.free()
        return None
    
    # 高度不能太小
    if height < 0.5:
        log_to_file(f"[STEP Exporter] Height too small: {height:.3f}")
        bm.free()
        return None
    
    # 检查中间区域是否存在非圆形特征（排除被凹槽/切割/布尔运算修改过的圆柱）
    # 策略: 合并中间高度范围内所有顶点的半径（无论每层顶点多少），
    #        避免因凹槽产生的稀疏层（每层 <4 顶点）被过滤掉
    z_mid_low = min_z + height * 0.20
    z_mid_high = max_z - height * 0.20
    
    # 如果有凹槽定制属性，提前提取凹槽参数（不依赖中间层检测结果）
    has_groove_custom = obj.get('step_groove_depth') is not None
    groove_params = {}
    if has_groove_custom:
        groove_params = {
            'groove_depth': obj['step_groove_depth'],
            'groove_bottom_width': obj.get('step_groove_bottom_width', 0),
            'groove_top_width': obj.get('step_groove_top_width', 0),
            'groove_extrusion_length': obj.get('step_groove_extrusion_length', 0),
        }

    # 如果有台阶内孔定制属性，提前提取参数
    has_stepped_hole_custom = obj.get('step_stepped_hole') is not None
    stepped_hole_params = {}
    if has_stepped_hole_custom:
        stepped_hole_params = {
            'small_hole_radius': obj.get('step_small_hole_radius', 0),
            'small_hole_height': obj.get('step_small_hole_height', 0),
            'inner_taper_deg': obj.get('step_inner_taper_deg', 2.0),
            'inner_min_diameter': obj.get('step_inner_min_diameter', 4.0),
        }
    
    mid_all_radii = []
    for zl_key in z_layers:
        if z_mid_low <= zl_key <= z_mid_high and len(z_layers[zl_key]) >= 1:
            mid_all_radii.extend(compute_radii(z_layers[zl_key]))
    
    if len(mid_all_radii) >= 16:
        mid_sorted = sorted(mid_all_radii)
        # 空心结构: 外圈递归检测子簇（凹槽底面 vs 圆柱表面）
        if might_be_hollow:
            is_cluster, outer_radii = has_two_clusters(mid_sorted)
            if is_cluster and len(outer_radii) >= 8:
                outer_sorted = sorted(outer_radii)
                sub_cluster, _ = has_two_clusters(outer_sorted)
                if sub_cluster:
                    if has_groove_custom:
                        log_to_file(f"[STEP Exporter] Middle region has sub-clusters (groove), "
                                    f"using custom groove parameters for parametric export")
                    else:
                        log_to_file(f"[STEP Exporter] Middle region outer ring has sub-clusters, "
                                    f"mesh has cuts/grooves")
                        bm.free()
                        return None
                mid_sorted = outer_radii
        mean_r = sum(mid_sorted) / len(mid_sorted)
        range_r = max(mid_sorted) - min(mid_sorted)
        if range_r > mean_r * 0.08:
            if has_groove_custom:
                log_to_file(f"[STEP Exporter] Middle region not cleanly circular (groove detected), "
                            f"using custom groove parameters for parametric export")
            else:
                log_to_file(f"[STEP Exporter] Middle region not cleanly circular "
                            f"(range={range_r:.3f} > {mean_r*0.08:.3f}), mesh has cuts/grooves")
                bm.free()
                return None
    
    log_to_file(f"[STEP Exporter] Detected: center=({center_x:.3f},{center_y:.3f}), "
                f"bottom_r={bottom_radius:.3f} top_r={top_radius:.3f}, height={height:.3f}")
    
    # 判断圆柱类型
    radius_ratio = top_radius / bottom_radius if bottom_radius > 0 else 1.0
    
    # 检查是否为空心（在内壁也有顶点层）
    is_hollow = False
    inner_radius = 0.0
    inner_top_radius = 0.0
    
    # 预先计算中段层的范围（两个分支都要用）
    hmid_start = max(0, len(sorted_z) // 4)
    hmid_end = min(len(sorted_z), 3 * len(sorted_z) // 4)
    if hmid_end - hmid_start < 2:
        hmid_start = 0
        hmid_end = len(sorted_z)
    
    # 如果底部或顶部已检测到两簇结构，直接确认空心
    if might_be_hollow or bottom_is_hollow or top_is_hollow:
        # 从底层和顶层分别提取内外半径
        def layer_inner_outer_radii(zl):
            pts = z_layers[zl]
            radii = sorted(compute_radii(pts))
            is_cluster, outer = has_two_clusters(radii)
            if is_cluster:
                n = len(radii)
                inner = radii[:n - len(outer)]
                inner_r = sorted(inner)[len(inner)//2] if inner else 0
                outer_r = sorted(outer)[len(outer)//2] if outer else 0
                return inner_r, outer_r
            else:
                return 0.0, sorted(radii)[len(radii)//2]
        
        # 底部内外半径
        inner_b, outer_b = layer_inner_outer_radii(sorted_z[0])
        # 顶部内外半径
        inner_t, outer_t = layer_inner_outer_radii(sorted_z[-1])
        
        if inner_b > 0.01 and inner_t > 0.01:
            inner_radius = inner_b
            inner_top_radius = inner_t
            outer_radius = max(outer_b, outer_t)
            is_hollow = True
            log_to_file(f"[STEP Exporter] Hollow detected: inner_r(bottom)={inner_b:.3f} inner_r(top)={inner_t:.3f} outer_r={outer_radius:.3f}")
        elif inner_b > 0.01 and bottom_is_hollow:
            # 底部有清晰两簇，但顶部没有（因倒角/圆角破坏了顶部簇结构）
            # 从顶部向下扫描，找到最靠近bevel的两簇层
            for scan_idx in range(len(sorted_z) - 2, len(sorted_z) // 3, -1):
                scan_zl = sorted_z[scan_idx]
                scan_radii = sorted(compute_radii(z_layers[scan_zl]))
                scan_is_cluster, scan_outer = has_two_clusters(scan_radii)
                if scan_is_cluster:
                    n_sc = len(scan_radii)
                    scan_inner = scan_radii[:n_sc - len(scan_outer)]
                    inner_t = sorted(scan_inner)[len(scan_inner)//2] if scan_inner else 0.0
                    outer_t = sorted(scan_outer)[len(scan_outer)//2] if scan_outer else 0.0
                    if inner_t > 0.01:
                        inner_radius = inner_b
                        inner_top_radius = inner_t
                        outer_radius = max(outer_b, outer_t)
                        is_hollow = True
                        log_to_file(f"[STEP Exporter] Hollow detected (scan near wall): inner_r(bottom)={inner_b:.3f} inner_r(top)={inner_t:.3f} outer_r={outer_radius:.3f} at z={scan_zl:.2f}")
                        break
    else:
        # 外层检测未发现两簇，再检查中间层
        hollow_evidence = 0
        
        for i in range(hmid_start, hmid_end):
            zl = sorted_z[i]
            pts = z_layers[zl]
            if len(pts) < 8:
                continue
            all_radii = sorted(compute_radii(pts))
            min_r = all_radii[0]
            max_r = all_radii[-1]
            if max_r - min_r > max_r * 0.2 and max_r > 3.0:
                hollow_evidence += 1
        
        if hollow_evidence >= 2:
            all_mid_radii = []
            for i in range(hmid_start, hmid_end):
                all_mid_radii.extend(compute_radii(z_layers[sorted_z[i]]))
            all_mid_radii_sorted = sorted(all_mid_radii)
            
            gap_idx = len(all_mid_radii_sorted) // 2
            inner_vals = all_mid_radii_sorted[:gap_idx]
            outer_vals = all_mid_radii_sorted[gap_idx:]
            
            inner_radius = sorted(inner_vals)[len(inner_vals)//2]
            outer_radius = sorted(outer_vals)[len(outer_vals)//2]
            inner_top_radius = inner_radius * radius_ratio if (radius_ratio < 0.99 or radius_ratio > 1.01) else inner_radius
            is_hollow = True
            log_to_file(f"[STEP Exporter] Hollow detected (mid-layer): inner_r={inner_radius:.3f} outer_r={outer_radius:.3f}")
    
    # ==== Chamfer/Fillet 过渡检测 ====
    # 策略：
    #   Blender标准圆柱体仅有顶部/底部顶点，中间无分层。
    #   关键判断: 该物体是圆柱本体(大面积恒定半径)还是圆锥本体？
    #     - 圆柱本体: >60%的高度内半径恒定 → 查找顶部/底部过渡
    #     - 圆锥本体: 半径线性变化 → 不检测过渡(锥形就是其本体形状)
    #   过渡区至少2层才分析(chamfer: 过渡起点+终点, fillet: 多种半径层)
    top_feature = None
    top_feature_size = 0.0
    bottom_feature = None
    bottom_feature_size = 0.0
    body_radius = bottom_radius
    
    def _layer_outer_radius(pts):
        radii = sorted(compute_radii(pts))
        n = len(radii)
        if n < 4:
            return None
        if n >= 16:
            is_cluster, outer_vals = has_two_clusters(radii)
            if is_cluster:
                return sorted(outer_vals)[len(outer_vals)//2]
        return sum(radii[n - n//4:]) / max(1, n//4)
    
    # 逐层计算半径
    z_radius_data = {}
    for zl in sorted_z:
        r = _layer_outer_radius(z_layers[zl])
        if r is not None:
            z_radius_data[zl] = r
    
    # 1. 从底部向上找恒定半径区域 → 判断是否为圆柱本体
    body_end_z = sorted_z[0]
    for zl in sorted_z:
        r = z_radius_data.get(zl)
        if r is None:
            continue
        if abs(r - bottom_radius) / max(bottom_radius, 0.01) < 0.01:
            body_end_z = zl
        else:
            break
    
    body_portion = (body_end_z - sorted_z[0]) / height if height > 0 else 0
    cylindrical_body = body_portion > 0.6
    
    # 同时也检查顶部向下是否有恒定半径区域
    if not cylindrical_body:
        body_start_z = sorted_z[-1]
        for zl in reversed(sorted_z):
            r = z_radius_data.get(zl)
            if r is None:
                continue
            if abs(r - top_radius) / max(top_radius, 0.01) < 0.01:
                body_start_z = zl
            else:
                break
        top_body_portion = (sorted_z[-1] - body_start_z) / height if height > 0 else 0
        if top_body_portion > 0.6:
            cylindrical_body = True
            body_radius = top_radius
            # swap direction: body is at top, transition at bottom
            body_end_z = body_start_z
    
    if cylindrical_body:
        body_radius = sorted([z_radius_data.get(zl, body_radius) for zl in sorted_z 
                               if abs(z_radius_data.get(zl, body_radius) - body_radius) / max(body_radius, 0.01) < 0.01
                               and zl in z_radius_data]) or [body_radius]
        body_radius = body_radius[len(body_radius)//2] if isinstance(body_radius, list) else body_radius
        
        # 顶部过渡：body_end_z 以上的所有层
        top_transition_zls = [zl for zl in sorted_z if zl > body_end_z and zl in z_radius_data]
        
        # 如果过渡层不足2层但顶部半径明显偏离，添加上一个本体层作为过渡起点
        if len(top_transition_zls) < 2:
            top_r = z_radius_data.get(sorted_z[-1])
            if top_r is not None and abs(top_r - body_radius) / max(body_radius, 0.01) > 0.01:
                # 找到本体与过渡的分界层
                for i in range(len(sorted_z) - 2, -1, -1):
                    zl = sorted_z[i]
                    if zl not in z_radius_data:
                        continue
                    if abs(z_radius_data[zl] - body_radius) / max(body_radius, 0.01) <= 0.01:
                        top_transition_zls = [sorted_z[j] for j in range(i, len(sorted_z)) if sorted_z[j] in z_radius_data]
                        break
        
        # 底部过渡：body_end_z 以下的层（如果有底部倒角）
        if len(sorted_z) >= 2 and sorted_z[0] < body_end_z:
            bottom_transition_zls = [zl for zl in sorted_z if zl < sorted_z[0] and zl in z_radius_data]
        else:
            bottom_transition_zls = []
    else:
        # 圆锥本体：用线性拟合检测过渡
        # 当Z层稀疏时（中间区域无层），以高度比例分区判断
        top_transition_zls = []
        bottom_transition_zls = []
        fit_zls = None  # will be set if mid-zone fitting is applicable
        valid_zls = [zl for zl in sorted_z if zl in z_radius_data]
        if len(valid_zls) >= 4:
            height = sorted_z[-1] - sorted_z[0]
            # 按高度分区：底15%，中70%，顶15%
            cut_bot = sorted_z[0] + height * 0.15
            cut_top = sorted_z[-1] - height * 0.15
            
            bot_zls = [zl for zl in valid_zls if zl < cut_bot]
            mid_zls = [zl for zl in valid_zls if cut_bot <= zl <= cut_top]
            top_zls = [zl for zl in valid_zls if zl > cut_top]
            
            # 判断：中间足够多层 → 正常锥体；否则 → 只有过渡区有层
            fit_done = False
            if len(mid_zls) >= 3:
                # 正常锥体：用中间层拟合，检测两端偏离
                fit_zls = mid_zls
            elif len(bot_zls) >= 1 and len(top_zls) >= 1:
                # 只有过渡区有层：取底部最上层和顶部最下层作为本体端点
                body_bot_z = bot_zls[-1]  # chamfer顶部
                body_top_z = top_zls[0]   # fillet底部
                body_bot_r = z_radius_data[body_bot_z]
                body_top_r = z_radius_data[body_top_z]
                
                # 本体线性：r = a*z + b
                dz = body_top_z - body_bot_z
                if dz > 0.01:
                    a = (body_top_r - body_bot_r) / dz
                    b = body_bot_r - a * body_bot_z
                    
                    deviation_thresh = max(abs(a) * height * 0.02 + 0.1, 0.3)
                    
                    # 底部过渡检测：任一级别偏离，整个底区视为过渡
                    any_bot_deviation = False
                    for zl in bot_zls:
                        expected_r = a * zl + b
                        actual_r = z_radius_data[zl]
                        if abs(actual_r - expected_r) > deviation_thresh:
                            any_bot_deviation = True
                            break
                    
                    if any_bot_deviation:
                        bottom_transition_zls = bot_zls
                    elif len(bot_zls) >= 2:
                        bot_slope = (z_radius_data[bot_zls[-1]] - z_radius_data[bot_zls[0]]) / (bot_zls[-1] - bot_zls[0])
                        if abs(bot_slope - a) > max(abs(a) * 0.3, 0.05):
                            bottom_transition_zls = bot_zls
                    
                    # 顶部过渡检测：任一级别偏离，整个顶区视为过渡
                    any_top_deviation = False
                    for zl in top_zls:
                        expected_r = a * zl + b
                        actual_r = z_radius_data[zl]
                        if abs(actual_r - expected_r) > deviation_thresh:
                            any_top_deviation = True
                            break
                    
                    if any_top_deviation:
                        top_transition_zls = top_zls
                    elif len(top_zls) >= 2:
                        top_slope = (z_radius_data[top_zls[-1]] - z_radius_data[top_zls[0]]) / (top_zls[-1] - top_zls[0])
                        if abs(top_slope - a) > max(abs(a) * 0.3, 0.05):
                            top_transition_zls = top_zls
                fit_done = True
            else:
                # 中间有层但不足3层：仍用中间层拟合（如果有的话）
                if len(mid_zls) >= 1:
                    fit_zls = mid_zls
                
            if not fit_done and fit_zls is not None and len(fit_zls) >= 3:
                # Linear regression r = a*z + b on fit_zls
                sum_z = sum(zl for zl in fit_zls)
                sum_r = sum(z_radius_data[zl] for zl in fit_zls)
                sz = sum_z / len(fit_zls)
                sr = sum_r / len(fit_zls)
                s_zz = sum((zl - sz) * (zl - sz) for zl in fit_zls)
                s_zr = sum((zl - sz) * (z_radius_data[zl] - sr) for zl in fit_zls)
                
                if s_zz > 0.0001:
                    a = s_zr / s_zz
                    b = sr - a * sz
                    deviation_thresh = max(abs(a) * height * 0.02 + 0.1, 0.3)
                    
                    deviating_top = []
                    deviating_bot = []
                    for zl in valid_zls:
                        expected_r = a * zl + b
                        actual_r = z_radius_data[zl]
                        dev = abs(actual_r - expected_r)
                        if dev > deviation_thresh:
                            if zl > fit_zls[-1]:
                                deviating_top.append(zl)
                            elif zl < fit_zls[0]:
                                deviating_bot.append(zl)
                    
                    top_transition_zls = deviating_top or top_transition_zls
                    bottom_transition_zls = deviating_bot or bottom_transition_zls
    
    # 2. 分析过渡区类型
    def _classify_transition(transition_zls):
        if len(transition_zls) < 2:
            return None, 0.0
        _radii = [(zl, z_radius_data[zl]) for zl in transition_zls if z_radius_data.get(zl) is not None]
        if len(_radii) < 2:
            return None, 0.0
        
        dr = _radii[-1][1] - _radii[0][1]
        threshold = max(body_radius * 0.01, 0.05)
        if abs(dr) < threshold:
            return None, 0.0
        
        slopes = []
        for j in range(1, len(_radii)):
            dz = _radii[j][0] - _radii[j-1][0]
            ds = _radii[j][1] - _radii[j-1][1]
            if dz > 0.0001:
                slopes.append(ds / dz)
        
        if len(slopes) < 1:
            return None, 0.0
        
        avg_slope = abs(sum(slopes) / len(slopes))
        if avg_slope < 0.005:
            return None, 0.0
        
        if len(slopes) >= 3:
            accels = [slopes[j] - slopes[j-1] for j in range(1, len(slopes))]
            avg_accel = sum(abs(a) for a in accels) / len(accels)
        else:
            avg_accel = 0
        
        if avg_accel < max(avg_slope * 0.12, 0.02):
            feature_type = 'chamfer'
            feature_size = abs(dr)
        else:
            feature_type = 'fillet'
            feature_size = (transition_zls[-1] - transition_zls[0]) * 1.0
            if feature_size < 0.5:
                feature_size = abs(dr)
        
        return feature_type, feature_size
    
    top_feature, top_feature_size = _classify_transition(top_transition_zls)
    bottom_feature, bottom_feature_size = _classify_transition(bottom_transition_zls)
    
    # 对于圆柱本体有过渡 → 修正 radius 为 body_radius
    if cylindrical_body and (top_feature or bottom_feature):
        bottom_radius = body_radius
        top_radius = body_radius
    
    bm.free()
    
    pos_x = obj.location.x
    pos_y = obj.location.y
    pos_z = obj.location.z
    
    # 构建返回参数
    if is_hollow:
        if bottom_radius * 0.98 <= top_radius <= bottom_radius * 1.02:
            obj_type = 'hollow_cylinder'
            if top_feature == 'fillet':
                obj_type = 'hollow_cylinder_fillet'
            return {
                'obj_type': obj_type,
                'outer_radius': max(bottom_radius, top_radius),
                'inner_radius': inner_radius,
                'height': height,
                'pos_x': pos_x,
                'pos_y': pos_y,
                'pos_z': pos_z,
                'top_feature': top_feature,
                'top_feature_size': top_feature_size,
                'bottom_feature': bottom_feature,
                'bottom_feature_size': bottom_feature_size,
            }
        else:
            obj_type = 'hollow_cone'
            if top_feature == 'fillet':
                obj_type = 'hollow_cone_fillet'
            if groove_params:
                obj_type = 'hollow_cone_fillet_grooved'
            if stepped_hole_params:
                obj_type = 'cone_stepped_hole'
                # 计算内锥孔底部半径：顶部直孔 r=small_hole_radius, 下部 2° 锥度
                inner_top_r = stepped_hole_params['small_hole_radius']
                inner_bottom_r = inner_top_r + (height - stepped_hole_params['small_hole_height']) * math.tan(math.radians(stepped_hole_params['inner_taper_deg']))
            result = {
                'obj_type': obj_type,
                'outer_bottom_radius': bottom_radius,
                'outer_top_radius': top_radius,
                'inner_bottom_radius': inner_radius,
                'inner_top_radius': inner_top_radius,
                'height': height,
                'pos_x': pos_x,
                'pos_y': pos_y,
                'pos_z': pos_z,
                'top_feature': top_feature,
                'top_feature_size': top_feature_size,
                'bottom_feature': bottom_feature,
                'bottom_feature_size': bottom_feature_size,
            }
            if groove_params:
                result.update(groove_params)
            if stepped_hole_params:
                result.update(stepped_hole_params)
                result['inner_bottom_radius'] = inner_bottom_r
                result['inner_top_radius'] = inner_top_r
            return result
    else:
        if bottom_radius * 0.98 <= top_radius <= bottom_radius * 1.02:
            avg_radius = (bottom_radius + top_radius) / 2.0
            obj_type = 'cylinder'
            if top_feature == 'chamfer':
                obj_type = 'cylinder_chamfer'
            elif top_feature == 'fillet':
                obj_type = 'cylinder_fillet'
            return {
                'obj_type': obj_type,
                'radius': avg_radius,
                'height': height,
                'pos_x': pos_x,
                'pos_y': pos_y,
                'pos_z': pos_z,
                'top_feature': top_feature,
                'top_feature_size': top_feature_size,
                'bottom_feature': bottom_feature,
                'bottom_feature_size': bottom_feature_size,
            }
        else:
            obj_type = 'cone'
            if top_feature and bottom_feature:
                obj_type = 'cone_chamfer_fillet'
            elif top_feature:
                obj_type = 'cone_fillet'
            return {
                'obj_type': obj_type,
                'bottom_radius': body_radius if bottom_feature else bottom_radius,
                'top_radius': top_radius,
                'height': height,
                'pos_x': pos_x,
                'pos_y': pos_y,
                'pos_z': pos_z,
                'top_feature': top_feature,
                'top_feature_size': top_feature_size,
                'bottom_feature': bottom_feature,
                'bottom_feature_size': bottom_feature_size,
            }


def _export_bottom_shells_sync(filepath, shells, step_schema, step_unit, enable_logging, context):
    """同步导出底壳（非计时器版本，直接在 execute 中调用）"""
    import _step_exporter as cpp_exporter
    
    if not shells:
        log_to_file(f"[STEP Exporter] No bottom shells to export")
        return
    
    log_to_file(f"[STEP Exporter] Exporting {len(shells)} shell(s) synchronously...")
    
    all_success = True
    total_shells = len(shells)
    temp_files = []
    
    # 导出每个底壳到临时文件
    for idx, params in enumerate(shells):
        has_holes = params.get('has_holes', False)
        shell_desc = f"with_holes" if has_holes else "no_holes"
        log_to_file(f"[STEP Exporter]   Exporting shell {idx+1}/{total_shells} ({shell_desc})...")
        
        temp_file = filepath + f".temp{idx}.step"
        temp_files.append(temp_file)
        
        if has_holes:
            success = cpp_exporter.export_bottom_shell_filleted_with_holes_step(
                temp_file,
                params['width'],
                params['depth'],
                params['outer_height'],
                params['bottom_thickness'],
                params['wall_thickness'],
                params['corner_radius'],
                params['outer_fillet_radius'],
                params['inner_fillet_radius'],
                params.get('step_height', 1.0),
                params.get('hole_radius', 1.5),
                params.get('hole_offset_x', 25.0),
                params.get('hole_offset_y', 20.0),
                params.get('pos_x', 0.0),
                params.get('pos_y', 0.0),
                params.get('pos_z', 0.0),
                step_schema,
                step_unit,
                1 if enable_logging else 0
            )
        else:
            success = cpp_exporter.export_bottom_shell_filleted_step(
                temp_file,
                params['width'],
                params['depth'],
                params['outer_height'],
                params['bottom_thickness'],
                params['wall_thickness'],
                params['corner_radius'],
                params['outer_fillet_radius'],
                params['inner_fillet_radius'],
                params.get('step_height', 1.0),
                params.get('pos_x', 0.0),
                params.get('pos_y', 0.0),
                params.get('pos_z', 0.0),
                step_schema,
                step_unit,
                1 if enable_logging else 0
            )
        
        if not success:
            all_success = False
            log_to_file(f"[STEP Exporter]   FAILED to export shell {idx+1}")
        else:
            log_to_file(f"[STEP Exporter]   Shell {idx+1} exported successfully")
    
    # 合并或复制最终文件
    if all_success and total_shells > 1:
        try:
            _merge_step_files(filepath, temp_files)
            log_to_file(f"[STEP Exporter] Merged {total_shells} shells into {filepath}")
        except Exception as merge_err:
            log_to_file(f"[STEP Exporter] Failed to merge STEP files: {merge_err}")
            import traceback
            log_to_file(traceback.format_exc())
            # 合并失败时至少保留第一个文件
            if os.path.exists(temp_files[0]):
                try:
                    import shutil
                    shutil.copy2(temp_files[0], filepath)
                except:
                    pass
        finally:
            # 清理临时文件及其日志
            for tf in temp_files:
                for ext in ('', '.log'):
                    try:
                        if os.path.exists(tf + ext):
                            os.remove(tf + ext)
                    except:
                        pass
    elif all_success and total_shells == 1:
        try:
            os.replace(temp_files[0], filepath)
        except:
            import shutil
            shutil.copy2(temp_files[0], filepath)
        finally:
            for ext in ('', '.log'):
                try:
                    if os.path.exists(temp_files[0] + ext):
                        os.remove(temp_files[0] + ext)
                except:
                    pass
    else:
        log_to_file(f"[STEP Exporter] Some shells failed to export, no output written")
    
    if all_success:
        update_progress(100, "底壳导出完成", context)
        log_to_file(f"[STEP Exporter] All {total_shells} bottom shell(s) exported successfully")
    else:
        update_progress(100, "部分底壳导出失败", context)
        log_to_file(f"[STEP Exporter] Some bottom shells failed to export")


def _export_bottom_shell_timer():
    global _bottom_shell_export_data

    if not _bottom_shell_export_data:
        return None

    try:
        data = _bottom_shell_export_data
        context = data['context']
        shells = data.get('shells', [])
        cylinders = data.get('cylinders', [])
        regular_objects = data.get('regular_objects', [])
        
        if not shells and not cylinders and not regular_objects:
            log_to_file(f"[STEP Exporter] No objects to export")
            end_progress(context)
            _bottom_shell_export_data = None
            return None

        total_objects = len(shells) + len(cylinders) + len(regular_objects)
        log_to_file(f"[STEP Exporter] Parametric timer: exporting {len(shells)} shell(s) + {len(cylinders)} cylinder(s) + {len(regular_objects)} mesh(es)...")
        
        import _step_exporter as cpp_exporter
        
        all_success = True
        temp_files = []
        temp_idx = 0
        
        # 导出每个底壳到临时文件
        for idx, params in enumerate(shells):
            has_holes = params.get('has_holes', False)
            shell_desc = f"with_holes" if has_holes else "no_holes"
            log_to_file(f"[STEP Exporter]   Exporting shell {idx+1}/{len(shells)} ({shell_desc})...")
            
            temp_file = data['filepath'] + f".temp{temp_idx}.step"
            temp_files.append(temp_file)
            temp_idx += 1
            
            if has_holes:
                success = cpp_exporter.export_bottom_shell_filleted_with_holes_step(
                    temp_file,
                    params['width'],
                    params['depth'],
                    params['outer_height'],
                    params['bottom_thickness'],
                    params['wall_thickness'],
                    params['corner_radius'],
                    params['outer_fillet_radius'],
                    params['inner_fillet_radius'],
                    params.get('step_height', 1.0),
                    params.get('hole_radius', 1.5),
                    params.get('hole_offset_x', 25.0),
                    params.get('hole_offset_y', 20.0),
                    params.get('pos_x', 0.0),
                    params.get('pos_y', 0.0),
                    params.get('pos_z', 0.0),
                    data['step_schema'],
                    data['step_unit'],
                    1 if data['enable_logging'] else 0
                )
            else:
                success = cpp_exporter.export_bottom_shell_filleted_step(
                    temp_file,
                    params['width'],
                    params['depth'],
                    params['outer_height'],
                    params['bottom_thickness'],
                    params['wall_thickness'],
                    params['corner_radius'],
                    params['outer_fillet_radius'],
                    params['inner_fillet_radius'],
                    params.get('step_height', 1.0),
                    params.get('pos_x', 0.0),
                    params.get('pos_y', 0.0),
                    params.get('pos_z', 0.0),
                    data['step_schema'],
                    data['step_unit'],
                    1 if data['enable_logging'] else 0
                )
            
            if not success:
                all_success = False
                log_to_file(f"[STEP Exporter]   FAILED to export shell {idx+1}")
            else:
                log_to_file(f"[STEP Exporter]   Shell {idx+1} exported successfully")
        
        # 导出每个圆柱体/圆锥体到临时文件
        for idx, cparams in enumerate(cylinders):
            obj_type = cparams.get('obj_type', 'cylinder')
            log_to_file(f"[STEP Exporter]   Exporting {obj_type} {idx+1}/{len(cylinders)}...")
            
            temp_file = data['filepath'] + f".temp{temp_idx}.step"
            temp_files.append(temp_file)
            temp_idx += 1
            
            px = cparams.get('pos_x', 0.0)
            py = cparams.get('pos_y', 0.0)
            pz = cparams.get('pos_z', 0.0)
            
            if obj_type == 'cylinder':
                success = cpp_exporter.export_cylinder_step(
                    temp_file,
                    cparams['radius'],
                    cparams['height'],
                    px, py, pz,
                    data['step_schema'],
                    data['step_unit'],
                    1 if data['enable_logging'] else 0
                )
            elif obj_type == 'cone':
                success = cpp_exporter.export_cone_step(
                    temp_file,
                    cparams['bottom_radius'],
                    cparams['top_radius'],
                    cparams['height'],
                    px, py, pz,
                    data['step_schema'],
                    data['step_unit'],
                    1 if data['enable_logging'] else 0
                )
            elif obj_type == 'hollow_cylinder':
                success = cpp_exporter.export_hollow_cylinder_step(
                    temp_file,
                    cparams['outer_radius'],
                    cparams['inner_radius'],
                    cparams['height'],
                    px, py, pz,
                    data['step_schema'],
                    data['step_unit'],
                    1 if data['enable_logging'] else 0
                )
            elif obj_type == 'hollow_cone':
                success = cpp_exporter.export_hollow_cone_step(
                    temp_file,
                    cparams['outer_bottom_radius'],
                    cparams['outer_top_radius'],
                    cparams['inner_bottom_radius'],
                    cparams['inner_top_radius'],
                    cparams['height'],
                    px, py, pz,
                    data['step_schema'],
                    data['step_unit'],
                    1 if data['enable_logging'] else 0
                )
            elif obj_type == 'cylinder_chamfer':
                success = cpp_exporter.export_cylinder_chamfer_step(
                    temp_file,
                    cparams['radius'],
                    cparams['height'],
                    cparams.get('top_feature_size', 0),
                    px, py, pz,
                    data['step_schema'],
                    data['step_unit'],
                    1 if data['enable_logging'] else 0
                )
            elif obj_type == 'cylinder_fillet':
                success = cpp_exporter.export_cylinder_fillet_step(
                    temp_file,
                    cparams['radius'],
                    cparams['height'],
                    cparams.get('top_feature_size', 0),
                    px, py, pz,
                    data['step_schema'],
                    data['step_unit'],
                    1 if data['enable_logging'] else 0
                )
            elif obj_type == 'cone_chamfer_fillet':
                success = cpp_exporter.export_cone_chamfer_fillet_step(
                    temp_file,
                    cparams.get('bottom_radius', cparams.get('radius', 0)),
                    cparams.get('top_radius', 0),
                    cparams['height'],
                    cparams.get('bottom_feature_size', 0),
                    cparams.get('top_feature_size', 0),
                    px, py, pz,
                    data['step_schema'],
                    data['step_unit'],
                    1 if data['enable_logging'] else 0
                )
            elif obj_type == 'hollow_cone_fillet':
                success = cpp_exporter.export_hollow_cone_fillet_step(
                    temp_file,
                    cparams.get('outer_bottom_radius', cparams.get('outer_radius', 0)),
                    cparams.get('outer_top_radius', cparams.get('outer_radius', 0)),
                    cparams.get('inner_bottom_radius', cparams.get('inner_radius', 0)),
                    cparams.get('inner_top_radius', cparams.get('inner_radius', 0)),
                    cparams['height'],
                    cparams.get('top_feature_size', 0),
                    px, py, pz,
                    data['step_schema'],
                    data['step_unit'],
                    1 if data['enable_logging'] else 0
                )
            elif obj_type == 'hollow_cone_fillet_grooved':
                success = cpp_exporter.export_hollow_cone_fillet_with_groove_step(
                    temp_file,
                    cparams.get('outer_bottom_radius', cparams.get('outer_radius', 0)),
                    cparams.get('outer_top_radius', cparams.get('outer_radius', 0)),
                    cparams.get('inner_bottom_radius', cparams.get('inner_radius', 0)),
                    cparams.get('inner_top_radius', cparams.get('inner_radius', 0)),
                    cparams['height'],
                    cparams.get('top_feature_size', 0),
                    cparams.get('groove_depth', 0),
                    cparams.get('groove_bottom_width', 0),
                    cparams.get('groove_top_width', 0),
                    cparams.get('groove_extrusion_length', 0),
                    px, py, pz,
                    data['step_schema'],
                    data['step_unit'],
                    1 if data['enable_logging'] else 0
                )
            elif obj_type == 'cone_stepped_hole':
                success = cpp_exporter.export_cone_stepped_hole_step(
                    temp_file,
                    cparams.get('outer_bottom_radius', cparams.get('outer_radius', 0)),
                    cparams.get('outer_top_radius', cparams.get('outer_radius', 0)),
                    cparams['height'],
                    cparams.get('small_hole_radius', 0),
                    cparams.get('small_hole_height', 0),
                    cparams.get('inner_bottom_radius', cparams.get('inner_radius', 0)),
                    cparams.get('inner_top_radius', cparams.get('inner_radius', 0)),
                    px, py, pz,
                    data['step_schema'],
                    data['step_unit'],
                    1 if data['enable_logging'] else 0
                )
            elif obj_type == 'cone_fillet':
                success = cpp_exporter.export_cone_chamfer_fillet_step(
                    temp_file,
                    cparams.get('bottom_radius', 0),
                    cparams.get('top_radius', 0),
                    cparams['height'],
                    0.0,  # no chamfer
                    cparams.get('top_feature_size', 0),
                    px, py, pz,
                    data['step_schema'],
                    data['step_unit'],
                    1 if data['enable_logging'] else 0
                )
            elif obj_type == 'hollow_cylinder_fillet':
                success = cpp_exporter.export_hollow_cylinder_fillet_step(
                    temp_file,
                    cparams.get('outer_radius', 0),
                    cparams.get('inner_radius', 0),
                    cparams['height'],
                    cparams.get('top_feature_size', 0),
                    px, py, pz,
                    data['step_schema'],
                    data['step_unit'],
                    1 if data['enable_logging'] else 0
                )
            else:
                log_to_file(f"[STEP Exporter]   Unknown cylinder type: {obj_type}")
                success = False
            
            if not success:
                all_success = False
                log_to_file(f"[STEP Exporter]   FAILED to export {obj_type} {idx+1}")
            else:
                log_to_file(f"[STEP Exporter]   {obj_type} {idx+1} exported successfully")
        
        # 导出每个常规 mesh 对象到临时文件（使用 incremental API）
        for idx, obj in enumerate(regular_objects):
            log_to_file(f"[STEP Exporter]   Exporting mesh obj {idx+1}/{len(regular_objects)}: {obj.name}...")
            
            temp_file = data['filepath'] + f".temp{temp_idx}.step"
            temp_files.append(temp_file)
            temp_idx += 1
            
            try:
                obj_data = _get_mesh_data_enhanced(obj, context, scale=1000.0)
                if obj_data is None:
                    raise RuntimeError("_get_mesh_data_enhanced returned None")
                
                # 设置日志回调供 C++ 使用
                global _cpp_log_callback
                _cpp_log_callback = lambda msg: log_to_file(msg)
                
                # 使用 incremental API 导出单个 mesh
                init_ok = cpp_exporter.init_incremental_export(
                    temp_file, 1, 1000.0,
                    1 if data['fix_geometry'] else 0,
                    1 if data['create_solid'] else 0,
                    1 if data['advanced_brep'] else 0,
                    data['step_schema'],
                    data['step_unit'],
                    1 if data['enable_logging'] else 0,
                    data.get('sew_tolerance', 0.001),
                    _cpp_log_callback
                )
                if init_ok:
                    add_ok = cpp_exporter.add_object_to_export(obj_data, None)
                    cpp_exporter.finalize_incremental_export()
                    if add_ok:
                        log_to_file(f"[STEP Exporter]   Mesh {obj.name} exported ({len(obj_data['vertices'])} verts, {len(obj_data['faces'])} tris)")
                    else:
                        all_success = False
                        log_to_file(f"[STEP Exporter]   FAILED to add mesh object {obj.name}")
                else:
                    all_success = False
                    log_to_file(f"[STEP Exporter]   FAILED to init incremental export for {obj.name}")
            except Exception as mesh_exp_err:
                all_success = False
                log_to_file(f"[STEP Exporter]   ERROR exporting mesh {obj.name}: {mesh_exp_err}")
                import traceback
                log_to_file(traceback.format_exc())
        
        # 合并所有临时文件到最终的 STEP 文件
        if all_success and total_objects > 1:
            try:
                _merge_step_files(data['filepath'], temp_files)
                log_to_file(f"[STEP Exporter] Merged {total_objects} objects into {data['filepath']}")
            except Exception as merge_err:
                log_to_file(f"[STEP Exporter] Failed to merge STEP files: {merge_err}")
                import traceback
                log_to_file(traceback.format_exc())
                # 合并失败时至少保留第一个文件
                if os.path.exists(temp_files[0]):
                    try:
                        import shutil
                        shutil.copy2(temp_files[0], data['filepath'])
                    except:
                        pass
            finally:
                # 合并C++子进程产出的log文件（在清理前）
                try:
                    _merge_log_files(os.path.dirname(data['filepath']), data['filepath'])
                except:
                    pass
                # 清理临时文件及其日志
                for tf in temp_files:
                    for ext in ('', '.log'):
                        try:
                            if os.path.exists(tf + ext):
                                os.remove(tf + ext)
                        except:
                            pass
        elif all_success and total_objects == 1:
            try:
                os.replace(temp_files[0], data['filepath'])
            except:
                import shutil
                shutil.copy2(temp_files[0], data['filepath'])
            finally:
                # 合并C++子进程产出的log文件（在清理前）
                try:
                    _merge_log_files(os.path.dirname(data['filepath']), data['filepath'])
                except:
                    pass
                for ext in ('', '.log'):
                    try:
                        if os.path.exists(temp_files[0] + ext):
                            os.remove(temp_files[0] + ext)
                    except:
                        pass
        
        if all_success:
            update_progress(100, "参数化导出完成", context)
            log_to_file(f"[STEP Exporter] All {total_objects} parametric object(s) exported successfully")
        else:
            update_progress(100, "部分对象导出失败", context)
            log_to_file(f"[STEP Exporter] Some parametric objects failed to export")

        end_progress(context)
    except Exception as e:
        log_to_file(f"[STEP Exporter] CRITICAL ERROR in timer: {e}")
        import traceback
        log_to_file(traceback.format_exc())
        try:
            end_progress(context)
        except:
            pass
    finally:
        _bottom_shell_export_data = None
        # 关闭日志文件
        global _export_log_file
        if _export_log_file and not _export_log_file.closed:
            try:
                _export_log_file.close()
            except:
                pass
        return None


def _merge_step_files(output_path, temp_files):
    """将多个 STEP 文件合并为一个，重新编号实体 ID"""
    import re
    
    header = None
    all_data_sections = []
    max_entity_id = 0
    
    # 实体 ID 匹配: #12345=... 
    entity_re = re.compile(r'^#(\d+)\s*=(.*)$')
    entity_ref_re = re.compile(r'#(\d+)')
    
    for filepath in temp_files:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 分离 HEADER 和 DATA
        parts = content.split('DATA;')
        if len(parts) < 2:
            raise ValueError(f"Invalid STEP file: {filepath}")
        
        data_part = parts[1]
        ends_index = data_part.rfind('ENDSEC;')
        if ends_index == -1:
            raise ValueError(f"No ENDSEC found in {filepath}")
        
        data_content = data_part[:ends_index].strip()
        
        if header is None:
            header = parts[0] + 'DATA;'
        
        all_data_sections.append(data_content)
    
    # 收集所有实体，重新编号
    merged_entities = []
    for section in all_data_sections:
        # 分割实体（以分号结尾，后面跟换行或下一个 #）
        # 更简单的方法：按 #\d+= 分割
        entities = []
        current_entity = None
        current_id = None
        
        for line in section.replace('\r', '').split('\n'):
            m = entity_re.match(line.strip())
            if m:
                # 保存上一个实体
                if current_entity is not None:
                    entities.append((current_id, current_entity))
                current_id = int(m.group(1))
                current_entity = line.strip()
            else:
                if current_entity is not None:
                    current_entity += '\n' + line.strip()
        
        # 保存最后一个实体
        if current_entity is not None:
            entities.append((current_id, current_entity))
        
        # 重新编号这个 section 的实体
        # 需要先计算偏移量
        id_shift = max_entity_id
        
        for old_id, entity_text in entities:
            new_id = old_id + id_shift
            max_entity_id = max(max_entity_id, new_id)
            
            # 替换实体自身的 ID: #old_id ␣= -> #new_id ␣=
            eq_pos = entity_text.find('=')
            # entity_text 格式: "#_{old_id}_=_REST"
            # 精确保留 '=' 之后的空格/字符，只替换 ID 部分
            entity_text = f'#{new_id}' + entity_text[eq_pos:]
            
            # 替换引用中的 #N（在 '=' 之后的部分）
            def replace_ref(match):
                ref_id = int(match.group(1))
                return f'#{ref_id + id_shift}'
            
            rest = entity_text[eq_pos + 1:]
            rest = entity_ref_re.sub(replace_ref, rest)
            entity_text = entity_text[:eq_pos + 1] + rest
            
            merged_entities.append((new_id, entity_text))
    
    # 写入合并后的文件
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(header + '\n')
        for _, entity in merged_entities:
            if not entity.endswith(';'):
                entity += ';'
            f.write(entity + '\n')
        f.write('ENDSEC;\nEND-ISO-10303-21;\n')


def _merge_log_files(output_dir, output_path):
    """将同目录下其他 .step.log 文件中的 [STEP Exporter] 行合并到主日志文件"""
    import re
    
    if not _export_log_file or _export_log_file.closed:
        return
    
    try:
        log_dir = os.path.dirname(output_path)
        main_log_basename = os.path.basename(output_path) + ".log"
        
        # 查找同目录下所有 .step.log 文件
        for fname in sorted(os.listdir(log_dir)):
            if fname == main_log_basename:
                continue
            if not fname.endswith('.step.log') and not fname.endswith('.step.log.temp'):
                continue
            
            log_path = os.path.join(log_dir, fname)
            try:
                with open(log_path, 'r', encoding='utf-8', errors='ignore') as lf:
                    content = lf.read()
                # 提取 [STEP Exporter] 开头的行
                step_lines = re.findall(r'\[STEP Exporter\].*', content)
                if step_lines:
                    _export_log_file.write(f"\n--- Merged from {fname} ---\n")
                    for line in step_lines:
                        if not line.endswith('\n'):
                            line += '\n'
                        _export_log_file.write(line)
                    _export_log_file.flush()
            except:
                pass
    except:
        pass


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
            
            # 合并C++子进程产出的log文件
            try:
                _merge_log_files(os.path.dirname(filepath), filepath)
            except:
                pass
            
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
                log_to_file(f"[STEP Exporter] Failed to open log file: {e}")
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
        
        # 尽早打开日志文件，确保所有 [STEP Exporter] 日志都写入 .step.log
        global _export_log_file, _log_buffer
        if _export_log_file is None or _export_log_file.closed:
            try:
                log_path = self.filepath + ".log"
                _export_log_file = open(log_path, 'w', encoding='utf-8')
                # 将之前缓冲的消息写入日志文件
                if _log_buffer:
                    for buf_msg in _log_buffer:
                        _export_log_file.write(buf_msg)
                    _export_log_file.flush()
                    _log_buffer = []
            except:
                pass
        
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
        global _export_params, _export_stage, _export_objects, _export_objects_data, _export_current_index
        
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
        
        # 检测底壳和圆柱对象，使用参数化导出
        bottom_shells = []
        cylinder_objects = []
        regular_export_objects = []
        
        for obj in _export_objects:
            if obj.type == 'MESH':
                log_to_file(f"[STEP Exporter] Checking: {obj.name}")
                
                # 先检测底壳
                shell_params = _analyze_bottom_shell_from_mesh(obj, context, scale)
                if shell_params:
                    bottom_shells.append(shell_params)
                    hh = shell_params.get('has_holes', False)
                    log_to_file(f"[STEP Exporter]   -> Bottom shell! has_holes={hh}")
                    log_to_file(f"[STEP Exporter] Found bottom shell: {obj.name} (has_holes={shell_params.get('has_holes', False)})")
                    continue
                
                # 再检测圆柱/圆锥
                cyl_params = _analyze_cylinder_from_mesh(obj, context, scale)
                if cyl_params:
                    cylinder_objects.append(cyl_params)
                    log_to_file(f"[STEP Exporter]   -> {cyl_params['obj_type']}! r={cyl_params.get('radius', cyl_params.get('bottom_radius', '?'))} h={cyl_params['height']}")
                    log_to_file(f"[STEP Exporter] Found {cyl_params['obj_type']}: {obj.name}")
                    continue
                
                log_to_file(f"[STEP Exporter]   -> NOT a parametric object")
                regular_export_objects.append(obj)
            elif obj.type == 'CURVE':
                regular_export_objects.append(obj)
        
        total_parametric = len(bottom_shells) + len(cylinder_objects)
        log_to_file(f"[STEP Exporter] Total objects: {len(_export_objects)}, shells: {len(bottom_shells)}, cylinders: {len(cylinder_objects)}, regular: {len(regular_export_objects)}")
        
        if bottom_shells or cylinder_objects:
            log_to_file(f"[STEP Exporter] Found {total_parametric} parametric object(s) (+ {len(regular_export_objects)} regular), using parametric export")
            update_progress(10, "检测到参数化对象，正在导出...", context)

            # 日志文件已在 execute() 开头打开，此处确保可用即可

            global _bottom_shell_export_data
            _bottom_shell_export_data = {
                'filepath': self.filepath,
                'shells': bottom_shells,
                'cylinders': cylinder_objects,
                'regular_objects': regular_export_objects,
                'step_schema': self.step_schema,
                'step_unit': step_unit,
                'enable_logging': self.enable_logging,
                'fix_geometry': self.fix_geometry,
                'create_solid': self.create_solid,
                'advanced_brep': self.advanced_brep,
                'sew_tolerance': self.sew_tolerance,
                'context': context,
            }

            timer_handle = bpy.app.timers.register(_export_bottom_shell_timer, first_interval=0.3)
            log_to_file(f"[STEP Exporter] Timer registered: {timer_handle}")
            self.report({'INFO'}, f"检测到 {total_parametric} 个参数化对象（{len(bottom_shells)}底壳 + {len(cylinder_objects)}圆柱），正在导出...")
            return {'FINISHED'}
        
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
        
        # 关闭日志文件（非参数化路径）
        if _export_log_file and not _export_log_file.closed:
            _export_log_file.close()
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
    
    log_to_file("[STEP Exporter] Enhanced plugin registered successfully")

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
    
    log_to_file("[STEP Exporter] Plugin unregistered")

# 直接运行时的测试
if __name__ == "__main__":
    # 清理之前的注册（如果存在）
    try:
        unregister()
    except:
        pass
    
    # 重新注册
    register()