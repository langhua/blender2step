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
from bpy.props import StringProperty, FloatProperty, IntProperty, BoolProperty, EnumProperty

# 进度报告系统
from .progress_report import (
                             start_progress, update_progress, end_progress,
                             set_operator, clear_operator,
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
_export_complete = False  # 异步导出完成标志
_export_success = False   # 异步导出成功标志
_export_start_time = 0.0  # 导出开始时间
_stage_start_time = 0.0   # 阶段开始时间
# 参数化异步导出状态（分阶段，每个对象一个timer tick）
_parametric_export_stage = 0
_parametric_export_idx = 0
_parametric_temp_files = []
_parametric_progress_val = 0.0
_parametric_temp_success_count = 0

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

# 模块版本标记 - 确认新代码已加载
_log_init_time = __import__('time').strftime('%H:%M:%S')
log_to_file(f"[STEP Exporter] [MODULE:v3] __init__.py loaded at {_log_init_time}")

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
        # 直接使用 obj.data，因为修改器已经被应用
        eval_mesh = obj.data
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

def _analyze_top_shell_from_mesh(obj, context, scale):
    """
    从 mesh 分析识别是否为顶壳类型（锥形/渐变截面），并测量所有参数
    顶壳特征：顶部面顶点数显著少于底部开口（vratio < 0.75）
    
    返回:
        dict: 包含顶壳参数的字典，如果不是顶壳则返回 None
    """
    if obj.type != 'MESH':
        return None
    
    import bmesh
    import math
    from collections import defaultdict
    
    log_to_file(f"[STEP Exporter] Analyzing mesh for TOP shell: {obj.name}")
    
    depsgraph = context.evaluated_depsgraph_get()
    eval_obj = obj.evaluated_get(depsgraph)
    mesh_data = eval_obj.data
    
    bm = bmesh.new()
    bm.from_mesh(mesh_data)
    bm.verts.ensure_lookup_table()
    
    vertices = bm.verts
    if len(vertices) < 100:
        log_to_file(f"[STEP Exporter] Too few vertices ({len(vertices)}), not a top shell")
        bm.free()
        return None
    
    # Z层分析
    z_layers = defaultdict(list)
    for v in vertices:
        z_key = round(v.co.z / 0.01) * 0.01
        z_layers[z_key].append(v)
    
    sorted_z_levels = sorted(z_layers.keys())
    if len(sorted_z_levels) < 2:
        log_to_file(f"[STEP Exporter] Not enough z-levels, not a top shell")
        bm.free()
        return None
    
    min_z = sorted_z_levels[0]
    max_z = sorted_z_levels[-1]
    bottom_z = min_z
    top_z = max_z
    outer_height = top_z - bottom_z
    
    bottom_verts = z_layers[bottom_z]
    top_verts = z_layers[top_z]
    
    if len(bottom_verts) < 50 or len(top_verts) < 8:
        log_to_file(f"[STEP Exporter] No clear bottom/top planes, not a top shell")
        bm.free()
        return None
    
    # 关键判断：top面顶点应显著少于bottom（因为top面内收，面积小）
    top_vcount = len(top_verts)
    bot_vcount = len(bottom_verts)
    vratio = top_vcount / max(bot_vcount, 1)
    log_to_file(f"[STEP Exporter] Vertex count: top={top_vcount}, bottom={bot_vcount}, ratio={vratio:.3f}")
    
    if vratio >= 0.75:
        log_to_file(f"[STEP Exporter] Top-face vertex ratio >= 0.75 → NOT a top shell")
        bm.free()
        return None
    
    log_to_file(f"[STEP Exporter] Top-face has fewer vertices → TOP shell candidate")
    
    # === 计算底部（开口端）的外轮廓尺寸 ===
    bottom_coords = [(v.co.x, v.co.y, v.co.z) for v in bottom_verts]
    
    # === 圆形轮廓检测：排除圆柱体误判为顶壳 ===
    # 计算底部顶点到中心的距离，如果接近圆形则不是顶壳
    bot_dists = [math.sqrt(x*x + y*y) for x, y, z in bottom_coords]
    if bot_dists:
        mean_dist = sum(bot_dists) / len(bot_dists)
        log_to_file(f"[STEP Exporter] Top-shell circularity check: mean_dist={mean_dist:.4f}, n={len(bot_dists)}")
        if mean_dist > 0.001:
            std_dist = math.sqrt(sum((d - mean_dist)**2 for d in bot_dists) / len(bot_dists))
            circularity = std_dist / mean_dist  # 越小越圆
            log_to_file(f"[STEP Exporter] Top-shell circularity: std={std_dist:.4f}, circ={circularity:.4f}")
            if circularity < 0.05:
                log_to_file(f"[STEP Exporter] Bottom contour is circular (circ={circularity:.3f}) → NOT a top shell (likely cylinder)")
                bm.free()
                return None
        else:
            log_to_file(f"[STEP Exporter] Top-shell mean_dist too small ({mean_dist:.4f}) → likely not a shell")
    
    bottom_x_vals = [x for x, y, z in bottom_coords]
    bottom_y_vals = [y for x, y, z in bottom_coords]
    bot_width = max(bottom_x_vals) - min(bottom_x_vals)
    bot_depth = max(bottom_y_vals) - min(bottom_y_vals)
    bot_cx = (max(bottom_x_vals) + min(bottom_x_vals)) / 2.0
    bot_cy = (max(bottom_y_vals) + min(bottom_y_vals)) / 2.0

    log_to_file(f"[STEP Exporter] Bottom contour: {bot_width:.4f}x{bot_depth:.4f}, center=({bot_cx:.4f},{bot_cy:.4f})")

    # === 计算顶部（封闭面）的轮廓尺寸 ===
    top_coords = [(v.co.x, v.co.y, v.co.z) for v in top_verts]

    if top_coords:
        top_x_vals = [x for x, y, z in top_coords]
        top_y_vals = [y for x, y, z in top_coords]
        top_width = max(top_x_vals) - min(top_x_vals)
        top_depth = max(top_y_vals) - min(top_y_vals)
        top_cx = (max(top_x_vals) + min(top_x_vals)) / 2.0
        top_cy = (max(top_y_vals) + min(top_y_vals)) / 2.0
    else:
        top_width = 0
        top_depth = 0
        top_cx = bot_cx
        top_cy = bot_cy

    # 顶壳经过 180° X 翻转后，宽面可能在顶部(max_z)，窄面在底部(min_z)
    # 确保 width/depth 取自宽面（外壳轮廓），top_width/top_depth 取自窄面
    if bot_width < top_width:
        log_to_file(f"[STEP Exporter] Bottom is narrow face, top is wide face -> swapping")
        width, depth, cx, cy = top_width, top_depth, top_cx, top_cy
        top_width, top_depth, top_cx, top_cy = bot_width, bot_depth, bot_cx, bot_cy
    else:
        width, depth, cx, cy = bot_width, bot_depth, bot_cx, bot_cy

    half_w = width / 2.0
    half_d = depth / 2.0
    log_to_file(f"[STEP Exporter] Outer (wide) contour: {width:.4f}x{depth:.4f}, center=({cx:.4f},{cy:.4f})")
    log_to_file(f"[STEP Exporter] Inner (narrow) contour: {top_width:.4f}x{top_depth:.4f}, center=({top_cx:.4f},{top_cy:.4f})")

    if top_coords:
        top_recess_x = (width - top_width) / 2.0
        top_recess_y = (depth - top_depth) / 2.0
        top_recess = max(top_recess_x, top_recess_y)
        top_offset_y = top_cy - cy  # 正值表示顶部向+Y偏移
        
        log_to_file(f"[STEP Exporter] Top recess={top_recess:.1f}, Y offset={top_offset_y:.1f}")
    else:
        top_recess = 10.0
        top_offset_y = 0.0
    
    # === 顶壁厚度分析 ===
    top_thickness = 1.5
    # 找顶部Z层群（top面及其下方的填充层）
    top_z_layer_verts = []
    for z_level in sorted_z_levels:
        if z_level > top_z - 2.0:
            top_z_layer_verts.extend([(v.co.x, v.co.y, v.co.z) for v in z_layers[z_level]])
    
    if top_z_layer_verts:
        z_vals = [z for x, y, z in top_z_layer_verts]
        if min(z_vals) < top_z:
            top_thickness = top_z - min(z_vals)
            if top_thickness < 0.5:
                top_thickness = 1.5
    log_to_file(f"[STEP Exporter] Top thickness: {top_thickness:.2f}")
    
    # === 壁厚分析 ===
    # 优先从自定义属性读取（由 create_filleted_top_shell 设置）
    custom_wt = obj.get('wall_thickness', 0.0)
    if custom_wt > 0:
        wall_thickness = custom_wt
        log_to_file(f"[STEP Exporter] Wall thickness from custom property: {wall_thickness:.2f}mm")
    else:
        # 壁厚 = 外轮廓边界框 - 内轮廓边界框，避开台阶环和圆角顶点
        # 找底部区域上方第一个不含台阶环的Z层（顶点数80-150，非最大Z层）
        bottom_region_zls = [z for z in sorted_z_levels if z <= bottom_z + 3.0]
        wall_thickness = 2.0
        if len(bottom_region_zls) >= 2:
            # 找台阶环顶Z层（底部区域顶点数最多的Z层，通常是台阶环和外壁共用的底部）
            max_z = bottom_region_zls[0]
            max_n = len(z_layers[max_z])
            for z in bottom_region_zls[1:]:
                n = len(z_layers[z])
                if n > max_n:
                    max_n = n
                    max_z = z
            log_to_file(f"[STEP Exporter] Wall bottom Z={max_z:.2f} ({max_n}v), min Z={bottom_z:.2f}")

            # 在台阶环顶Z层上方 0.3mm 以上找一个顶点数合理的Z层（内轮廓顶点）
            inner_z = None
            for z in sorted(bottom_region_zls):
                if z > max_z + 0.3 and 60 <= len(z_layers[z]) <= 150:
                    inner_z = z
                    break

            if inner_z is not None:
                inner_coords = [(v.co.x, v.co.y) for v in z_layers[inner_z]]
                inner_xs = [x for x, y in inner_coords]
                inner_ys = [y for x, y in inner_coords]
                inner_w = max(inner_xs) - min(inner_xs)
                inner_d = max(inner_ys) - min(inner_ys)
                wall_w = (width - inner_w) / 2.0
                wall_d = (depth - inner_d) / 2.0
                wall_thickness = (wall_w + wall_d) / 2.0
                log_to_file(f"[STEP Exporter] Wall thickness: {wall_thickness:.2f}mm (inner contour at z={inner_z:.2f}: {inner_w:.1f}x{inner_d:.1f}, {len(z_layers[inner_z])}v)")
            else:
                log_to_file(f"[STEP Exporter] Wall thickness: {wall_thickness:.2f}mm (default, no suitable inner Z layer)")
                for z in sorted(bottom_region_zls):
                    log_to_file(f"[STEP Exporter]   z={z:.2f} n={len(z_layers[z])} v")
        else:
            log_to_file(f"[STEP Exporter] Wall thickness: {wall_thickness:.2f} (default, insufficient Z levels)")
    wall_thickness = max(1.0, min(10.0, wall_thickness))

    # === 台阶环检测 ===
    # 优先从自定义属性读取（由 create_filleted_top_shell 设置）
    step_ring_height = 0.0
    step_ring_width = 0.0
    custom_ring_h = obj.get('step_ring_height', 0.0)
    custom_ring_w = obj.get('step_ring_width', 0.0)
    if custom_ring_h > 0 and custom_ring_w > 0:
        step_ring_height = custom_ring_h
        step_ring_width = custom_ring_w
        log_to_file(f"[STEP Exporter] Step ring from custom property: height={step_ring_height:.1f}mm, width={step_ring_width:.1f}mm")
    elif len(bottom_region_zls) >= 2:
        # 角度扇区分析，P40-P90百份位避开圆角顶点
        z0 = bottom_region_zls[0]
        z1 = None
        for z in sorted(bottom_region_zls)[1:]:
            if z - z0 >= 0.3 and len(z_layers[z]) >= 40:
                z1 = z
                break

        if z1 is not None and len(z_layers[z0]) >= 80:
            z0_coords = [(v.co.x, v.co.y) for v in z_layers[z0]]
            num_sectors = 64
            sector_angle_step = 2.0 * math.pi / num_sectors
            sector_dists = [[] for _ in range(num_sectors)]

            for x, y in z0_coords:
                dx = x - cx
                dy = y - cy
                dist = math.sqrt(dx * dx + dy * dy)
                angle = math.atan2(dy, dx)
                if angle < 0:
                    angle += 2.0 * math.pi
                sector_idx = int(angle / sector_angle_step) % num_sectors
                sector_dists[sector_idx].append(dist)

            sector_gaps = []
            for s_dists in sector_dists:
                if len(s_dists) < 3:
                    continue
                s_dists.sort()
                n_s = len(s_dists)
                # P40: 跳过圆角顶点，取台阶环内轮廓位置
                inner_idx = max(0, int(n_s * 0.40))
                # P90: 取外轮廓位置
                outer_idx = min(n_s - 1, int(n_s * 0.90))
                if inner_idx >= outer_idx:
                    continue
                inner_val = s_dists[inner_idx]
                outer_val = s_dists[outer_idx]
                if outer_val > inner_val + 0.2:
                    sector_gaps.append(outer_val - inner_val)

            if len(sector_gaps) >= num_sectors // 4:
                sector_gaps.sort()
                trim_n = max(1, len(sector_gaps) // 4)
                if len(sector_gaps) > trim_n * 2:
                    trimmed = sector_gaps[trim_n:-trim_n]
                else:
                    trimmed = sector_gaps
                avg_gap = sum(trimmed) / len(trimmed)

                log_to_file(f"[STEP Exporter] Step ring check z0={z0:.2f} n={len(z_layers[z0])} sectors={len(sector_gaps)} avg_gap={avg_gap:.2f} wall_thickness={wall_thickness:.2f}")

                if 0.3 <= avg_gap <= wall_thickness * 0.8:
                    step_ring_width = round(avg_gap, 1)
                    step_ring_height = round(z1 - z0, 1)
                    log_to_file(f"[STEP Exporter] Step ring detected: height={step_ring_height:.1f}mm, width={step_ring_width:.1f}mm (angular-sector P40-P90 gap={avg_gap:.1f})")

    log_to_file(f"[STEP Exporter] Step ring: height={step_ring_height:.1f}mm, width={step_ring_width:.1f}mm")
    
    # === 角圆角分析 ===
    # 用底部顶点包围盒
    corner_radius = 0.0
    corner_verts = [(x, y) for x, y, z in bottom_coords
                    if abs(x - cx) > half_w * 0.6 and abs(y - cy) > half_d * 0.6]
    if corner_verts:
        radii = []
        for vx, vy in corner_verts:
            dx = half_w - abs(vx - cx)
            dy = half_d - abs(vy - cy)
            if dx > 0 and dy > 0:
                r = dx + dy + math.sqrt(2 * dx * dy)
                radii.append(r)
        if radii:
            radii.sort()
            corner_radius = radii[len(radii) // 2]
    if corner_radius < 1.0:
        corner_radius = min(width, depth) * 0.1
    log_to_file(f"[STEP Exporter] Corner radius: {corner_radius:.2f}")
    
    # === 圆角半径分析 ===
    # 底部圆角：找底部Z层群，测Z差值
    outer_fillet_radius = 0.0
    bottom_z_layer_verts = []
    for z_level in sorted_z_levels:
        if z_level < bottom_z + 3.0:
            bottom_z_layer_verts.extend([(v.co.x, v.co.y, v.co.z) for v in z_layers[z_level]])
    
    if bottom_z_layer_verts:
        bottom_z_vals = [z for x, y, z in bottom_z_layer_verts]
        if max(bottom_z_vals) > bottom_z + 0.5:
            outer_fillet_radius = max(bottom_z_vals) - bottom_z
    outer_fillet_radius = max(0.0, min(outer_fillet_radius, outer_height * 0.2))
    inner_fillet_radius = max(0.1, min(outer_fillet_radius * 0.6, 3.0))  # 内圆角基于外圆角估算
    
    # === 顶部窗口检测 ===
    window_len = 0.0
    window_wid = 0.0
    window_data = obj.get('window_data', '')
    if window_data:
        log_to_file(f"[STEP Exporter] Window data from custom property: {window_data}")
    # === 读取通孔圆倒角半径（可在Blender中修改） ===
    hole_fillet_radius = obj.get('hole_fillet_radius', 0.0)
    if hole_fillet_radius > 0.0 and window_data:
        # 将 fillet_radius 注入到 window_data 的圆孔条目中
        entries = window_data.split(';')
        modified = False
        for i, entry in enumerate(entries):
            parts = entry.split(',')
            # 圆孔格式: cx,cy,cz,radius,1 或 cx,cy,cz,radius,1,fillet_radius
            if len(parts) >= 5 and parts[4].strip() == '1':
                if len(parts) == 5:
                    # 没有 fillet_radius，追加
                    entries[i] = entry + f",{hole_fillet_radius:.3f}"
                    modified = True
                elif len(parts) == 6:
                    # 已有 fillet_radius，更新
                    entries[i] = ','.join(parts[:5]) + f",{hole_fillet_radius:.3f}"
                    modified = True
        if modified:
            window_data = ';'.join(entries)
            log_to_file(f"[STEP Exporter]   Updated hole fillet radius: {hole_fillet_radius:.3f}")
    if not window_data and top_coords and len(top_coords) > 30:
        top_z_layer_coords = [(v.co.x, v.co.y) for v in top_verts]
        top_dists = [math.sqrt((x - cx)**2 + (y - cy)**2) for x, y in top_z_layer_coords]
        if top_dists:
            max_top_dist = max(top_dists)
            inner_top = [(x, y) for (x, y), d in zip(top_z_layer_coords, top_dists) if d < max_top_dist * 0.7]
            if len(inner_top) >= 4:
                wx_vals = [x for x, y in inner_top]
                wy_vals = [y for x, y in inner_top]
                window_len = max(wx_vals) - min(wx_vals)
                window_wid = max(wy_vals) - min(wy_vals)
                log_to_file(f"[STEP Exporter] Window detected: {window_len:.1f}x{window_wid:.1f}")
    
    # 释放BMesh
    bm.free()
    
    log_to_file(f"[STEP Exporter] Detected TOP shell: {width:.4f}x{depth:.4f} h={outer_height:.4f} tt={top_thickness:.1f} wt={wall_thickness:.1f} cr={corner_radius:.1f} recess={top_recess:.1f} yOff={top_offset_y:.1f} ofr={outer_fillet_radius:.1f} ifr={inner_fillet_radius:.1f} win={window_len:.1f}x{window_wid:.1f} step_ring={step_ring_height:.1f}x{step_ring_width:.1f}")
    
    return {
        'obj': obj,
        'width': width,
        'depth': depth,
        'outer_height': outer_height,
        'top_thickness': top_thickness,
        'wall_thickness': wall_thickness,
        'corner_radius': corner_radius,
        'outer_fillet_radius': outer_fillet_radius,
        'inner_fillet_radius': inner_fillet_radius,
        'top_recess': top_recess,
        'top_offset_y': top_offset_y,
        'window_len': window_len,
        'window_wid': window_wid,
        'window_data': window_data,
        'step_ring_height': step_ring_height,
        'step_ring_width': step_ring_width,
        'pos_x': obj.location.x,
        'pos_y': obj.location.y,
        'pos_z': obj.location.z,
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
    
    # 区分顶壳/底壳：顶壳的封闭面在 max-Z（顶点少），开口在 min-Z（内外壁顶点多）
    # 底壳的封闭面在 min-Z，开口在 max-Z
    top_vcount = len(top_verts)
    bot_vcount = len(bottom_verts)
    vratio = top_vcount / max(bot_vcount, 1)
    log_to_file(f"[STEP Exporter] Vertex count: top={top_vcount}, bottom={bot_vcount}, ratio={vratio:.3f}")
    
    # 关键判断：如果底部顶点显著多于顶部（ratio < 0.7），说明开口在底部 → 顶壳
    if vratio < 0.70:
        log_to_file(f"[STEP Exporter] Bottom has significantly more vertices (ratio={vratio:.3f}) → TOP shell (opening at bottom), not bottom shell")
        bm.free()
        return None
    
    # 几何检查：顶壳锥形渐缩，顶面bbox显著小于底面bbox
    top_x_coords = [v.co.x for v in top_verts]
    top_y_coords = [v.co.y for v in top_verts]
    bottom_x_coords = [v.co.x for v in bottom_verts]
    bottom_y_coords = [v.co.y for v in bottom_verts]
    top_w = max(top_x_coords) - min(top_x_coords)
    top_d = max(top_y_coords) - min(top_y_coords)
    bot_w = max(bottom_x_coords) - min(bottom_x_coords)
    bot_d = max(bottom_y_coords) - min(bottom_y_coords)
    area_ratio = (top_w * top_d) / max(bot_w * bot_d, 0.01)
    log_to_file(f"[STEP Exporter] Top bbox: {top_w:.1f}x{top_d:.1f}, Bottom bbox: {bot_w:.1f}x{bot_d:.1f}, area_ratio={area_ratio:.3f}")
    
    if area_ratio < 0.80:
        log_to_file(f"[STEP Exporter] Top face area is {area_ratio:.3f}x bottom → TOP shell (tapered), not bottom shell")
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
    
    # 内圆角基于外圆角估算（底壳内外圆角比例约1:2）
    # 另可从 Z-layer gap 检测内壁起始位置推算（见 create_bottom_shell.py 的 measure 逻辑）
    inner_fillet_radius = max(0.1, min(outer_fillet_radius * 0.5, 3.0))
    
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
        z_key = round(z / 0.0001) * 0.0001
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
    
    # 修复：当顶部有孔洞（如标准圆柱顶部打孔）时，has_two_clusters可能因
    # 三角面片中间顶点过多而无法检测到两簇。此时用简单阈值法提取外圈半径。
    if not top_is_hollow and not might_be_hollow:
        top_min_r = top_radii_sorted[0]
        top_max_r = top_radii_sorted[-1]
        if top_max_r - top_min_r > top_max_r * 0.15 and top_min_r > top_max_r * 0.1:
            mid_r = (top_min_r + top_max_r) / 2.0
            top_outer = [r for r in top_radii_sorted if r > mid_r]
            if len(top_outer) >= 4:
                top_is_hollow = True
                might_be_hollow = True
                top_outer_radii = sorted(top_outer)
                log_to_file(f"[STEP Exporter] Detected ring at top via threshold: outer_r={top_outer_radii[len(top_outer_radii)//2]:.3f}")
    
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
    
    # 修复：底部有圆倒角/孔洞时，底部Z层混合了倒角+孔洞+外壁顶点导致半径方差高。
    # 此时顶部通常是干净的单层圆。若顶部方差低，用顶部半径作为圆柱体半径。
    # 不能简单向上扫描找"干净层"——靠近底部的干净层可能是内孔壁（半径偏小），
    # 会被误判为锥体底部。
    if std_b > bottom_radius * 0.15 and std_t <= top_radius * 0.15:
        # 顶部干净，底部混乱 → 恒定半径圆柱，用顶部数据替代底部
        bottom_radius = top_radius
        bottom_outer_radii = top_outer_radii if might_be_hollow else top_radii
        std_b = std_t
        # 标记为可能空心：后续中间层检测需要提取外圈簇，避免内孔壁污染半径范围检查
        if not might_be_hollow:
            might_be_hollow = True
        log_to_file(f"[STEP Exporter] Bottom variance high (std_b={std_b:.4f}), top is clean (r={top_radius:.4f}), using top radius for cylinder body")
    
    # 标准差不大于平均半径的 15% 才认为是规则圆柱
    if std_b > bottom_radius * 0.15 or std_t > top_radius * 0.15:
        log_to_file(f"[STEP Exporter] Radius variance too high: std_b={std_b:.3f} std_t={std_t:.3f}")
        bm.free()
        return None
    
    # 半径不能太小
    if bottom_radius < 0.001 or top_radius < 0.001:
        log_to_file(f"[STEP Exporter] Radius too small: b={bottom_radius:.3f} t={top_radius:.3f}")
        bm.free()
        return None
    
    # 高度不能太小
    if height < 0.0005:
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

    mid_all_radii = []
    for zl_key in z_layers:
        if z_mid_low <= zl_key <= z_mid_high and len(z_layers[zl_key]) >= 1:
            mid_all_radii.extend(compute_radii(z_layers[zl_key]))
    
    if len(mid_all_radii) >= 16:
        mid_sorted = sorted(mid_all_radii)
        # 检测中间区域是否有内外两簇（如双端盲孔圆柱的外壁+内孔壁）
        mid_is_cluster, mid_outer_radii = has_two_clusters(mid_sorted)
        if mid_is_cluster and len(mid_outer_radii) >= 8:
            # 使用外簇（更大半径的那簇）进行圆度检测
            mid_sorted = mid_outer_radii
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
    z_max_radius = {}  # 每层最大半径（用于检测外壁是否存在）
    for zl in sorted_z:
        r = _layer_outer_radius(z_layers[zl])
        if r is not None:
            z_radius_data[zl] = r
        # 计算该层最大半径
        all_r = compute_radii(z_layers[zl])
        if len(all_r) > 0:
            z_max_radius[zl] = max(all_r)
    
    # DEBUG: 输出 z-level 和半径数据
    log_to_file(f"[STEP Exporter]   detect: {len(sorted_z)} z-levels, {len(z_radius_data)} with radius data")
    for zl in sorted_z:
        r = z_radius_data.get(zl)
        max_r = z_max_radius.get(zl, 0)
        if r is not None:
            log_to_file(f"[STEP Exporter]     z={zl:.6f} r={r:.6f} max_r={max_r:.6f}")
    log_to_file(f"[STEP Exporter]   detect: bottom_r={bottom_radius:.6f} top_r={top_radius:.6f} height={height:.6f}")
    
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
    
    # 修复：圆柱顶部打孔时，孔洞表面顶点半径远小于本体半径，
    # 导致cylindrical_body=False（"本体"区域只有底部1层）。
    # 检测这种模式：底部半径大、上方第一层半径骤降>40% → 圆柱带孔洞，非锥体/倒角
    hole_pattern_detected = False
    hole_position = 'top'  # 默认顶部盲孔，底部盲孔时检测为 'bottom'
    hole_radius = 0.0
    hole_depth = 0.0
    hole_depth_top = 0.0  # 双端孔时顶部孔深
    
    # 强制圆柱体判断：两端半径接近且顶部干净时，即使中间z层缺少外壁顶点
    # （如盲孔圆柱的外壁仅有顶部/底部顶点），也认定为恒定半径圆柱。
    # 同时检测底部盲孔：底部顶点数>>顶部顶点数 → 孔在底部。
    if not cylindrical_body and abs(bottom_radius - top_radius) / max(bottom_radius, 0.01) < 0.02 and std_t <= top_radius * 0.05:
        cylindrical_body = True
        body_radius = (bottom_radius + top_radius) / 2.0
        body_end_z = sorted_z[-1]
        log_to_file(f"[STEP Exporter]   Forced cylindrical body: ends same radius (b={bottom_radius:.3f} t={top_radius:.3f}), top clean")
        
        # 底部盲孔检测：强制圆柱体意味着底部有孔洞特征
        b_radii = sorted(compute_radii(z_layers[sorted_z[0]]))
        inner_n = max(4, len(b_radii) // 8)
        inner_r = sorted(b_radii[:inner_n])[inner_n//2]
        
        # 从底部向上扫描找内孔结束位置（用max半径判断外壁是否存在）
        hole_end_bottom = sorted_z[0]
        for zl in sorted_z[1:]:
            r = z_radius_data.get(zl)
            max_r = z_max_radius.get(zl, 0)
            # 内孔z层：外半径小 且 没有外壁顶点
            if r is not None and r < body_radius * 0.7 and max_r < body_radius * 0.85:
                hole_end_bottom = zl
        
        # 从顶部向下扫描找内孔开始位置
        hole_start_top = sorted_z[-1]
        for zl in reversed(sorted_z[:-1]):
            r = z_radius_data.get(zl)
            max_r = z_max_radius.get(zl, 0)
            if r is not None and r < body_radius * 0.7 and max_r < body_radius * 0.85:
                hole_start_top = zl
        
        bottom_hole_d = hole_end_bottom - sorted_z[0]
        top_hole_d = sorted_z[-1] - hole_start_top
        
        # 判断两端是否有孔
        btm_has_hole = inner_r > 0.0005 and bottom_hole_d > height * 0.05
        top_has_hole = inner_r > 0.0005 and top_hole_d > height * 0.05
        
        if btm_has_hole and top_has_hole:
            # 两端都有孔：可能重叠（贯通/相交）也可能不重叠（中间有实体段）
            if hole_end_bottom >= hole_start_top:
                # 孔范围交叉/重叠：用max半径重新扫描找实际孔底
                btm_end = sorted_z[0]
                for zl in sorted_z[1:]:
                    r = z_radius_data.get(zl)
                    max_r = z_max_radius.get(zl, 0)
                    if r is not None and r < body_radius * 0.7 and max_r < body_radius * 0.85:
                        btm_end = zl
                    else:
                        break
                top_start = sorted_z[-1]
                for zl in reversed(sorted_z[:-1]):
                    r = z_radius_data.get(zl)
                    max_r = z_max_radius.get(zl, 0)
                    if r is not None and r < body_radius * 0.7 and max_r < body_radius * 0.85:
                        top_start = zl
                    else:
                        break
                # 如果扫描到对端（无外壁z层），用max半径找外壁首现位置作为分界
                if btm_end >= sorted_z[-1] * 0.99 or top_start <= sorted_z[0] * 1.01:
                    # 找中间区域第一个有外壁的z层
                    mid_z = (sorted_z[0] + sorted_z[-1]) / 2
                    outer_zls = [zl for zl in sorted_z[1:-1]
                                 if z_max_radius.get(zl, 0) > body_radius * 0.85]
                    if outer_zls:
                        # 用最靠近中点的外壁z层作为分界
                        boundary_z = min(outer_zls, key=lambda zl: abs(zl - mid_z))
                        btm_end = boundary_z
                        top_start = boundary_z
                        log_to_file(f"[STEP Exporter]   Both scans reached opposite ends, using max-radius boundary z={boundary_z:.4f}")
                    else:
                        # 完全没有外壁z层：回退到中点
                        btm_end = mid_z
                        top_start = mid_z
                        log_to_file(f"[STEP Exporter]   No outer-wall z-levels found, using midpoint z={mid_z:.4f}")
                bottom_hole_d = btm_end - sorted_z[0]
                top_hole_d = sorted_z[-1] - top_start
            # else: 不重叠，bottom_hole_d 和 top_hole_d 已在上方扫描中获得
            
            if bottom_hole_d > height * 0.05 and top_hole_d > height * 0.05:
                hole_pattern_detected = True
                hole_position = 'both'
                hole_radius = inner_r
                # 优先使用对象上存储的精确孔深（避免 mesh z-level 分析误差）
                stored_depth = obj.get('hole_depth') if hasattr(obj, 'get') else None
                stored_pos = obj.get('hole_position') if hasattr(obj, 'get') else None
                if stored_depth is not None and stored_pos == 'both':
                    hole_depth = stored_depth
                    hole_depth_top = stored_depth
                    log_to_file(f"[STEP Exporter]   Using stored hole_depth={stored_depth:.4f} from object property")
                else:
                    hole_depth = bottom_hole_d
                    hole_depth_top = top_hole_d
                log_to_file(f"[STEP Exporter]   Dual blind holes: inner_r={inner_r:.4f} btm_d={hole_depth:.4f} ({hole_depth/height*100:.0f}%) top_d={hole_depth_top:.4f} ({hole_depth_top/height*100:.0f}%)")
            else:
                log_to_file(f"[STEP Exporter]   Hole spans cylinder but depths too small — exporting as solid cylinder")
        elif btm_has_hole:
            hole_pattern_detected = True
            hole_position = 'bottom'
            hole_radius = inner_r
            hole_depth = bottom_hole_d
            log_to_file(f"[STEP Exporter]   Bottom blind hole: inner_r={inner_r:.4f} hole_depth={bottom_hole_d:.4f} ({bottom_hole_d/height*100:.0f}%)")
        elif top_has_hole:
            hole_pattern_detected = True
            hole_position = 'top'
            hole_radius = inner_r
            hole_depth = top_hole_d
            log_to_file(f"[STEP Exporter]   Top blind hole: inner_r={inner_r:.4f} hole_depth={top_hole_d:.4f} ({top_hole_d/height*100:.0f}%)")
        else:
            log_to_file(f"[STEP Exporter]   Blind hole check: inner_r={inner_r:.6f} btm_d={bottom_hole_d:.6f} top_d={top_hole_d:.6f} — not detected")
    
    if not cylindrical_body and bottom_radius > 0.01:
        above_zls = [zl for zl in sorted_z if zl > body_end_z and zl in z_radius_data]
        if above_zls:
            above_r_first = z_radius_data[above_zls[0]]
            if above_r_first < bottom_radius * 0.6:
                log_to_file(f"[STEP Exporter]   Hole pattern detected: bottom_r={bottom_radius:.3f} above_r={above_r_first:.3f}, treating as cylinder")
                cylindrical_body = True
                body_radius = bottom_radius
                top_radius = bottom_radius  # 防止后续检测为锥体
                hole_pattern_detected = True
    
    # 底部盲孔检测：顶部恒定半径为本体，底部参数骤降为孔洞
    if not hole_pattern_detected and cylindrical_body and top_radius > 0.01:
        below_zls_bottom = [zl for zl in sorted_z if zl < body_end_z and zl in z_radius_data]
        if below_zls_bottom:
            below_r_first = z_radius_data[below_zls_bottom[0]]  # 紧邻本体的孔洞层
            if below_r_first < body_radius * 0.6:
                log_to_file(f"[STEP Exporter]   Bottom hole pattern detected: body_r={body_radius:.3f} below_r={below_r_first:.3f}")
                hole_pattern_detected = True
                hole_position = 'bottom'
    
    # 底部盲孔检测（顶点数比值法）：当底部顶点数远多于顶部（>3x），
    # 且顶部是干净的单层圆时，孔洞在底部。适用于外壁无中间层顶点的情况。
    # 不依赖 has_two_clusters（圆倒角导致底部层难以聚类）。
    if not hole_pattern_detected and cylindrical_body:
        bot_vcount = len(z_layers[sorted_z[0]])
        top_vcount = len(z_layers[sorted_z[-1]])
        if bot_vcount > top_vcount * 3:
            # 孔在底部：从底部层半径分布中找最小半径簇作为内孔半径
            b_radii = sorted(compute_radii(z_layers[sorted_z[0]]))
            # 取底部最小的10%顶点半径的中位数（排除外壁和倒角顶点）
            inner_count = max(4, len(b_radii) // 10)
            inner_r = sorted(b_radii[:inner_count])[inner_count//2]
            
            # 孔深：找底部以上顶点数最多的Z层（通常是孔底平面），
            # 孔底以上顶点数应骤降（内孔壁结束，仅剩外壁）
            best_z = sorted_z[0]
            best_vc = 0
            for zl in sorted_z[1:-1]:  # 跳过底部和顶部
                vc = len(z_layers[zl])
                if vc > best_vc:
                    best_vc = vc
                    best_z = zl
            # 孔底以上第一层顶点数应显著下降
            if best_vc > top_vcount * 2:
                hole_end_z = best_z
            else:
                hole_end_z = sorted_z[0]  # 无法确定，保守使用底部
            
            hole_depth = hole_end_z - sorted_z[0]
            if inner_r > 0.001 and hole_depth > height * 0.1:
                hole_radius = inner_r
                hole_pattern_detected = True
                hole_position = 'bottom'
                log_to_file(f"[STEP Exporter]   Bottom blind hole via vcount ratio: bot_v={bot_vcount} top_v={top_vcount} inner_r={inner_r:.4f} hole_depth={hole_depth:.4f} ({hole_depth/height*100:.0f}%) best_z={best_z:.4f} best_vc={best_vc}")
    
    # 底部盲孔检测（空心簇法）：底部有两簇（外壁+内孔），但顶部无两簇（实心顶）
    if not hole_pattern_detected and cylindrical_body and bottom_is_hollow and not top_is_hollow:
        # 确认中间层也有两簇（内孔壁存在），顶部层无两簇（内孔未贯穿）
        mid_has_hole = False
        for zl in sorted_z[1:-1]:  # 检查中间层（排除底部和顶部）
            if len(z_layers[zl]) >= 16:
                mid_radii = sorted(compute_radii(z_layers[zl]))
                mid_cluster, _ = has_two_clusters(mid_radii)
                if mid_cluster:
                    mid_has_hole = True
                    break
        if mid_has_hole:
            # 计算孔洞深度：从底部向上找到内孔消失的Z层
            # hole_end_z = 最后一个有两簇的Z层（内孔壁终点）
            hole_end_z = sorted_z[0]  # 默认仅在底部
            for zl in sorted_z[1:]:
                if len(z_layers[zl]) >= 16:
                    zl_radii = sorted(compute_radii(z_layers[zl]))
                    zl_cluster, _ = has_two_clusters(zl_radii)
                    if zl_cluster:
                        hole_end_z = zl  # 更新为最后一个有两簇的层
                    else:
                        break  # 内孔在此层之上消失
            # 获取孔半径：从底部层内部簇中提取
            inner_b, _ = layer_inner_outer_radii(sorted_z[0]) if 'layer_inner_outer_radii' in dir() else (0, 0)
            if inner_b == 0:
                # inline compute
                b_radii = sorted(compute_radii(z_layers[sorted_z[0]]))
                b_cluster, b_outer = has_two_clusters(b_radii)
                if b_cluster:
                    n_b = len(b_radii)
                    b_inner = b_radii[:n_b - len(b_outer)]
                    inner_b = sorted(b_inner)[len(b_inner)//2] if b_inner else 0
            
            hole_depth = hole_end_z - sorted_z[0]
            if inner_b > 0.001 and hole_depth > height * 0.15:
                hole_radius = inner_b
                hole_pattern_detected = True
                hole_position = 'bottom'
                log_to_file(f"[STEP Exporter]   Bottom blind hole detected via cluster: inner_r={inner_b:.4f} hole_depth={hole_depth:.4f} ({hole_depth/height*100:.0f}%)")
    
    if cylindrical_body:
        body_radius = sorted([z_radius_data.get(zl, body_radius) for zl in sorted_z 
                               if abs(z_radius_data.get(zl, body_radius) - body_radius) / max(body_radius, 0.01) < 0.01
                               and zl in z_radius_data]) or [body_radius]
        body_radius = body_radius[len(body_radius)//2] if isinstance(body_radius, list) else body_radius
        
        # 顶部过渡：body_end_z 以上的所有层
        top_transition_zls = [zl for zl in sorted_z if zl > body_end_z and zl in z_radius_data]
        
        # 孔洞模式：孔洞表面的顶点不应被检测为倒角/圆角过渡
        if hole_pattern_detected:
            top_transition_zls = []
        
        # 如果过渡层不足2层但顶部半径明显偏离，添加上一个本体层作为过渡起点
        if len(top_transition_zls) < 2 and not hole_pattern_detected:
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
        top_transition_zls = []
        bottom_transition_zls = []
        
        # === 稀疏层级的倒角/圆角快速检测（3层模式） ===
        valid_zls = [zl for zl in sorted_z if zl in z_radius_data]
        if len(valid_zls) == 3:
            r0 = z_radius_data[valid_zls[0]]
            r1 = z_radius_data[valid_zls[1]]
            r2 = z_radius_data[valid_zls[2]]
            ratio_01 = abs(r0 - r1) / max(abs(r0), 0.001)
            ratio_12 = abs(r1 - r2) / max(abs(r1), 0.001)
            if ratio_01 > 0.01 and ratio_12 < 0.01:
                # r0 != r1 == r2 → 顶部倒角，r0 是完整半径（圆柱体）
                body_radius = r0
                bottom_radius = r0
                top_radius = r0  # 让后续比例检查通过，确保返回 cylinder 而非 cone
                top_feature = 'chamfer'
                top_feature_size = r0 - r2
                top_transition_zls = [valid_zls[0], valid_zls[1]]
                cylindrical_body = True
                body_end_z = valid_zls[2]
            elif ratio_01 < 0.01 and ratio_12 > 0.01:
                # r0 == r1 != r2 → 底部倒角（圆柱体）
                body_radius = r0
                bottom_radius = r0
                top_radius = r0
                bottom_feature = 'chamfer'
                bottom_feature_size = r0 - r2
                bottom_transition_zls = [valid_zls[1], valid_zls[2]]
                cylindrical_body = True
                body_end_z = valid_zls[0]
            elif ratio_01 > 0.01 and ratio_12 > 0.01:
                # 两端都有半径变化 → 可能是锥体+倒角
                # 需要通过 z 间距判断倒角在顶部还是底部
                # 倒角过渡区较短，锥体本体较长
                gap_bottom = valid_zls[1] - valid_zls[0]  # 底部过渡区高度
                gap_top = valid_zls[2] - valid_zls[1]      # 顶部过渡区高度
                if gap_bottom < gap_top * 0.5:
                    # 底部过渡区很短 → 底部倒角 on 锥体
                    # r0: chamfer后的底面半径, r1: 锥体底部全半径, r2: 锥体顶部半径
                    body_radius = r1
                    bottom_feature = 'chamfer'
                    bottom_feature_size = r1 - r0
                    bottom_transition_zls = [valid_zls[0], valid_zls[1]]
                    log_to_file(f"[STEP Exporter]   detect: 3-layer cone with bottom chamfer (r0={r0:.4f}<r1={r1:.4f}>r2={r2:.4f}, gap_bot={gap_bottom:.4f}<gap_top={gap_top:.4f})")
                elif gap_top < gap_bottom * 0.5:
                    # 顶部过渡区很短 → 顶部倒角 on 锥体（锥体上宽下窄）
                    # r0: 锥体底部半径, r1: 锥体顶部全半径, r2: chamfer后的顶面半径
                    body_radius = r1
                    top_feature = 'chamfer'
                    top_feature_size = r1 - r2
                    top_transition_zls = [valid_zls[1], valid_zls[2]]
                    log_to_file(f"[STEP Exporter]   detect: 3-layer cone with top chamfer (r0={r0:.4f}<r1={r1:.4f}>r2={r2:.4f}, gap_top={gap_top:.4f}<gap_bot={gap_bottom:.4f})")
                elif r0 < r1:
                    # 无法通过间距判断，退化为按半径关系判断：r0<r1 → 底部倒角
                    body_radius = r1
                    bottom_feature = 'chamfer'
                    bottom_feature_size = r1 - r0
                    bottom_transition_zls = [valid_zls[0], valid_zls[1]]
                    log_to_file(f"[STEP Exporter]   detect: 3-layer cone with bottom chamfer (fallback, r0={r0:.4f}<r1={r1:.4f})")
                elif r0 > r1:
                    # r0 > r1 > r2 → 顶部倒角 on 锥体
                    body_radius = r1
                    top_feature = 'chamfer'
                    top_feature_size = r1 - r2
                    top_transition_zls = [valid_zls[1], valid_zls[2]]
                    log_to_file(f"[STEP Exporter]   detect: 3-layer cone with top chamfer (r0={r0:.4f}>r1={r1:.4f}>r2={r2:.4f})")
        
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
                    
                    deviation_thresh = max(abs(a) * height * 0.02 + 0.1, 0.15)
                    
                    # 底部过渡检测：只收集偏离拟合线的层级
                    deviating_bot = []
                    for zl in bot_zls:
                        expected_r = a * zl + b
                        actual_r = z_radius_data[zl]
                        if abs(actual_r - expected_r) > deviation_thresh:
                            deviating_bot.append(zl)
                    
                    if deviating_bot:
                        bottom_transition_zls = deviating_bot
                    elif len(bot_zls) >= 2:
                        bot_slope = (z_radius_data[bot_zls[-1]] - z_radius_data[bot_zls[0]]) / (bot_zls[-1] - bot_zls[0])
                        if abs(bot_slope - a) > max(abs(a) * 0.3, 0.05):
                            bottom_transition_zls = bot_zls
                    
                    # 顶部过渡检测：只收集偏离拟合线的层级
                    deviating_top = []
                    for zl in top_zls:
                        expected_r = a * zl + b
                        actual_r = z_radius_data[zl]
                        if abs(actual_r - expected_r) > deviation_thresh:
                            deviating_top.append(zl)
                    
                    if deviating_top:
                        top_transition_zls = deviating_top
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
                    deviation_thresh = max(abs(a) * height * 0.02 + 0.1, 0.15)
                    
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
    
    # === 倒角+圆角组合检测：圆柱本体无中间顶点时的回退 ===
    # 当圆柱本体无内部顶点，两端过渡区都只有少量层级时，
    # 顶部2+层同半径→倒角，底部2+层渐变半径→圆角
    if not cylindrical_body and not top_transition_zls and not bottom_transition_zls:
        valid_zls_mod = [zl for zl in sorted_z if zl in z_radius_data]
        if len(valid_zls_mod) >= 4:
            # 底部检测：检查底部半径是否单调递减/递增（圆角特征）
            # 取前5层检查趋势，然后扩展整个过渡区
            probe_count = min(5, len(valid_zls_mod) // 2)
            if probe_count >= 3:
                bot_radii_probe = [z_radius_data[valid_zls_mod[i]] for i in range(probe_count)]
                dr_total = bot_radii_probe[-1] - bot_radii_probe[0]
                if abs(dr_total) > 0.00005:
                    # 单调性检查
                    monotonically = True
                    direction = 1 if dr_total > 0 else -1
                    for i in range(1, probe_count):
                        if (bot_radii_probe[i] - bot_radii_probe[i-1]) * direction < 0:
                            monotonically = False
                            break
                    if monotonically:
                        # 扩展到所有跟随同一趋势的层（不跨越 >1mm 的空隙）
                        bottom_transition_zls = []
                        for i in range(len(valid_zls_mod)):
                            if i == 0:
                                bottom_transition_zls.append(valid_zls_mod[i])
                                continue
                            # 空隙检查：相邻层 z 差 > 0.001（1mm）说明离开了过渡区
                            z_gap = valid_zls_mod[i] - valid_zls_mod[i-1]
                            if z_gap > 0.001:
                                break
                            d = z_radius_data[valid_zls_mod[i]] - z_radius_data[valid_zls_mod[i-1]]
                            if abs(d) < 0.000005:
                                break  # 半径变化太小，停止扩展
                            if d * direction < 0:
                                break  # 方向反转，停止扩展
                            bottom_transition_zls.append(valid_zls_mod[i])
                        
                        if len(bottom_transition_zls) >= 3:
                            # 过渡区跨度检查：不超过总高度的30%（排除锥体误判）
                            total_height_mod = sorted_z[-1] - sorted_z[0]
                            transition_span = bottom_transition_zls[-1] - bottom_transition_zls[0]
                            if total_height_mod > 0 and transition_span / total_height_mod > 0.3:
                                bottom_transition_zls = []  # 跨度太大，不是过渡特征
                            else:
                                bottom_feature = 'fillet'
                                bottom_zs = transition_span
                                bottom_dr = abs(z_radius_data[bottom_transition_zls[-1]] - z_radius_data[bottom_transition_zls[0]])
                                bottom_feature_size = max(bottom_zs, bottom_dr)
                                body_radius = z_radius_data[bottom_transition_zls[0]]
                                bottom_radius = body_radius
                                top_radius = body_radius
                                cylindrical_body = True
            
            # 顶部检测：检查最高2层是否半径相同（倒角特征）
            if len(valid_zls_mod) >= 4:
                top_zls_mod = valid_zls_mod[-2:]  # 取顶部2层
                if len(top_zls_mod) >= 2:
                    top_radii = [z_radius_data[zl] for zl in top_zls_mod]
                    if abs(top_radii[-1] - top_radii[-2]) / max(abs(top_radii[-1]), 0.001) < 0.01:
                        # 顶部两层半径相同 → 倒角
                        if not body_radius:
                            # 从第三层推断体半径
                            if len(valid_zls_mod) >= 3:
                                body_radius = z_radius_data[valid_zls_mod[-3]]
                            else:
                                body_radius = top_radii[-1]
                            bottom_radius = body_radius
                            top_radius = body_radius
                        top_feature = 'chamfer'
                        top_feature_size = body_radius - top_radii[-1] if body_radius > top_radii[-1] else 0
                        top_transition_zls = top_zls_mod
                        cylindrical_body = True
    
    # 2. 分析过渡区类型
    def _classify_transition(transition_zls):
        if len(transition_zls) < 2:
            return None, 0.0
        _radii = [(zl, z_radius_data[zl]) for zl in transition_zls if z_radius_data.get(zl) is not None]
        if len(_radii) < 2:
            return None, 0.0
        
        dr = _radii[-1][1] - _radii[0][1]
        threshold = max(body_radius * 0.01, 0.0001)
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
        
        if len(slopes) >= 2:
            accels = [slopes[j] - slopes[j-1] for j in range(1, len(slopes))]
            avg_accel = sum(abs(a) for a in accels) / len(accels)
            if avg_accel < max(avg_slope * 0.12, 0.02):
                feature_type = 'chamfer'
                feature_size = abs(dr)
            else:
                feature_type = 'fillet'
                # Fillet radius: Z-span captures the tangent-to-tangent range but may
                # underestimate when bottom portion deviates less than threshold.
                # Use max(Z-span, |dr|) as robust estimate (both should equal R for 90°
                # fillets on cylinders; on tapered cones they converge to same value).
                z_span = (transition_zls[-1] - transition_zls[0]) * 1.0
                feature_size = max(z_span, abs(dr))
        else:
            # 单斜率过渡 → 倒角（线性过渡），用 |dr| 作为倒角尺寸
            feature_type = 'chamfer'
            feature_size = abs(dr)
        
        return feature_type, feature_size
    
    # 扩展单层过渡：当过渡区只有1层时，加入相邻的本体端点层
    # 例如双倒角圆柱：sorted_z = [-0.02(chamfer rim), -0.017(chamfer face), 0.017(chamfer face), 0.02(chamfer rim)]
    # 过渡区只有 chamfer rim 一层，需要包含 chamfer face 才能正确分类
    if top_transition_zls and len(top_transition_zls) == 1:
        valid_zls = [zl for zl in sorted_z if zl in z_radius_data]
        idx = valid_zls.index(top_transition_zls[0])
        if idx > 0:
            top_transition_zls = [valid_zls[idx - 1], valid_zls[idx]]
    if bottom_transition_zls and len(bottom_transition_zls) == 1:
        valid_zls = [zl for zl in sorted_z if zl in z_radius_data]
        idx = valid_zls.index(bottom_transition_zls[0])
        if idx + 1 < len(valid_zls):
            bottom_transition_zls = [valid_zls[idx], valid_zls[idx + 1]]
    
    if top_transition_zls and not top_feature:
        top_feature, top_feature_size = _classify_transition(top_transition_zls)
    if bottom_transition_zls and not bottom_feature:
        bottom_feature, bottom_feature_size = _classify_transition(bottom_transition_zls)
    
    # 对于圆柱本体有过渡 → 修正 radius 为 body_radius
    if cylindrical_body and (top_feature or bottom_feature):
        # 单侧过渡：用无过渡侧的极端Z层半径作为本体半径
        # 避免 body_radius 因过渡区边界顶点混入导致轻微偏差
        if top_feature and not bottom_feature:
            body_radius = bottom_radius  # 底部是无过渡侧，用底部极端半径
        elif bottom_feature and not top_feature:
            body_radius = top_radius  # 顶部是无过渡侧，用顶部极端半径
        bottom_radius = body_radius
        top_radius = body_radius
    
    # 回退检测：锥体分析检测到两端过渡特征，但 cylindrical_body 仍为 False
    # 当两端过渡区边缘半径接近时（差距<5%），推断为圆柱本体（非锥体）
    if not cylindrical_body and top_feature and bottom_feature:
        if top_transition_zls and bottom_transition_zls:
            # 过渡区z层级为升序排列
            # 顶部过渡：升序，第一个是本体边界，最后一个是极端
            # 底部过渡：升序，第一个是极端，最后一个是本体边界
            top_body_r = z_radius_data.get(top_transition_zls[0], None)
            bot_body_r = z_radius_data.get(bottom_transition_zls[-1], None)
            if top_body_r is not None and bot_body_r is not None and top_body_r > 0.001:
                if abs(top_body_r - bot_body_r) / top_body_r < 0.05:
                    body_radius = (top_body_r + bot_body_r) / 2.0
                    bottom_radius = body_radius
                    top_radius = body_radius
                    cylindrical_body = True
                    log_to_file(f"[STEP Exporter] Recovered cylindrical body from transition edges: r={body_radius:.4f}")
    
    bm.free()
    
    # DEBUG: 输出特征检测结果
    log_to_file(f"[STEP Exporter]   detect: cylindrical_body={cylindrical_body} top_feature={top_feature} top_feature_size={top_feature_size:.4f} bottom_feature={bottom_feature} bottom_feature_size={bottom_feature_size:.4f}")
    log_to_file(f"[STEP Exporter]   detect: top_transition_zls={len(top_transition_zls)} bottom_transition_zls={len(bottom_transition_zls)}")
    
    pos_x = obj.location.x
    pos_y = obj.location.y
    pos_z = obj.location.z
    
    # 检测对象旋转：如果世界矩阵翻转了 Z 轴（绕 X 或 Y 旋转 180°），
    # 则交换 top_feature 和 bottom_feature（局部坐标中 chamfer 在顶部，
    # 但世界坐标中应该在底部），同时交换 top_radius/bottom_radius
    world_mat = obj.matrix_world
    if world_mat[2][2] < 0:
        if top_feature or bottom_feature:
            log_to_file(f"[STEP Exporter] Z-axis flipped by rotation, swapping top/bottom features")
            top_feature, bottom_feature = bottom_feature, top_feature
            top_feature_size, bottom_feature_size = bottom_feature_size, top_feature_size
        # 交换上下半径（对于锥体/空心锥体，上下半径不同，旋转180°后需要对应交换）
        if abs(bottom_radius - top_radius) > 0.0001:
            top_radius, bottom_radius = bottom_radius, top_radius
            if is_hollow:
                inner_radius, inner_top_radius = inner_top_radius, inner_radius
            log_to_file(f"[STEP Exporter] Z-axis flipped by rotation, swapping top/bottom radii")
    
    # ===== Mesh-based Stepped Hole Detection for Hollow Cones =====
    # Detects stepped inner holes: constant-radius straight section at top,
    # tapered section below. Signature: inner radius near-constant in top portion
    # while outer continues to taper, with a jump at the step transition.
    stepped_hole_params = {}
    if is_hollow and not (bottom_radius * 0.98 <= top_radius <= bottom_radius * 1.02):
        inner_z_data = {}
        for zl in sorted_z:
            pts = z_layers[zl]
            if len(pts) < 16:
                continue
            radii = sorted(compute_radii(pts))
            is_cluster, outer = has_two_clusters(radii)
            if not is_cluster:
                continue
            n = len(radii)
            inner_vals = radii[:n - len(outer)]
            if len(inner_vals) >= 4:
                inner_z_data[zl] = sorted(inner_vals)[len(inner_vals) // 2]
        
        if len(inner_z_data) >= 3:
            inner_z_sorted = sorted(inner_z_data.keys())
            top_z = inner_z_sorted[-1]
            
            # Look at top 35%: inner radius should be nearly constant (straight hole section)
            top_cut = top_z - height * 0.35
            top_zls = [zl for zl in inner_z_sorted if zl >= top_cut]
            bot_zls = [zl for zl in inner_z_sorted if zl < top_cut]
            
            # Accept 3-level meshes: 2 in top section + 1 in bottom
            # Accept 4+ level meshes: >=2 in each
            usable = (len(top_zls) >= 2 and len(bot_zls) >= 2) or \
                     (len(inner_z_data) == 3 and len(top_zls) == 2 and len(bot_zls) == 1)
            
            if usable:
                top_inner = [inner_z_data[zl] for zl in top_zls]
                bot_inner = [inner_z_data[zl] for zl in bot_zls]
                top_range = max(top_inner) - min(top_inner)
                top_mean = sum(top_inner) / len(top_inner)
                bot_range = max(bot_inner) - min(bot_inner)
                bot_min = min(bot_inner)
                
                # Criteria for stepped hole:
                # - Top section nearly constant radius (straight hole)
                # - Bottom inner radius significantly larger than top
                # - For 4+ levels: bottom section has significant taper
                # - For 3 levels: accept by gap between bottom and top inner
                if len(inner_z_data) >= 4:
                    is_stepped = (top_range < max(top_mean * 0.05, 0.10) and
                                  bot_range > max(top_mean * 0.08, 0.30) and
                                  top_mean < inner_radius * 0.85)
                else:
                    # 3-level mesh: check top flat + bottom significantly larger
                    is_stepped = (top_range < max(top_mean * 0.05, 0.10) and
                                  bot_min > top_mean * 1.3 and
                                  top_mean < inner_radius * 0.85)
                
                if is_stepped:
                    # Find step Z: maximum inner-radius gap between adjacent layers
                    best_gap = 0.0
                    step_z = top_cut
                    for i in range(len(inner_z_sorted) - 1):
                        r1 = inner_z_data[inner_z_sorted[i]]
                        r2 = inner_z_data[inner_z_sorted[i + 1]]
                        gap = abs(r2 - r1)
                        if gap > best_gap:
                            best_gap = gap
                            # Step is at the higher Z (smaller radius is above the step)
                            step_z = inner_z_sorted[i + 1]
                    
                    small_h = top_z - step_z
                    if 0.5 <= small_h <= height * 0.6:
                        # inner_top_radius (large hole radius at step) computed from
                        # bottom inner_radius and 2° taper (same as outer cone).
                        # This avoids mesh artifacts at the coincident step face.
                        inner_top_r = inner_radius - (height - small_h) * math.tan(math.radians(2))
                        stepped_hole_params = {
                            'small_hole_radius': top_mean,
                            'small_hole_height': small_h,
                            'inner_bottom_radius': inner_radius,
                            'inner_top_radius': max(inner_top_r, top_mean + 0.1),
                        }
                        log_to_file(f"[STEP Exporter] Detected stepped inner hole from mesh: "
                                    f"straight_r={top_mean:.3f} straight_h={small_h:.2f} "
                                    f"inner_bot_r={inner_radius:.3f} inner_top_r={inner_top_r:.3f} "
                                    f"step_gap={best_gap:.3f}")
    
    # 构建返回参数
    # 应用单位缩放：所有尺寸参数 × scale（mm=1000, m=1）
    S = scale if scale > 0 else 1.0
    
    # 检测到孔洞模式（顶部/底部盲孔）：返回盲孔圆柱体类型
    # 使用 OpenCASCADE 布尔减操作创建参数化盲孔
    if hole_pattern_detected:
        if hole_position == 'bottom':
            # 底部盲孔：如果 hole_radius/hole_depth 已在检测阶段设置，直接使用
            if hole_radius > 0 and hole_depth > 0:
                log_to_file(f"[STEP Exporter]   Using pre-computed blind hole params: hole_r={hole_radius:.4f} hole_d={hole_depth:.4f}")
            else:
                # 优先通过中间层内孔簇计算孔半径和深度
                hole_radius_from_cluster = False
                # 尝试在任何有两簇的层提取内孔半径（不限于底部层）
                for zl in sorted_z[:-1]:  # 检查所有非顶层
                    if len(z_layers[zl]) >= 16:
                        zl_radii = sorted(compute_radii(z_layers[zl]))
                        zl_cluster, zl_outer = has_two_clusters(zl_radii)
                        if zl_cluster:
                            n_z = len(zl_radii)
                            zl_inner = zl_radii[:n_z - len(zl_outer)]
                            inner_r = sorted(zl_inner)[len(zl_inner)//2] if zl_inner else 0
                            # 找内孔消失Z层
                            hole_end_z = zl
                            for zl2 in sorted_z[sorted_z.index(zl)+1:]:
                                if len(z_layers[zl2]) >= 16:
                                    zl2_radii = sorted(compute_radii(z_layers[zl2]))
                                    zl2_cluster, _ = has_two_clusters(zl2_radii)
                                    if zl2_cluster:
                                        hole_end_z = zl2
                                    else:
                                        break
                            hole_depth = hole_end_z - sorted_z[0]
                            if inner_r > 0.001 and hole_depth > height * 0.1:
                                hole_radius = inner_r
                                hole_radius_from_cluster = True
                                log_to_file(f"[STEP Exporter]   Bottom blind hole via cluster at z={zl:.4f}: inner_r={inner_r:.4f} hole_depth={hole_depth:.4f}")
                                break
                if not hole_radius_from_cluster:
                    # 回退：用顶点数比值法估算孔参数
                    bot_vc = len(z_layers[sorted_z[0]])
                    top_vc = len(z_layers[sorted_z[-1]])
                    if bot_vc > top_vc * 3:
                        b_radii = sorted(compute_radii(z_layers[sorted_z[0]]))
                        inner_count = max(4, len(b_radii) // 10)
                        hole_radius = sorted(b_radii[:inner_count])[inner_count//2]
                        # 孔深：底部以上顶点数最多的Z层（孔底平面）
                        best_z = sorted_z[0]
                        best_vc = 0
                        for zl in sorted_z[1:-1]:
                            vc = len(z_layers[zl])
                            if vc > best_vc:
                                best_vc = vc
                                best_z = zl
                        hole_end_z = best_z if best_vc > top_vc * 2 else sorted_z[0]
                        hole_depth = hole_end_z - sorted_z[0]
                        log_to_file(f"[STEP Exporter]   Bottom blind hole via vcount fallback: inner_r={hole_radius:.4f} hole_depth={hole_depth:.4f}")
                    else:
                        below_zls = [zl for zl in sorted_z if zl < body_end_z and zl in z_radius_data]
                        if below_zls:
                            hole_depth = body_end_z - sorted_z[0]
                            hole_wall_r = sorted([z_radius_data[zl] for zl in below_zls])
                            hole_radius = hole_wall_r[len(hole_wall_r)//2]
                        else:
                            hole_depth = height * 0.5
                            hole_radius = body_radius * 0.5
            body_radius_for_export = top_radius
        elif hole_position == 'both':
            # 双端盲孔：检测阶段已设置 hole_radius, hole_depth (底部), hole_depth_top (顶部)
            body_radius_for_export = top_radius
            log_to_file(f"[STEP Exporter]   Dual blind holes: using pre-computed params btm_d={hole_depth:.4f} top_d={hole_depth_top:.4f}")
        else:
            # 顶部盲孔：原有逻辑
            above_zls = [zl for zl in sorted_z if zl > body_end_z and zl in z_radius_data]
            z_hole_bottom = above_zls[0] if above_zls else sorted_z[-1]
            hole_depth = sorted_z[-1] - z_hole_bottom  # 从顶部到孔底的距离
            
            # 孔半径：取孔壁区域（非顶部混合层）的中位数半径
            hole_wall_zls = [zl for zl in above_zls if zl < sorted_z[-1] * 0.99]
            if hole_wall_zls:
                hole_wall_r = sorted([z_radius_data[zl] for zl in hole_wall_zls])
                hole_radius = hole_wall_r[len(hole_wall_r)//2]
            else:
                hole_radius = z_radius_data[above_zls[0]]
            body_radius_for_export = bottom_radius
        
        log_to_file(f"[STEP Exporter]   -> cylinder_blind_hole! r={body_radius_for_export:.3f} h={height:.3f} hole_r={hole_radius:.3f} hole_d={hole_depth:.3f} pos={hole_position}")
        hole_fillet_r = obj.get('hole_fillet_radius', 0.0) if hasattr(obj, 'get') else 0.0
        if hole_fillet_r > 0:
            log_to_file(f"[STEP Exporter]   hole fillet: r={hole_fillet_r:.3f}")
        result = {
            'obj_type': 'cylinder_blind_hole',
            'radius': body_radius_for_export * S,
            'height': height * S,
            'hole_radius': hole_radius * S,
            'hole_depth': hole_depth * S,
            'hole_fillet_radius': hole_fillet_r,  # 已为 mm，无需缩放
            'hole_position': hole_position,
            'pos_x': pos_x * S,
            'pos_y': pos_y * S,
            'pos_z': pos_z * S,
        }
        if hole_position == 'both':
            result['hole_depth_top'] = hole_depth_top * S
        return result
    
    bottom_radius *= S; top_radius *= S; height *= S
    pos_x *= S; pos_y *= S; pos_z *= S
    body_radius *= S
    if is_hollow: inner_radius *= S; inner_top_radius *= S
    if top_feature: top_feature_size *= S
    if bottom_feature: bottom_feature_size *= S
    if groove_params:
        for k in ('groove_depth', 'groove_bottom_width', 'groove_top_width', 'groove_extrusion_length'):
            if k in groove_params: groove_params[k] *= S
    if stepped_hole_params:
        for k in ('small_hole_radius', 'small_hole_height', 'inner_bottom_radius', 'inner_top_radius'):
            if k in stepped_hole_params: stepped_hole_params[k] *= S
    
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
                result['inner_bottom_radius'] = stepped_hole_params['inner_bottom_radius']
                result['inner_top_radius'] = stepped_hole_params['inner_top_radius']
            return result
    else:
        if bottom_radius * 0.98 <= top_radius <= bottom_radius * 1.02:
            # 使用体半径（过渡检测中已修正），避免极端z层混入面顶点导致半径偏小
            if body_radius and abs(body_radius - bottom_radius) / max(bottom_radius, 0.001) > 0.02:
                avg_radius = body_radius
            else:
                avg_radius = (bottom_radius + top_radius) / 2.0
            obj_type = 'cylinder'
            if top_feature == 'chamfer':
                if bottom_feature == 'fillet':
                    obj_type = 'cylinder_chamfer_fillet'
                elif bottom_feature == 'chamfer':
                    obj_type = 'cylinder_chamfer_both'
                else:
                    obj_type = 'cylinder_chamfer'
            elif top_feature == 'fillet':
                if bottom_feature == 'chamfer':
                    obj_type = 'cylinder_chamfer_fillet'  # reversed: chamfer at bottom
                elif bottom_feature == 'fillet':
                    obj_type = 'cylinder_fillet_both'
                else:
                    obj_type = 'cylinder_fillet'
            elif bottom_feature == 'fillet':
                obj_type = 'cylinder_fillet'
            elif bottom_feature == 'chamfer':
                obj_type = 'cylinder_chamfer'
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
                if top_feature == 'chamfer' and bottom_feature == 'chamfer':
                    obj_type = 'cone_chamfer'
                elif top_feature == 'fillet' and bottom_feature == 'fillet':
                    obj_type = 'cone_fillet'
                else:
                    obj_type = 'cone_chamfer_fillet'
            elif top_feature == 'chamfer' or bottom_feature == 'chamfer':
                obj_type = 'cone_chamfer'
            elif top_feature == 'fillet' or bottom_feature == 'fillet':
                obj_type = 'cone_fillet'
            # 锥体 + 特征：从过渡区边界获取正确的本体半径
            # body_radius 初始化为 bottom_radius（极端面半径），对于锥体不适用
            body_bot_r = bottom_radius
            body_top_r = top_radius
            if bottom_feature and bottom_transition_zls:
                bzls = sorted(bottom_transition_zls)
                if bzls:
                    body_bot_r = z_radius_data.get(bzls[-1], bottom_radius / S) * S
                    log_to_file(f"[STEP Exporter]   body_bot: z_range=[{bzls[0]:.6f},{bzls[-1]:.6f}] zls={len(bzls)} -> r={body_bot_r:.6f}")
            if top_feature and top_transition_zls:
                tzls = sorted(top_transition_zls)
                if tzls:
                    body_top_r = z_radius_data.get(tzls[0], top_radius / S) * S
                    log_to_file(f"[STEP Exporter]   body_top: z_range=[{tzls[0]:.6f},{tzls[-1]:.6f}] zls={len(tzls)} -> r={body_top_r:.6f}")
            log_to_file(f"[STEP Exporter]   CLASSIFIED: {obj_type} bR={body_bot_r:.6f} tR={body_top_r:.6f} h={height:.6f}")
            return {
                'obj_type': obj_type,
                'bottom_radius': body_bot_r,
                'top_radius': body_top_r,
                'height': height,
                'pos_x': pos_x,
                'pos_y': pos_y,
                'pos_z': pos_z,
                'top_feature': top_feature,
                'top_feature_size': top_feature_size,
                'bottom_feature': bottom_feature,
                'bottom_feature_size': bottom_feature_size,
            }


def _export_parametric_sync(filepath, bottom_shells, top_shells, cylinders, step_schema, step_unit, enable_logging, context):
    """同步导出所有参数化对象（底壳、顶壳、圆柱），用于后台模式回退"""
    import _step_exporter as cpp_exporter
    
    total = len(bottom_shells) + len(top_shells) + len(cylinders)
    if total == 0:
        log_to_file(f"[STEP Exporter] No parametric objects to export")
        return
    
    log_to_file(f"[STEP Exporter] Exporting {len(bottom_shells)} bottom + {len(top_shells)} top + {len(cylinders)} cylinders synchronously...")
    
    all_success = True
    temp_files = []
    temp_idx = 0
    
    # 导出底壳
    for idx, params in enumerate(bottom_shells):
        has_holes = params.get('has_holes', False)
        log_to_file(f"[STEP Exporter]   Exporting bottom shell {idx+1}/{len(bottom_shells)} ({'holes' if has_holes else 'no holes'})...")
        temp_file = filepath + f".temp{temp_idx}.step"
        temp_files.append(temp_file)
        temp_idx += 1
        
        if has_holes:
            success = cpp_exporter.export_bottom_shell_filleted_with_holes_step(
                temp_file, params['width'], params['depth'], params['outer_height'],
                params['bottom_thickness'], params['wall_thickness'], params['corner_radius'],
                params['outer_fillet_radius'], params['inner_fillet_radius'],
                params.get('step_height', 1.0), params.get('hole_radius', 1.5),
                params.get('hole_offset_x', 25.0), params.get('hole_offset_y', 20.0),
                params.get('pos_x', 0.0), params.get('pos_y', 0.0), params.get('pos_z', 0.0),
                step_schema, step_unit, 1 if enable_logging else 0)
        else:
            success = cpp_exporter.export_bottom_shell_filleted_step(
                temp_file, params['width'], params['depth'], params['outer_height'],
                params['bottom_thickness'], params['wall_thickness'], params['corner_radius'],
                params['outer_fillet_radius'], params['inner_fillet_radius'],
                params.get('step_height', 1.0), params.get('pos_x', 0.0),
                params.get('pos_y', 0.0), params.get('pos_z', 0.0),
                step_schema, step_unit, 1 if enable_logging else 0)
        if not success:
            all_success = False
            log_to_file(f"[STEP Exporter]   FAILED to export bottom shell {idx+1}")
        else:
            log_to_file(f"[STEP Exporter]   Bottom shell {idx+1} exported")
    
    # 导出顶壳
    for idx, tparams in enumerate(top_shells):
        log_to_file(f"[STEP Exporter]   Exporting top shell {idx+1}/{len(top_shells)}...")
        temp_file = filepath + f".temp{temp_idx}.step"
        temp_files.append(temp_file)
        temp_idx += 1
        
        success = cpp_exporter.export_top_shell_filleted_step(
            temp_file, tparams['width'], tparams['depth'], tparams['outer_height'],
            tparams['top_thickness'], tparams['wall_thickness'], tparams['corner_radius'],
            tparams['outer_fillet_radius'], tparams['inner_fillet_radius'],
            tparams['top_recess'], tparams['top_offset_y'],
            tparams.get('window_len', 0.0), tparams.get('window_wid', 0.0),
            tparams.get('step_ring_height', 0.0), tparams.get('step_ring_width', 0.0),
            tparams.get('pos_x', 0.0), tparams.get('pos_y', 0.0), tparams.get('pos_z', 0.0),
            step_schema, step_unit, tparams.get('window_data', ''),
            1 if enable_logging else 0)
        if not success:
            all_success = False
            log_to_file(f"[STEP Exporter]   FAILED to export top shell {idx+1}")
        else:
            log_to_file(f"[STEP Exporter]   Top shell {idx+1} exported")
    
    # 导出圆柱/圆锥
    for idx, cparams in enumerate(cylinders):
        obj_type = cparams.get('obj_type', 'cylinder')
        log_to_file(f"[STEP Exporter]   Exporting {obj_type} {idx+1}/{len(cylinders)}...")
        temp_file = filepath + f".temp{temp_idx}.step"
        temp_files.append(temp_file)
        temp_idx += 1
        
        px, py, pz = cparams.get('pos_x', 0.0), cparams.get('pos_y', 0.0), cparams.get('pos_z', 0.0)
        if obj_type == 'cylinder':
            success = cpp_exporter.export_cylinder_step(temp_file, cparams['radius'], cparams['height'],
                px, py, pz, step_schema, step_unit, 1 if enable_logging else 0)
        elif obj_type == 'cone':
            success = cpp_exporter.export_cone_step(temp_file, cparams['bottom_radius'], cparams['top_radius'],
                cparams['height'], px, py, pz, step_schema, step_unit, 1 if enable_logging else 0)
        elif obj_type == 'hollow_cylinder':
            success = cpp_exporter.export_hollow_cylinder_step(temp_file, cparams['outer_radius'],
                cparams['inner_radius'], cparams['height'], px, py, pz,
                step_schema, step_unit, 1 if enable_logging else 0)
        elif obj_type == 'cylinder_chamfer':
            success = cpp_exporter.export_cylinder_chamfer_step(
                temp_file, cparams['radius'], cparams['height'],
                cparams.get('top_feature_size', 0), px, py, pz,
                step_schema, step_unit, 1 if enable_logging else 0)
        elif obj_type == 'cylinder_fillet':
            success = cpp_exporter.export_cylinder_fillet_step(
                temp_file, cparams['radius'], cparams['height'],
                cparams.get('top_feature_size', 0), px, py, pz,
                step_schema, step_unit, 1 if enable_logging else 0)
        elif obj_type == 'cylinder_chamfer_fillet':
            reversed_flag = 1 if cparams.get('top_feature') == 'fillet' else 0
            chamfer_sz = cparams.get('top_feature_size', 0)
            fillet_sz = cparams.get('bottom_feature_size', 0)
            if reversed_flag:
                # 当 reversed_flag=1 时，top_feature 是 fillet，bottom_feature 是 chamfer
                # 传入 C++ 的参数需要对应交换：chamfer_size = bottom_feature_size, fillet_radius = top_feature_size
                chamfer_sz, fillet_sz = fillet_sz, chamfer_sz
                log_to_file(f"[STEP Exporter]   reversed_flag=1, swapped chamfer/fillet sizes: chamfer={chamfer_sz:.6f} fillet={fillet_sz:.6f}")
            log_to_file(f"[STEP Exporter]   export params: r={cparams['radius']:.6f} h={cparams['height']:.6f} chamfer={chamfer_sz:.6f} fillet={fillet_sz:.6f} reversed={reversed_flag}")
            success = cpp_exporter.export_cylinder_chamfer_fillet_step(
                temp_file, cparams['radius'], cparams['height'],
                chamfer_sz, fillet_sz,
                px, py, pz, step_schema, step_unit,
                1 if enable_logging else 0, reversed_flag)
            if success:
                try:
                    shell_cnt, face_cnts = _verify_step_shell(temp_file)
                    expected = 5
                    actual = face_cnts[0] if face_cnts else 0
                    if actual < expected:
                        log_to_file(f"[STEP Exporter]   WARNING: expected {expected} faces, got {actual} - chamfer/fillet may have failed!")
                    log_to_file(f"[STEP Exporter]   verify: {shell_cnt} shells, face counts: {face_cnts}")
                except Exception as ve:
                    log_to_file(f"[STEP Exporter]   verify error: {ve}")
        elif obj_type == 'cylinder_chamfer_both':
            success = cpp_exporter.export_cylinder_chamfer_both_step(
                temp_file, cparams['radius'], cparams['height'],
                cparams.get('top_feature_size', 0),
                cparams.get('bottom_feature_size', 0),
                px, py, pz, step_schema, step_unit,
                1 if enable_logging else 0)
        elif obj_type == 'cylinder_fillet_both':
            success = cpp_exporter.export_cylinder_fillet_both_step(
                temp_file, cparams['radius'], cparams['height'],
                cparams.get('top_feature_size', 0),
                cparams.get('bottom_feature_size', 0),
                px, py, pz, step_schema, step_unit,
                1 if enable_logging else 0)
        elif obj_type == 'cylinder_blind_hole':
            hole_pos = cparams.get('hole_position', 'top')
            if hole_pos == 'both':
                success = cpp_exporter.export_cylinder_dual_blind_holes_step(
                    temp_file, cparams['radius'], cparams['height'],
                    cparams['hole_radius'], cparams['hole_depth'],
                    cparams.get('hole_depth_top', 0),
                    cparams.get('hole_fillet_radius', 0),
                    px, py, pz, step_schema, step_unit,
                    1 if enable_logging else 0)
            else:
                success = cpp_exporter.export_cylinder_blind_hole_step(
                    temp_file, cparams['radius'], cparams['height'],
                    cparams['hole_radius'], cparams['hole_depth'],
                    cparams.get('hole_fillet_radius', 0),
                    hole_pos,
                    px, py, pz, step_schema, step_unit,
                    1 if enable_logging else 0)
        else:
            success = False
        if not success:
            all_success = False
            log_to_file(f"[STEP Exporter]   FAILED to export {obj_type} {idx+1}")
        else:
            log_to_file(f"[STEP Exporter]   {obj_type} {idx+1} exported")
            # 验证导出结果
            shell_cnt, face_cnts = _verify_step_shell(temp_file)
            log_to_file(f"[STEP Exporter]   verify: {shell_cnt} shells, face counts: {face_cnts}")
    
    # 合并或复制
    successful_temp_files = [tf for tf in temp_files if os.path.exists(tf)]
    successful_count = len(successful_temp_files)
    
    if successful_count > 1:
        try:
            _merge_step_files(filepath, successful_temp_files)
            log_to_file(f"[STEP Exporter] Merged {successful_count}/{total} parametric objects into {filepath}")
        except Exception as merge_err:
            log_to_file(f"[STEP Exporter] Failed to merge STEP files: {merge_err}")
            import traceback
            log_to_file(traceback.format_exc())
            if os.path.exists(successful_temp_files[0]):
                import shutil
                shutil.copy2(successful_temp_files[0], filepath)
    elif successful_count == 1:
        try:
            temp_file = successful_temp_files[0]
            temp_size = os.path.getsize(temp_file)
            log_to_file(f"[STEP Exporter] Merging single file: {temp_file} ({temp_size} bytes) -> {filepath}")
            os.replace(temp_file, filepath)
            log_to_file(f"[STEP Exporter] Single file merge OK")
        except Exception as merge_err:
            log_to_file(f"[STEP Exporter] os.replace failed: {merge_err}, trying shutil.copy2")
            import shutil
            try:
                shutil.copy2(temp_file, filepath)
                log_to_file(f"[STEP Exporter] shutil.copy2 fallback OK")
            except Exception as copy_err:
                log_to_file(f"[STEP Exporter] shutil.copy2 also failed: {copy_err}")
    else:
        log_to_file(f"[STEP Exporter] No parametric objects exported successfully")
    
    # 合并后验证输出文件
    if successful_count > 0:
        out_shell_cnt, out_face_cnts = _verify_step_shell(filepath)
        log_to_file(f"[STEP Exporter] post-merge verify: {out_shell_cnt} shells, face counts: {out_face_cnts}")
    
    # 清理临时文件
    for tf in temp_files:
        for ext in ('', '.log'):
            try:
                if os.path.exists(tf + ext):
                    os.remove(tf + ext)
            except:
                pass
    
    if successful_count == total:
        update_progress(100, "参数化导出完成", context)
        log_to_file(f"[STEP Exporter] All {total} parametric object(s) exported successfully")
    elif successful_count > 0:
        update_progress(100, f"部分导出: {successful_count}/{total}个成功", context)
        log_to_file(f"[STEP Exporter] {successful_count}/{total} parametric objects exported")
    else:
        update_progress(100, "参数化导出失败", context)
        log_to_file(f"[STEP Exporter] No parametric objects exported")


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


def _export_cylinder_staged(cpp_exporter, temp_file, cparams, data):
    """导出单个圆柱/圆锥类型对象到临时文件，返回成功标志"""
    log_to_file(f"[STEP Exporter]   [VER:v2] _export_cylinder_staged entry, obj_type={cparams.get('obj_type', '?')}")
    obj_type = cparams.get('obj_type', 'cylinder')
    px = cparams.get('pos_x', 0.0)
    py = cparams.get('pos_y', 0.0)
    pz = cparams.get('pos_z', 0.0)
    
    if obj_type == 'cylinder':
        return cpp_exporter.export_cylinder_step(
            temp_file, cparams['radius'], cparams['height'],
            px, py, pz, data['step_schema'], data['step_unit'],
            1 if data['enable_logging'] else 0)
    elif obj_type == 'cone':
        return cpp_exporter.export_cone_step(
            temp_file, cparams['bottom_radius'], cparams['top_radius'],
            cparams['height'], px, py, pz,
            data['step_schema'], data['step_unit'],
            1 if data['enable_logging'] else 0)
    elif obj_type == 'hollow_cylinder':
        return cpp_exporter.export_hollow_cylinder_step(
            temp_file, cparams['outer_radius'], cparams['inner_radius'],
            cparams['height'], px, py, pz,
            data['step_schema'], data['step_unit'],
            1 if data['enable_logging'] else 0)
    elif obj_type == 'hollow_cone':
        return cpp_exporter.export_hollow_cone_step(
            temp_file,
            cparams['outer_bottom_radius'], cparams['outer_top_radius'],
            cparams['inner_bottom_radius'], cparams['inner_top_radius'],
            cparams['height'], px, py, pz,
            data['step_schema'], data['step_unit'],
            1 if data['enable_logging'] else 0)
    elif obj_type == 'cylinder_chamfer':
        return cpp_exporter.export_cylinder_chamfer_step(
            temp_file, cparams['radius'], cparams['height'],
            cparams.get('top_feature_size', 0), px, py, pz,
            data['step_schema'], data['step_unit'],
            1 if data['enable_logging'] else 0)
    elif obj_type == 'cylinder_fillet':
        return cpp_exporter.export_cylinder_fillet_step(
            temp_file, cparams['radius'], cparams['height'],
            cparams.get('top_feature_size', 0), px, py, pz,
            data['step_schema'], data['step_unit'],
            1 if data['enable_logging'] else 0)
    elif obj_type == 'cylinder_chamfer_fillet':
        reversed_flag = 1 if cparams.get('top_feature') == 'fillet' else 0
        chamfer_sz = cparams.get('top_feature_size', 0)
        fillet_sz = cparams.get('bottom_feature_size', 0)
        if reversed_flag:
            # 当 reversed_flag=1 时，top_feature 是 fillet，bottom_feature 是 chamfer
            # 传入 C++ 的参数需要对应交换：chamfer_size = bottom_feature_size, fillet_radius = top_feature_size
            chamfer_sz, fillet_sz = fillet_sz, chamfer_sz
        log_to_file(f"[STEP Exporter]   export params: r={cparams['radius']:.6f} h={cparams['height']:.6f} chamfer={chamfer_sz:.6f} fillet={fillet_sz:.6f} reversed={reversed_flag}")
        result = cpp_exporter.export_cylinder_chamfer_fillet_step(
            temp_file, cparams['radius'], cparams['height'],
            chamfer_sz, fillet_sz,
            px, py, pz,
            data['step_schema'], data['step_unit'],
            1 if data['enable_logging'] else 0, reversed_flag)
        # 验证导出结果——带倒角圆角的圆柱体应有 5 个面，最少 3 个
        if result:
            try:
                shell_cnt, face_cnts = _verify_step_shell(temp_file)
                expected = 5
                actual = face_cnts[0] if face_cnts else 0
                if actual < expected:
                    log_to_file(f"[STEP Exporter]   WARNING: expected {expected} faces, got {actual} - chamfer/fillet may have failed!")
                log_to_file(f"[STEP Exporter]   verify: {shell_cnt} shells, face counts: {face_cnts}")
            except Exception as ve:
                log_to_file(f"[STEP Exporter]   verify error: {ve}")
        return result
    elif obj_type == 'cylinder_chamfer_both':
        return cpp_exporter.export_cylinder_chamfer_both_step(
            temp_file, cparams['radius'], cparams['height'],
            cparams.get('top_feature_size', 0),
            cparams.get('bottom_feature_size', 0),
            px, py, pz,
            data['step_schema'], data['step_unit'],
            1 if data['enable_logging'] else 0)
    elif obj_type == 'cylinder_fillet_both':
        return cpp_exporter.export_cylinder_fillet_both_step(
            temp_file, cparams['radius'], cparams['height'],
            cparams.get('top_feature_size', 0),
            cparams.get('bottom_feature_size', 0),
            px, py, pz,
            data['step_schema'], data['step_unit'],
            1 if data['enable_logging'] else 0)
    elif obj_type == 'cylinder_blind_hole':
        hole_pos = cparams.get('hole_position', 'top')
        if hole_pos == 'both':
            return cpp_exporter.export_cylinder_dual_blind_holes_step(
                temp_file, cparams['radius'], cparams['height'],
                cparams['hole_radius'], cparams['hole_depth'],
                cparams.get('hole_depth_top', 0),
                cparams.get('hole_fillet_radius', 0),
                px, py, pz,
                data['step_schema'], data['step_unit'],
                1 if data['enable_logging'] else 0)
        return cpp_exporter.export_cylinder_blind_hole_step(
            temp_file, cparams['radius'], cparams['height'],
            cparams['hole_radius'], cparams['hole_depth'],
            cparams.get('hole_fillet_radius', 0),
            hole_pos,
            px, py, pz,
            data['step_schema'], data['step_unit'],
            1 if data['enable_logging'] else 0)
    elif obj_type == 'cone_chamfer_fillet':
        # Determine feature order: C++ expects chamfer_size first, fillet_radius second
        # reversed=0: bottom chamfer + top fillet; reversed=1: bottom fillet + top chamfer
        bot_feat = cparams.get('bottom_feature')
        top_feat = cparams.get('top_feature')
        if bot_feat == 'fillet' and top_feat == 'chamfer':
            rev_flag = 1
            chamfer_sz = cparams.get('top_feature_size', 0)
            fillet_r = cparams.get('bottom_feature_size', 0)
        else:
            rev_flag = 0
            chamfer_sz = cparams.get('bottom_feature_size', 0)
            fillet_r = cparams.get('top_feature_size', 0)
        log_to_file(f"[STEP Exporter]   cone_chamfer_fillet: bR={cparams.get('bottom_radius',0):.4f} tR={cparams.get('top_radius',0):.4f} h={cparams['height']:.4f} chamfer_sz={chamfer_sz:.4f} fillet_r={fillet_r:.4f} reversed={rev_flag}")
        return cpp_exporter.export_cone_chamfer_fillet_step(
            temp_file,
            cparams.get('bottom_radius', cparams.get('radius', 0)),
            cparams.get('top_radius', 0), cparams['height'],
            chamfer_sz, fillet_r, rev_flag,
            px, py, pz,
            data['step_schema'], data['step_unit'],
            1 if data['enable_logging'] else 0)
    elif obj_type == 'cone_chamfer':
        has_bottom = cparams.get('bottom_feature') == 'chamfer'
        has_top = cparams.get('top_feature') == 'chamfer'
        if has_bottom and has_top:
            # Both ends chamfered: use new C++ function
            bot_sz = cparams.get('bottom_feature_size', 0)
            top_sz = cparams.get('top_feature_size', 0)
            log_to_file(f"[STEP Exporter]   cone_chamfer(both): bot_sz={bot_sz:.4f} top_sz={top_sz:.4f}")
            return cpp_exporter.export_cone_chamfer_step_both(
                temp_file,
                cparams.get('bottom_radius', cparams.get('radius', 0)),
                cparams.get('top_radius', 0), cparams['height'],
                bot_sz, top_sz, px, py, pz,
                data['step_schema'], data['step_unit'],
                1 if data['enable_logging'] else 0)
        else:
            chamfer_sz = cparams.get('bottom_feature_size', 0) if has_bottom else cparams.get('top_feature_size', 0)
            is_top = 1 if has_top else 0
            log_to_file(f"[STEP Exporter]   cone_chamfer: chamfer_sz={chamfer_sz:.4f} is_top={is_top}")
            return cpp_exporter.export_cone_chamfer_step(
                temp_file,
                cparams.get('bottom_radius', cparams.get('radius', 0)),
                cparams.get('top_radius', 0), cparams['height'],
                chamfer_sz, is_top, px, py, pz,
                data['step_schema'], data['step_unit'],
                1 if data['enable_logging'] else 0)
    elif obj_type == 'hollow_cone_fillet':
        return cpp_exporter.export_hollow_cone_fillet_step(
            temp_file,
            cparams.get('outer_bottom_radius', cparams.get('outer_radius', 0)),
            cparams.get('outer_top_radius', cparams.get('outer_radius', 0)),
            cparams.get('inner_bottom_radius', cparams.get('inner_radius', 0)),
            cparams.get('inner_top_radius', cparams.get('inner_radius', 0)),
            cparams['height'], cparams.get('top_feature_size', 0),
            px, py, pz, data['step_schema'], data['step_unit'],
            1 if data['enable_logging'] else 0)
    elif obj_type == 'hollow_cone_fillet_grooved':
        return cpp_exporter.export_hollow_cone_fillet_with_groove_step(
            temp_file,
            cparams.get('outer_bottom_radius', cparams.get('outer_radius', 0)),
            cparams.get('outer_top_radius', cparams.get('outer_radius', 0)),
            cparams.get('inner_bottom_radius', cparams.get('inner_radius', 0)),
            cparams.get('inner_top_radius', cparams.get('inner_radius', 0)),
            cparams['height'], cparams.get('top_feature_size', 0),
            cparams.get('groove_depth', 0),
            cparams.get('groove_bottom_width', 0),
            cparams.get('groove_top_width', 0),
            cparams.get('groove_extrusion_length', 0),
            px, py, pz, data['step_schema'], data['step_unit'],
            1 if data['enable_logging'] else 0)
    elif obj_type == 'cone_stepped_hole':
        top_fr = cparams.get('top_feature_size', 0.0) if cparams.get('top_feature') == 'fillet' else 0.0
        return cpp_exporter.export_cone_stepped_hole_step(
            temp_file,
            cparams.get('outer_bottom_radius', cparams.get('outer_radius', 0)),
            cparams.get('outer_top_radius', cparams.get('outer_radius', 0)),
            cparams['height'],
            cparams.get('small_hole_radius', 0),
            cparams.get('small_hole_height', 0),
            cparams.get('inner_bottom_radius', cparams.get('inner_radius', 0)),
            cparams.get('inner_top_radius', cparams.get('inner_radius', 0)),
            top_fr, px, py, pz, data['step_schema'], data['step_unit'],
            1 if data['enable_logging'] else 0)
    elif obj_type == 'cone_fillet':
        has_bottom = cparams.get('bottom_feature') == 'fillet'
        has_top = cparams.get('top_feature') == 'fillet'
        if has_bottom and has_top:
            # Both ends filleted: use new C++ function
            bot_r = cparams.get('bottom_feature_size', 0)
            top_r = cparams.get('top_feature_size', 0)
            log_to_file(f"[STEP Exporter]   cone_fillet(both): bot_r={bot_r:.4f} top_r={top_r:.4f}")
            return cpp_exporter.export_cone_fillet_step_both(
                temp_file,
                cparams.get('bottom_radius', cparams.get('radius', 0)),
                cparams.get('top_radius', 0), cparams['height'],
                bot_r, top_r, px, py, pz,
                data['step_schema'], data['step_unit'],
                1 if data['enable_logging'] else 0)
        else:
            return cpp_exporter.export_cone_chamfer_fillet_step(
                temp_file,
                cparams.get('bottom_radius', 0), cparams.get('top_radius', 0),
                cparams['height'], 0.0, cparams.get('top_feature_size', 0), 0,
                px, py, pz, data['step_schema'], data['step_unit'],
                1 if data['enable_logging'] else 0)
    elif obj_type == 'hollow_cylinder_fillet':
        return cpp_exporter.export_hollow_cylinder_fillet_step(
            temp_file,
            cparams.get('outer_radius', 0), cparams.get('inner_radius', 0),
            cparams['height'], cparams.get('top_feature_size', 0),
            px, py, pz, data['step_schema'], data['step_unit'],
            1 if data['enable_logging'] else 0)
    else:
        log_to_file(f"[STEP Exporter]   Unknown cylinder type: {obj_type}")
        return False


def _parametric_export_staged():
    """分阶段异步导出参数化物体。
    每个对象在独立的 timer tick 中处理，保证 Blender UI 能刷新进度条。
    返回正数表示继续下一个 tick，返回 None 表示完成/停止。
    """
    global _bottom_shell_export_data, _parametric_export_stage, _parametric_export_idx
    global _parametric_temp_files, _parametric_progress_val, _parametric_temp_success_count
    global _export_complete, _export_success, _export_log_file, _cpp_log_callback
    global _export_start_time, _stage_start_time
    
    import time
    
    if not _bottom_shell_export_data:
        return None
    
    data = None
    try:
        data = _bottom_shell_export_data
        context = data['context']
        shells = data.get('shells', [])
        top_shells_data = data.get('top_shells', [])
        cylinders = data.get('cylinders', [])
        regular_objects = data.get('regular_objects', [])
        
        import _step_exporter as cpp_exporter
        
        # === Stage 0: Init — 构建对象列表 ===
        if _parametric_export_stage == 0:
            _export_start_time = time.time()
            _stage_start_time = time.time()
            
            total_objects = len(shells) + len(top_shells_data) + len(cylinders) + len(regular_objects)
            if total_objects == 0:
                log_to_file(f"[STEP Exporter] No objects to export")
                end_progress(context)
                _bottom_shell_export_data = None
                _export_complete = True
                _export_success = True
                return None
            
            log_to_file(f"[STEP Exporter] Staged export: {len(shells)} bottom + {len(top_shells_data)} top + {len(cylinders)} cyl + {len(regular_objects)} mesh")
            _parametric_export_stage = 1
            _parametric_export_idx = 0
            _parametric_temp_files = []
            _parametric_progress_val = 10.0
            update_progress(10, f"开始导出 ({total_objects}个对象)...", context)
            
            elapsed = time.time() - _stage_start_time
            log_to_file(f"[STEP Exporter] [TIMING] Stage 0 (Init) completed in {elapsed:.3f}s")
            return 0.05
        
        # 构建扁平化对象列表（只在 stage 1 需要）
        all_objects = []
        for params in shells:
            all_objects.append(('bottom_shell', params))
        for tparams in top_shells_data:
            all_objects.append(('top_shell', tparams))
        for cparams in cylinders:
            all_objects.append(('cylinder', cparams))
        for obj in regular_objects:
            all_objects.append(('regular', obj))
        total_objects = len(all_objects)
        
        # === Stage 1: 逐个导出对象 ===
        if _parametric_export_stage == 1:
            if _parametric_export_idx == 0:
                _stage_start_time = time.time()
            
            if _parametric_export_idx >= total_objects:
                _parametric_export_stage = 2
                elapsed = time.time() - _stage_start_time
                log_to_file(f"[STEP Exporter] [TIMING] Stage 1 (Export {total_objects} objects) completed in {elapsed:.3f}s")
                return 0.05
            
            obj_type, obj_params = all_objects[_parametric_export_idx]
            obj_num = _parametric_export_idx + 1
            temp_file = data['filepath'] + f".temp{_parametric_export_idx}.step"
            _parametric_temp_files.append(temp_file)
            success = False
            
            obj_start = time.time()
            try:
                if obj_type == 'bottom_shell':
                    params = obj_params
                    has_holes = params.get('has_holes', False)
                    desc = "with_holes" if has_holes else "no_holes"
                    log_to_file(f"[STEP Exporter] Exporting bottom shell {obj_num}/{total_objects} ({desc})...")
                    
                    if has_holes:
                        success = cpp_exporter.export_bottom_shell_filleted_with_holes_step(
                            temp_file, params['width'], params['depth'], params['outer_height'],
                            params['bottom_thickness'], params['wall_thickness'],
                            params['corner_radius'], params['outer_fillet_radius'],
                            params['inner_fillet_radius'],
                            params.get('step_height', 1.0), params.get('hole_radius', 1.5),
                            params.get('hole_offset_x', 25.0), params.get('hole_offset_y', 20.0),
                            params.get('pos_x', 0.0), params.get('pos_y', 0.0), params.get('pos_z', 0.0),
                            data['step_schema'], data['step_unit'],
                            1 if data['enable_logging'] else 0)
                    else:
                        success = cpp_exporter.export_bottom_shell_filleted_step(
                            temp_file, params['width'], params['depth'], params['outer_height'],
                            params['bottom_thickness'], params['wall_thickness'],
                            params['corner_radius'], params['outer_fillet_radius'],
                            params['inner_fillet_radius'],
                            params.get('step_height', 1.0),
                            params.get('pos_x', 0.0), params.get('pos_y', 0.0), params.get('pos_z', 0.0),
                            data['step_schema'], data['step_unit'],
                            1 if data['enable_logging'] else 0)
                
                elif obj_type == 'top_shell':
                    tparams = obj_params
                    log_to_file(f"[STEP Exporter] Exporting top shell {obj_num}/{total_objects}...")
                    success = cpp_exporter.export_top_shell_filleted_step(
                        temp_file, tparams['width'], tparams['depth'], tparams['outer_height'],
                        tparams['top_thickness'], tparams['wall_thickness'],
                        tparams['corner_radius'], tparams['outer_fillet_radius'],
                        tparams['inner_fillet_radius'], tparams['top_recess'],
                        tparams['top_offset_y'],
                        tparams.get('window_len', 0.0), tparams.get('window_wid', 0.0),
                        tparams.get('step_ring_height', 0.0), tparams.get('step_ring_width', 0.0),
                        tparams.get('pos_x', 0.0), tparams.get('pos_y', 0.0), tparams.get('pos_z', 0.0),
                        data['step_schema'], data['step_unit'], tparams.get('window_data', ''),
                        1 if data['enable_logging'] else 0)
                
                elif obj_type == 'cylinder':
                    cparams = obj_params
                    obj_subtype = cparams.get('obj_type', 'cylinder')
                    log_to_file(f"[STEP Exporter] Exporting {obj_subtype} {obj_num}/{total_objects}...")
                    success = _export_cylinder_staged(cpp_exporter, temp_file, cparams, data)
                
                elif obj_type == 'regular':
                    obj = obj_params
                    log_to_file(f"[STEP Exporter] Exporting mesh {obj_num}/{total_objects}: {obj.name}...")
                    obj_data = _get_mesh_data_enhanced(obj, context, scale=1000.0)
                    if obj_data is None:
                        raise RuntimeError("_get_mesh_data_enhanced returned None")
                    _cpp_log_callback = lambda msg: log_to_file(msg)
                    init_ok = cpp_exporter.init_incremental_export(
                        temp_file, 1, 1000.0,
                        1 if data['fix_geometry'] else 0,
                        1 if data['create_solid'] else 0,
                        1 if data['advanced_brep'] else 0,
                        data['step_schema'], data['step_unit'],
                        1 if data['enable_logging'] else 0,
                        data.get('sew_tolerance', 0.001),
                        _cpp_log_callback)
                    if init_ok:
                        add_ok = cpp_exporter.add_object_to_export(obj_data, None)
                        cpp_exporter.finalize_incremental_export()
                        if add_ok:
                            log_to_file(f"[STEP Exporter]   Mesh {obj.name} exported ({len(obj_data['vertices'])} verts, {len(obj_data['faces'])} tris)")
                            success = True
                        else:
                            log_to_file(f"[STEP Exporter]   FAILED to add mesh {obj.name}")
                    else:
                        log_to_file(f"[STEP Exporter]   FAILED init incremental for {obj.name}")
                
                if success:
                    log_to_file(f"[STEP Exporter]   Object {obj_num}/{total_objects} OK ({time.time()-obj_start:.3f}s)")
                    # 验证导出结果
                    shell_cnt, face_cnts = _verify_step_shell(temp_file)
                    log_to_file(f"[STEP Exporter]   verify: {shell_cnt} shells, face counts: {face_cnts}")
                else:
                    log_to_file(f"[STEP Exporter]   Object {obj_num}/{total_objects} FAILED ({time.time()-obj_start:.3f}s)")
            except Exception as obj_err:
                log_to_file(f"[STEP Exporter]   ERROR exporting object {obj_num}: {obj_err} ({time.time()-obj_start:.3f}s)")
                import traceback
                log_to_file(traceback.format_exc())
            
            # 更新进度（10%-90% 之间均匀分布）
            _parametric_progress_val = 10.0 + (80.0 / max(total_objects, 1)) * obj_num
            type_names = {'bottom_shell': '底壳', 'top_shell': '顶壳', 'cylinder': '圆柱', 'regular': '网格'}
            type_name = type_names.get(obj_type, obj_type)
            update_progress(int(_parametric_progress_val), f"导出{type_name} {obj_num}/{total_objects}", context)
            
            _parametric_export_idx += 1
            return 0.05  # 继续下一个 tick
        
        # === Stage 2: 合并临时文件 ===
        elif _parametric_export_stage == 2:
            _stage_start_time = time.time()
            update_progress(90, "正在合并文件...", context)
            
            successful_temp_files = [tf for tf in _parametric_temp_files if os.path.exists(tf)]
            successful_count = len(successful_temp_files)
            
            if successful_count > 1:
                try:
                    _merge_step_files(data['filepath'], successful_temp_files)
                    log_to_file(f"[STEP Exporter] Merged {successful_count} objects into {data['filepath']}")
                except Exception as merge_err:
                    log_to_file(f"[STEP Exporter] Failed to merge STEP files: {merge_err}")
                    import traceback
                    log_to_file(traceback.format_exc())
                    if os.path.exists(successful_temp_files[0]):
                        try:
                            import shutil
                            shutil.copy2(successful_temp_files[0], data['filepath'])
                        except:
                            pass
                finally:
                    try:
                        _merge_log_files(os.path.dirname(data['filepath']), data['filepath'])
                    except:
                        pass
            elif successful_count == 1:
                try:
                    temp_file = successful_temp_files[0]
                    temp_size = os.path.getsize(temp_file) if os.path.exists(temp_file) else -1
                    log_to_file(f"[STEP Exporter] Merging single file: {temp_file} ({temp_size} bytes) -> {data['filepath']}")
                    os.replace(temp_file, data['filepath'])
                    log_to_file(f"[STEP Exporter] Single file merge OK")
                except Exception as merge_err:
                    log_to_file(f"[STEP Exporter] os.replace failed: {merge_err}, trying shutil.copy2")
                    import shutil
                    try:
                        shutil.copy2(temp_file, data['filepath'])
                        log_to_file(f"[STEP Exporter] shutil.copy2 fallback OK")
                    except Exception as copy_err:
                        log_to_file(f"[STEP Exporter] shutil.copy2 also failed: {copy_err}")
                finally:
                    try:
                        _merge_log_files(os.path.dirname(data['filepath']), data['filepath'])
                    except:
                        pass
            
            # 清理临时文件
            for tf in _parametric_temp_files:
                for ext in ('', '.log'):
                    try:
                        if os.path.exists(tf + ext):
                            os.remove(tf + ext)
                    except:
                        pass
            
            _parametric_temp_success_count = successful_count  # 保存成功计数供 Stage 3 使用
            _parametric_export_stage = 3
            elapsed = time.time() - _stage_start_time
            log_to_file(f"[STEP Exporter] [TIMING] Stage 2 (Merge) completed in {elapsed:.3f}s")
            # 合并后验证输出文件
            if successful_count > 0:
                out_shell_cnt, out_face_cnts = _verify_step_shell(data['filepath'])
                log_to_file(f"[STEP Exporter] post-merge verify: {out_shell_cnt} shells, face counts: {out_face_cnts}")
            return 0.05  # 进入完成阶段
        
        # === Stage 3: 完成 ===
        elif _parametric_export_stage == 3:
            successful_count = _parametric_temp_success_count
            total_for_count = max(total_objects, 1)
            
            if successful_count == total_for_count:
                update_progress(100, "参数化导出完成", context)
            elif successful_count > 0:
                update_progress(100, f"部分导出: {successful_count}/{total_for_count}个成功", context)
            else:
                update_progress(100, "参数化导出失败", context)
            
            end_progress(context)
            _bottom_shell_export_data = None
            _export_success = (successful_count > 0)
            _export_complete = True
            
            total_elapsed = time.time() - _export_start_time
            log_to_file(f"[STEP Exporter] [TIMING] Total export completed in {total_elapsed:.3f}s")
            
            if _export_log_file and not _export_log_file.closed:
                try:
                    _export_log_file.close()
                except:
                    pass
            return None  # 停止 timer
        
        return None  # 未知阶段，安全停止
        
    except Exception as e:
        log_to_file(f"[STEP Exporter] CRITICAL ERROR in staged parametric export: {e}")
        import traceback
        log_to_file(traceback.format_exc())
        try:
            if data and 'context' in data:
                end_progress(data['context'])
        except:
            pass
        _bottom_shell_export_data = None
        _export_complete = True
        _export_success = False
        if _export_log_file and not _export_log_file.closed:
            try:
                _export_log_file.close()
            except:
                pass
        return None


def _verify_step_shell(filepath):
    """快速验证 STEP 文件中的 CLOSED_SHELL 面数，用于诊断导出问题。
    返回 (shell_count, face_counts_list) 或 (0, []) 如果文件不存在."""
    import re
    if not os.path.exists(filepath):
        return 0, []
    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        # 查找所有 CLOSED_SHELL 定义: #N=CLOSED_SHELL('name',(#F1,#F2,...));
        shells = re.findall(r'#\d+\s*=\s*CLOSED_SHELL\s*\([^,]*,\s*\(([^)]*)\)', content)
        face_counts = []
        for s in shells:
            faces = [x.strip() for x in s.split(',') if x.strip().startswith('#')]
            face_counts.append(len(faces))
        return len(shells), face_counts
    except Exception:
        return 0, []


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
                _merge_log_files(os.path.dirname(params['filepath']), params['filepath'])
            except:
                pass
            
            # 关闭日志文件
            if _export_log_file and not _export_log_file.closed:
                _export_log_file.close()
            
            return None  # 停止 timer
        
        # 初始调用，设置阶段 1
        if _export_stage == 0:
            # 日志文件已在 execute() 中打开，此处不再重复打开
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
    
    _timer = None  # 事件定时器句柄，用于 modal 进度显示
    
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
        

    
    def modal(self, context, event):
        global _export_complete, _export_success, _export_log_file
        
        if event.type == 'TIMER':
            if _export_complete:
                log_to_file(f"[STEP Exporter] Modal: export complete, success={_export_success}, cleaning up...")
                
                # 移除事件定时器
                if self._timer:
                    try:
                        context.window_manager.event_timer_remove(self._timer)
                    except:
                        pass
                    self._timer = None
                
                # 结束进度条（wm.progress + operator.report）
                end_progress(context)
                clear_operator()
                
                # 关闭日志文件
                if _export_log_file and not _export_log_file.closed:
                    _export_log_file.close()
                    _export_log_file = None
                
                # 合并日志文件（参数化路径）
                try:
                    _merge_log_files(os.path.dirname(self.filepath), self.filepath)
                except:
                    pass
                
                if _export_success:
                    self.report({'INFO'}, "STEP 导出完成")
                else:
                    self.report({'ERROR'}, "STEP 导出失败，请查看日志")
                
                return {'FINISHED'}
            
            # 在modal handler中执行分阶段导出，确保UI能刷新进度条
            try:
                next_tick = _parametric_export_staged()
                if next_tick is None:
                    # 导出完成
                    _export_complete = True
                    return {'PASS_THROUGH'}
                
                # 强制刷新3D视图UI以确保进度条更新可见
                try:
                    for area in context.screen.areas:
                        if area.type == 'VIEW_3D':
                            area.tag_redraw()
                            break
                except:
                    pass
                
                return {'PASS_THROUGH'}
            except Exception as e:
                log_to_file(f"[STEP Exporter] Modal export error: {e}")
                import traceback
                log_to_file(traceback.format_exc())
                _export_success = False
                _export_complete = True
                return {'PASS_THROUGH'}
        
        return {'PASS_THROUGH'}

    def execute(self, context):
        if not CPP_MODULE_LOADED or not step_exporter:
            self.report({'ERROR'}, "C++ extension module '_step_exporter' not loaded. Check console for details.")
            return {'CANCELLED'}
        
        # 尽早打开日志文件，确保所有 [STEP Exporter] 日志都写入 .step.log
        global _export_log_file, _log_buffer, _export_complete, _export_success
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
        
        # 启动进度条显示（使用 built-in wm.progress API）
        set_operator(self)
        log_to_file(f"[STEP Exporter] === Calling start_progress ===")
        start_progress(context)
        
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
        top_shells = []
        cylinder_objects = []
        regular_export_objects = []
        
        for obj in _export_objects:
            if obj.type == 'MESH':
                log_to_file(f"[STEP Exporter] Checking: {obj.name}")
                
                # 如果对象标记了需要使用网格导出（如包含通孔），则跳过参数化分析
                if obj.get("step_use_mesh", False):
                    log_to_file(f"[STEP Exporter]   -> marked for mesh export (has holes/cuts)")
                    regular_export_objects.append(obj)
                    continue
                
                # 先检测圆柱/圆锥（优先于壳检测，避免 chamfer+fillet 圆柱被误判为顶壳）
                cyl_params = _analyze_cylinder_from_mesh(obj, context, scale)
                if cyl_params:
                    cylinder_objects.append(cyl_params)
                    log_to_file(f"[STEP Exporter]   -> {cyl_params['obj_type']}! r={cyl_params.get('radius', cyl_params.get('bottom_radius', '?'))} h={cyl_params['height']}")
                    log_to_file(f"[STEP Exporter] Found {cyl_params['obj_type']}: {obj.name}")
                    continue
                
                # 再检测底壳
                shell_params = _analyze_bottom_shell_from_mesh(obj, context, scale)
                if shell_params:
                    bottom_shells.append(shell_params)
                    hh = shell_params.get('has_holes', False)
                    log_to_file(f"[STEP Exporter]   -> Bottom shell! has_holes={hh}")
                    log_to_file(f"[STEP Exporter] Found bottom shell: {obj.name} (has_holes={shell_params.get('has_holes', False)})")
                    continue

                # 最后检测顶壳（锥形渐缩壳）
                top_shell_params = _analyze_top_shell_from_mesh(obj, context, scale)
                if top_shell_params:
                    top_shells.append(top_shell_params)
                    log_to_file(f"[STEP Exporter]   -> Top shell! recess={top_shell_params.get('top_recess',0):.1f}")
                    log_to_file(f"[STEP Exporter] Found top shell: {obj.name}")
                    continue
                
                log_to_file(f"[STEP Exporter]   -> NOT a parametric object")
                regular_export_objects.append(obj)
            elif obj.type == 'CURVE':
                regular_export_objects.append(obj)
        
        total_parametric = len(bottom_shells) + len(top_shells) + len(cylinder_objects)
        log_to_file(f"[STEP Exporter] Total objects: {len(_export_objects)}, bottom_shells: {len(bottom_shells)}, top_shells: {len(top_shells)}, cylinders: {len(cylinder_objects)}, regular: {len(regular_export_objects)}")
        
        if bottom_shells or top_shells or cylinder_objects:
            log_to_file(f"[STEP Exporter] Found {total_parametric} parametric object(s) (+ {len(regular_export_objects)} regular), using parametric export")
            update_progress(10, "检测到参数化对象，正在导出...", context)

            # 日志文件已在 execute() 开头打开，此处确保可用即可

            global _bottom_shell_export_data
            _bottom_shell_export_data = {
                'filepath': self.filepath,
                'shells': bottom_shells,
                'top_shells': top_shells,
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

            _export_complete = False
            _export_success = False
            
            # 重置分阶段导出状态
            global _parametric_export_stage, _parametric_export_idx, _parametric_temp_files, _parametric_progress_val
            _parametric_export_stage = 0
            _parametric_export_idx = 0
            _parametric_temp_files = []
            _parametric_progress_val = 0.0
            
            # 后台模式：直接在循环中运行分阶段导出（无UI，无需modal）
            if bpy.app.background:
                log_to_file(f"[STEP Exporter] Background mode: running staged export synchronously")
                try:
                    while True:
                        next_tick = _parametric_export_staged()
                        if next_tick is None:
                            break
                except Exception as e:
                    log_to_file(f"[STEP Exporter] Background export error: {e}")
                    import traceback
                    log_to_file(traceback.format_exc())
                    _export_success = False
                    _export_complete = True
                
                # 清理
                end_progress(context)
                clear_operator()
                if _export_log_file and not _export_log_file.closed:
                    _export_log_file.close()
                    _export_log_file = None
                try:
                    _merge_log_files(os.path.dirname(self.filepath), self.filepath)
                except:
                    pass
                
                log_to_file(f"[STEP Exporter] Background export done, success={_export_success}")
                self.report({'INFO' if _export_success else 'ERROR'}, "STEP 导出完成" if _export_success else "STEP 导出失败")
                return {'FINISHED'}
            
            # UI模式：注册事件定时器用于modal进度更新
            wm = context.window_manager
            self._timer = wm.event_timer_add(0.1, window=context.window)
            wm.modal_handler_add(self)
            log_to_file(f"[STEP Exporter] Modal handler and event timer registered")

            return {'RUNNING_MODAL'}
        
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
        global _export_stage, _export_objects_data, _export_current_index
        _export_complete = False
        _export_success = False
        _export_stage = 0
        _export_objects_data = []
        _export_current_index = 0

        # 注册事件定时器用于modal进度更新
        wm = context.window_manager
        self._timer = wm.event_timer_add(0.2, window=context.window)
        wm.modal_handler_add(self)
        log_to_file(f"[STEP Exporter] Modal handler and event timer registered (regular path)")

        log_to_file(f"[STEP Exporter] === Registering app timer ===")
        log_to_file(f"[STEP Exporter] Objects to export: {len(_export_objects)}")

        # 包装 _export_worker_timer，完成后设置完成标志
        def _async_regular_worker():
            global _export_complete, _export_success
            try:
                result = _export_worker_timer()
                if result is None:
                    # timer 停止，导出完成（可能成功也可能失败，由内部决定）
                    _export_success = True
                    _export_complete = True
                    return None
                return result
            except Exception as e:
                log_to_file(f"[STEP Exporter] Async regular export error: {e}")
                import traceback
                log_to_file(traceback.format_exc())
                _export_success = False
                _export_complete = True
                return None

        # 将导出工作交给 app timer，让 modal operator 保持生命周期
        bpy.app.timers.register(_async_regular_worker, first_interval=0.1)
        log_to_file(f"[STEP Exporter] App timer registered for regular export")

        # 返回 RUNNING_MODAL 保持 operator 生命周期，进度条才能持续显示
        return {'RUNNING_MODAL'}
    
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
            # 直接使用 obj.data，因为修改器已经被应用
            eval_mesh = obj.data
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
                oc_ver = step_exporter.get_occt_version() if hasattr(step_exporter, 'get_occt_version') else "7.7.2"
                box.label(text=f"✓ OpenCASCADE {oc_ver} ready", icon='CHECKMARK')
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
        
        # 样品生成
        layout.separator()
        layout.label(text="Sample Generators", icon='MESH_DATA')
        col = layout.column(align=True)
        col.operator("step_exporter.create_top_shell", text="Create Top Shell", icon='MESH_PLANE')
        col.operator("step_exporter.create_bottom_shell", text="Create Bottom Shell", icon='MESH_PLANE')
        col.operator("step_exporter.create_cylinder", text="Create Cylinder", icon='MESH_CYLINDER')

# ====================== 样品生成 Operators ======================

class STEP_EXPORTER_OT_create_top_shell(Operator):
    """创建带开窗的塑料顶壳样品"""
    bl_idname = "step_exporter.create_top_shell"
    bl_label = "Create Top Shell"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        script_path = os.path.join(os.path.dirname(__file__), 'test', 'create_top_shell.py')
        exec(compile(open(script_path).read(), script_path, 'exec'), {'__name__': '__main__', '__file__': script_path})
        self.report({'INFO'}, "Top shell created")
        return {'FINISHED'}


class STEP_EXPORTER_OT_create_bottom_shell(Operator):
    """创建带螺栓孔的塑料底壳样品"""
    bl_idname = "step_exporter.create_bottom_shell"
    bl_label = "Create Bottom Shell"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        script_path = os.path.join(os.path.dirname(__file__), 'test', 'create_bottom_shell.py')
        old_argv = sys.argv
        try:
            sys.argv = [sys.argv[0] if len(sys.argv) > 0 else "", "with_holes"]
            exec(compile(open(script_path).read(), script_path, 'exec'), {'__name__': '__main__'})
        finally:
            sys.argv = old_argv
        self.report({'INFO'}, "Bottom shell created")
        return {'FINISHED'}


class STEP_EXPORTER_OT_create_cylinder(Operator):
    """创建机械圆柱体样品"""
    bl_idname = "step_exporter.create_cylinder"
    bl_label = "Create Cylinder"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        script_path = os.path.join(os.path.dirname(__file__), 'test', 'create_mesh_cylinder.py')
        exec(compile(open(script_path).read(), script_path, 'exec'), {'__name__': '__main__', '__file__': script_path})
        self.report({'INFO'}, "Cylinder created")
        return {'FINISHED'}


# ====================== 参数化圆柱生成 Operator ======================

class STEP_EXPORTER_OT_create_parametric_cylinder(Operator):
    """创建参数化圆柱体（标准/锥形，带倒角/开孔）"""
    bl_idname = "step_exporter.create_parametric_cylinder"
    bl_label = "Parametric Cylinder"
    bl_options = {'REGISTER', 'UNDO'}
    
    # === 圆柱类型 ===
    cylinder_type: EnumProperty(
        name="Type",
        description="Cylinder type",
        items=[
            ('standard', "Standard", "Standard cylinder"),
            ('tapered', "Tapered", "Tapered cylinder (truncated cone)"),
        ],
        default='standard',
    )
    # 标准圆柱
    radius: FloatProperty(
        name="Radius", default=15.0, min=0.5, max=500.0,
    )
    # 锥形圆柱
    top_radius: FloatProperty(
        name="Top R", default=10.0, min=0.1, max=500.0,
    )
    bottom_radius: FloatProperty(
        name="Bottom R", default=20.0, min=0.1, max=500.0,
    )
    # 通用
    height: FloatProperty(
        name="Height", default=40.0, min=0.5, max=500.0,
    )
    segments: IntProperty(
        name="Segments", default=64, min=8, max=256,
    )
    
    # === 单位 ===
    unit: EnumProperty(
        name="Unit",
        items=[
            ('mm', "mm", "Millimeters (input ×0.001 → meters)"),
            ('m', "m", "Meters (input ×1.0, no conversion)"),
        ],
        default='mm',
    )
    
    # === 倒角 ===
    chamfer_type: EnumProperty(
        name="Chamfer",
        items=[
            ('none', "None", "No edge treatment"),
            ('chamfer', "Chamfer", "Top chamfer only"),
            ('fillet', "Fillet", "Top fillet only"),
            ('chamfer_fillet', "Chamfer+Fillet", "Top chamfer + bottom fillet"),
            ('chamfer_both', "Both Chamfer", "Top & bottom chamfer"),
            ('fillet_both', "Both Fillet", "Top & bottom fillet"),
        ],
        default='none',
    )
    chamfer_size: FloatProperty(
        name="Chamfer Size", default=2.0, min=0.1, max=50.0,
    )
    fillet_radius: FloatProperty(
        name="Fillet R", default=2.0, min=0.1, max=50.0,
    )
    
    # === 孔 ===
    hole_type: EnumProperty(
        name="Hole",
        items=[
            ('none', "None", "Solid cylinder, no hole"),
            ('top', "Top", "Blind hole from top"),
            ('bottom', "Bottom", "Blind hole from bottom"),
            ('both', "Both", "Blind holes from top and bottom"),
            ('through', "Through", "Through hole (top to bottom)"),
        ],
        default='none',
    )
    hole_radius: FloatProperty(
        name="Hole R", default=5.0, min=0.1, max=100.0,
    )
    hole_depth: FloatProperty(
        name="Hole Depth %", default=50.0, min=1.0, max=100.0, subtype='PERCENTAGE',
        description="Hole depth as percentage of cylinder height (for blind holes)",
    )
    hole_is_tapered: BoolProperty(
        name="Tapered Hole", default=False,
    )
    hole_top_radius: FloatProperty(
        name="Hole Top R", default=6.0, min=0.1, max=100.0,
    )
    hole_bottom_radius: FloatProperty(
        name="Hole Bottom R", default=4.0, min=0.1, max=100.0,
    )
    hole_fillet_radius: FloatProperty(
        name="Hole Fillet R", default=0.5, min=0.0, max=50.0,
        description="Fillet radius for hole opening edge (0 = no fillet)",
    )
    
    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=320)
    
    def draw(self, context):
        layout = self.layout
        
        # Cylinder type
        box = layout.box()
        box.label(text="Cylinder", icon='MESH_CYLINDER')
        box.prop(self, 'unit')
        box.prop(self, 'cylinder_type')
        if self.cylinder_type == 'standard':
            box.prop(self, 'radius')
        else:
            box.prop(self, 'top_radius')
            box.prop(self, 'bottom_radius')
        box.prop(self, 'height')
        box.prop(self, 'segments')
        
        # Chamfer/Fillet
        box = layout.box()
        box.label(text="Edge Treatment", icon='MOD_BEVEL')
        box.prop(self, 'chamfer_type')
        if self.chamfer_type in ('chamfer', 'both'):
            box.prop(self, 'chamfer_size')
        if self.chamfer_type in ('fillet', 'both'):
            box.prop(self, 'fillet_radius')
        
        # Hole
        box = layout.box()
        box.label(text="Hole", icon='MESH_CYLINDER')
        box.prop(self, 'hole_type')
        if self.hole_type != 'none':
            box.prop(self, 'hole_is_tapered')
            if self.hole_is_tapered:
                box.prop(self, 'hole_top_radius')
                box.prop(self, 'hole_bottom_radius')
            else:
                box.prop(self, 'hole_radius')
            if self.hole_type in ('top', 'bottom', 'both'):
                box.prop(self, 'hole_depth')
            box.prop(self, 'hole_fillet_radius')
    
    def execute(self, context):
        try:
            obj = _generate_parametric_cylinder(self)
            if obj:
                obj.select_set(True)
                context.view_layer.objects.active = obj
                self.report({'INFO'}, "Cylinder created: " + obj.name)
        except Exception as e:
            self.report({'ERROR'}, str(e))
            import traceback; traceback.print_exc()
            return {'CANCELLED'}
        return {'FINISHED'}


def _generate_parametric_cylinder(props):
    """使用 BMesh 生成参数化圆柱体"""
    import bmesh, math
    
    # 单位缩放因子 (Blender 内部单位为米)
    # mm: 用户输入毫米 → 转为米 (×0.001)
    # m:  用户输入米 → 保持不变 (×1.0)
    S = 0.001 if props.unit == 'mm' else 1.0
    
    Z_UP = (0, 0, 1)
    Z_DOWN = (0, 0, -1)
    
    # === 1. 创建基础圆柱体 mesh ===
    bm = bmesh.new()
    
    if props.cylinder_type == 'standard':
        # 标准圆柱：用旋绕
        R = props.radius * S
        H = props.height * S
        geom = bmesh.ops.create_circle(
            bm, cap_ends=False, radius=R, segments=props.segments,
        )
        verts_circ = geom['verts']
        # 排序顶点（沿圆周逆时针）
        verts_circ = sorted(verts_circ, key=lambda v: math.atan2(v.co.y, v.co.x))
        
        # 拉伸到底面
        bottom_z = -H / 2.0
        top_z = H / 2.0
        
        # 底部面顶点
        verts_bottom = []
        for v in verts_circ:
            nv = bm.verts.new((v.co.x, v.co.y, bottom_z))
            verts_bottom.append(nv)
        # 顶部面顶点
        verts_top = []
        for v in verts_circ:
            nv = bm.verts.new((v.co.x, v.co.y, top_z))
            verts_top.append(nv)
        bm.verts.index_update()
        
        # 删除原始圆
        bmesh.ops.delete(bm, geom=verts_circ, context='VERTS')
        
        # 创建侧面
        n = len(verts_bottom)
        for i in range(n):
            j = (i + 1) % n
            bm.faces.new((verts_bottom[i], verts_bottom[j], verts_top[j], verts_top[i]))
        
        # 顶面和底面 (法线必须朝外)
        bm.faces.new(verts_top)                     # 顶面法线 +Z
        bm.faces.new(list(reversed(verts_bottom)))  # 底面法线 -Z
        
    else:
        # 锥形圆柱
        BR = props.bottom_radius * S
        TR = props.top_radius * S
        H = props.height * S
        geom = bmesh.ops.create_circle(
            bm, cap_ends=False, radius=BR, segments=props.segments,
        )
        verts_circ_bottom = sorted(geom['verts'], key=lambda v: math.atan2(v.co.y, v.co.x))
        
        bottom_z = -H / 2.0
        top_z = H / 2.0
        
        # 创建底部顶点
        verts_bottom = []
        for v in verts_circ_bottom:
            nv = bm.verts.new((v.co.x, v.co.y, bottom_z))
            verts_bottom.append(nv)
        bmesh.ops.delete(bm, geom=verts_circ_bottom, context='VERTS')
        
        # 创建顶部顶点（较小半径）
        geom2 = bmesh.ops.create_circle(
            bm, cap_ends=False, radius=TR, segments=props.segments,
        )
        verts_circ_top = sorted(geom2['verts'], key=lambda v: math.atan2(v.co.y, v.co.x))
        verts_top = []
        for v in verts_circ_top:
            nv = bm.verts.new((v.co.x, v.co.y, top_z))
            verts_top.append(nv)
        bmesh.ops.delete(bm, geom=verts_circ_top, context='VERTS')
        
        bm.verts.index_update()
        
        # 侧面
        n = len(verts_bottom)
        for i in range(n):
            j = (i + 1) % n
            bm.faces.new((verts_bottom[i], verts_bottom[j], verts_top[j], verts_top[i]))
        
        # 顶面和底面 (法线必须朝外)
        bm.faces.new(verts_top)                     # 顶面法线 +Z
        bm.faces.new(list(reversed(verts_bottom)))  # 底面法线 -Z
    
    bm.normal_update()
    
    # 写入临时 mesh
    mesh_name = "Cylinder_Mesh"
    mesh = bpy.data.meshes.new(mesh_name)
    bm.to_mesh(mesh)
    bm.free()
    
    obj = bpy.data.objects.new("ParametricCylinder", mesh)
    bpy.context.collection.objects.link(obj)
    
    # === 2. 应用倒角/圆角（顶部边缘） ===
    if props.chamfer_type != 'none':
        _apply_edge_treatment(obj, props, S)
    
    # === 3. 创建孔 ===
    if props.hole_type != 'none':
        _create_holes(obj, props, S)
    
    # 存储圆倒角参数到自定义属性，供导出时读取
    if props.hole_fillet_radius > 0:
        obj['hole_fillet_radius'] = props.hole_fillet_radius
    
    return obj


def _apply_edge_treatment(obj, props, S):
    """在边缘应用倒角/圆角"""
    bpy.ops.object.select_all(action='DESELECT')
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    bpy.ops.object.mode_set(mode='EDIT')
    
    bm = bmesh.from_edit_mesh(obj.data)
    bm.edges.ensure_lookup_table()
    
    H = props.height * S
    top_z = H / 2.0
    btm_z = -H / 2.0
    CS = props.chamfer_size * S
    FR = props.fillet_radius * S
    
    def select_edge_loop(z_target):
        for e in bm.edges: e.select = False
        for v in bm.verts: v.select = False
        bm.select_flush(False)
        for edge in bm.edges:
            v0_z = edge.verts[0].co.z
            v1_z = edge.verts[1].co.z
            if abs(v0_z - z_target) < 0.001 and abs(v1_z - z_target) < 0.001:
                edge.select = True
        bmesh.update_edit_mesh(obj.data)
    
    if props.chamfer_type == 'chamfer':
        # 仅顶部斜倒角
        select_edge_loop(top_z)
        bpy.ops.mesh.bevel(offset_type='OFFSET', offset=CS, segments=1, profile=0.0, affect='EDGES')
    
    elif props.chamfer_type == 'fillet':
        # 仅顶部圆倒角
        select_edge_loop(top_z)
        bpy.ops.mesh.bevel(offset_type='OFFSET', offset=FR, segments=16, profile=0.5, affect='EDGES')
    
    elif props.chamfer_type == 'chamfer_fillet':
        # 顶部斜倒角 + 底部圆倒角
        select_edge_loop(top_z)
        bpy.ops.mesh.bevel(offset_type='OFFSET', offset=CS, segments=1, profile=0.0, affect='EDGES')
        bm = bmesh.from_edit_mesh(obj.data)
        select_edge_loop(btm_z)
        bpy.ops.mesh.bevel(offset_type='OFFSET', offset=FR, segments=16, profile=0.5, affect='EDGES')
    
    elif props.chamfer_type == 'chamfer_both':
        # 顶部 + 底部斜倒角
        select_edge_loop(top_z)
        bpy.ops.mesh.bevel(offset_type='OFFSET', offset=CS, segments=1, profile=0.0, affect='EDGES')
        bm = bmesh.from_edit_mesh(obj.data)
        select_edge_loop(btm_z)
        bpy.ops.mesh.bevel(offset_type='OFFSET', offset=CS, segments=1, profile=0.0, affect='EDGES')
    
    elif props.chamfer_type == 'fillet_both':
        # 顶部 + 底部圆倒角（一次 bevel 选中两个边环）
        select_edge_loop(top_z)
        bm = bmesh.from_edit_mesh(obj.data)
        for edge in bm.edges:
            v0_z = edge.verts[0].co.z
            v1_z = edge.verts[1].co.z
            if abs(v0_z - btm_z) < 0.001 and abs(v1_z - btm_z) < 0.001:
                edge.select = True
        bmesh.update_edit_mesh(obj.data)
        bpy.ops.mesh.bevel(offset_type='OFFSET', offset=FR, segments=16, profile=0.5, affect='EDGES')
    
    bpy.ops.object.mode_set(mode='OBJECT')


def _create_holes(obj, props, S):
    """创建孔（布尔减）"""
    import bmesh, math
    
    H = props.height * S
    hole_d = props.hole_depth / 100.0 * H if props.hole_type in ('top', 'bottom', 'both') else H + 20.0
    
    # 判断孔半径
    if props.hole_is_tapered:
        hr_top = props.hole_top_radius * S
        hr_bottom = props.hole_bottom_radius * S
    else:
        hr_top = props.hole_radius * S
        hr_bottom = props.hole_radius * S
    
    cutters = []
    
    def make_hole_cutter(cut_name, z_bottom, z_top, r_bottom, r_top):
        """使用 Blender 原生圆柱体创建切割体（比手动 bmesh 更可靠）"""
        cutter_height = z_top - z_bottom
        cutter_z = (z_top + z_bottom) / 2.0
        avg_r = (r_bottom + r_top) / 2.0
        
        # 使用 Blender 原生圆柱体
        bpy.ops.mesh.primitive_cylinder_add(
            vertices=64, radius=avg_r, depth=cutter_height,
            location=(0, 0, cutter_z)
        )
        obj_c = bpy.context.active_object
        obj_c.name = cut_name
        obj_c.hide_set(True)
        obj_c.hide_render = True
        return obj_c
    
    hh = H
    ext = max(hr_bottom, hole_d * 0.5) if props.hole_type != 'through' else max(hr_bottom, H * 0.5)
    
    log_to_file(f"[STEP Exporter] _create_holes: H={H:.4f} hole_d={hole_d:.4f} hole_radius={hr_bottom:.4f} ext={ext:.4f} type={props.hole_type}")
    
    if props.hole_type == 'through':
        cutters.append(make_hole_cutter(
            "HoleCutter_Through",
            -hh / 2 - ext, hh / 2 + ext, hr_bottom, hr_top
        ))
    elif props.hole_type == 'top':
        cutters.append(make_hole_cutter(
            "HoleCutter_Top",
            hh / 2 - hole_d, hh / 2 + ext, hr_top, hr_top
        ))
    elif props.hole_type == 'bottom':
        cutters.append(make_hole_cutter(
            "HoleCutter_Bottom",
            -hh / 2 - ext, -hh / 2 + hole_d, hr_bottom, hr_bottom
        ))
    elif props.hole_type == 'both':
        cutters.append(make_hole_cutter(
            "HoleCutter_Top",
            hh / 2 - hole_d, hh / 2 + ext, hr_top, hr_top
        ))
        cutters.append(make_hole_cutter(
            "HoleCutter_Bottom",
            -hh / 2 - ext, -hh / 2 + hole_d, hr_bottom, hr_bottom
        ))
    
    # 布尔减：先创建所有 modifier，再一次性通过 depsgraph 应用
    mod_names = []
    for cutter in cutters:
        mod_name = "Bool_Hole_" + cutter.name
        mod = obj.modifiers.new(name=mod_name, type='BOOLEAN')
        mod.object = cutter
        mod.operation = 'DIFFERENCE'
        mod.solver = 'EXACT'
        mod_names.append(mod_name)
        log_to_file(f"[STEP Exporter] _boolean_difference: created {mod_name} (cutter at z={cutter.location.z:.4f}, r={cutter.dimensions.x/2:.4f}, h={cutter.dimensions.z:.4f})")
    
    # 一次性通过 depsgraph 评估所有 modifier
    depsgraph = bpy.context.evaluated_depsgraph_get()
    obj.update_tag()
    bpy.context.view_layer.update()
    eval_obj = obj.evaluated_get(depsgraph)
    new_mesh = bpy.data.meshes.new_from_object(eval_obj)
    old_mesh = obj.data
    obj.data = new_mesh
    obj.modifiers.clear()
    if old_mesh and old_mesh.users == 0:
        bpy.data.meshes.remove(old_mesh)
    log_to_file(f"[STEP Exporter] _boolean_difference: all {len(mod_names)} modifiers applied, target verts={len(obj.data.vertices)}")
    
    # 删除切割体（不再需要）
    for cutter in cutters:
        mesh = cutter.data
        bpy.data.objects.remove(cutter, do_unlink=True)
        if mesh and mesh.users == 0:
            bpy.data.meshes.remove(mesh)
    
    # 存储孔参数到自定义属性，供检测阶段直接使用（避免 mesh z-level 分析误差）
    if props.hole_type in ('top', 'bottom', 'both'):
        obj['hole_depth'] = hole_d
        obj['hole_position'] = props.hole_type
        log_to_file(f"[STEP Exporter] _create_holes: stored hole_depth={hole_d:.4f} hole_position={props.hole_type} on object")
    
    # 孔口圆倒角
    if props.hole_fillet_radius > 0 and cutters:
        _apply_hole_fillet(obj, props, S)


def _boolean_difference(target, cutter):
    """对 target 做布尔减 cutter，立即应用"""
    mod_name = "Bool_Hole_" + cutter.name
    mod = target.modifiers.new(name=mod_name, type='BOOLEAN')
    mod.object = cutter
    mod.operation = 'DIFFERENCE'
    mod.solver = 'EXACT'  # 使用精确求解器
    
    # 设为活跃对象，确保在 OBJECT 模式
    bpy.context.view_layer.objects.active = target
    target.select_set(True)
    bpy.ops.object.mode_set(mode='OBJECT')
    
    log_to_file(f"[STEP Exporter] _boolean_difference: applying {mod_name} (cutter at z={cutter.location.z:.4f}, r={cutter.dimensions.x/2:.4f}, h={cutter.dimensions.z:.4f})")
    bpy.ops.object.modifier_apply(modifier=mod_name)
    
    log_to_file(f"[STEP Exporter] _boolean_difference: {mod_name} done, target verts={len(target.data.vertices)}")


def _apply_hole_fillet(obj, props, S):
    """对孔口边缘做圆倒角"""
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.mode_set(mode='EDIT')
    
    bm = bmesh.from_edit_mesh(obj.data)
    bm.edges.ensure_lookup_table()
    
    H = props.height * S
    top_z = H / 2.0
    btm_z = -H / 2.0
    
    # 清除所有选择
    for e in bm.edges:
        e.select = False
    for v in bm.verts:
        v.select = False
    
    for edge in bm.edges:
        vz0 = edge.verts[0].co.z
        vz1 = edge.verts[1].co.z
        # 孔口边缘：靠近顶部或底面但不是外圆柱边缘的边
        if props.hole_type in ('top', 'through', 'both'):
            dz_top_min = min(abs(vz0 - top_z), abs(vz1 - top_z))
            # 顶部孔口边：在顶面附近且半径小于外半径
            if dz_top_min < 0.01:
                dist0 = math.sqrt(edge.verts[0].co.x**2 + edge.verts[0].co.y**2)
                dist1 = math.sqrt(edge.verts[1].co.x**2 + edge.verts[1].co.y**2)
                outer_r = (props.radius if props.cylinder_type == 'standard' else props.top_radius) * S
                if dist0 < outer_r * 0.9 and dist1 < outer_r * 0.9:
                    edge.select = True
        
        if props.hole_type in ('bottom', 'through', 'both'):
            dz_btm_min = min(abs(vz0 - btm_z), abs(vz1 - btm_z))
            if dz_btm_min < 0.01:
                dist0 = math.sqrt(edge.verts[0].co.x**2 + edge.verts[0].co.y**2)
                dist1 = math.sqrt(edge.verts[1].co.x**2 + edge.verts[1].co.y**2)
                outer_r = (props.radius if props.cylinder_type == 'standard' else props.bottom_radius) * S
                if dist0 < outer_r * 0.9 and dist1 < outer_r * 0.9:
                    edge.select = True
    
    sel_edges = [e for e in bm.edges if e.select]
    if sel_edges and props.hole_fillet_radius > 0:
        bmesh.ops.bevel(
            bm,
            geom=sel_edges,
            offset=props.hole_fillet_radius * S,
            offset_type='OFFSET',
            segments=8,
            profile=0.5,
            affect='EDGES',
        )
    
    bmesh.update_edit_mesh(obj.data)
    bpy.ops.object.mode_set(mode='OBJECT')


# ====================== 参数化圆柱面板 ======================

class STEP_EXPORTER_PT_cylinder_panel(Panel):
    """参数化圆柱生成面板"""
    bl_label = "Parametric Cylinder"
    bl_idname = "STEP_EXPORTER_PT_cylinder_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "STEP Export"
    bl_parent_id = "STEP_EXPORTER_PT_main_panel"
    bl_options = {'DEFAULT_CLOSED'}
    
    def draw(self, context):
        layout = self.layout
        layout.operator("step_exporter.create_parametric_cylinder", text="Generate Cylinder", icon='MESH_CYLINDER')


# ====================== 注册与注销 ======================

classes = [
    STEP_EXPORTER_OT_export_enhanced,
    STEP_EXPORTER_PT_main_panel,
    STEP_EXPORTER_OT_create_top_shell,
    STEP_EXPORTER_OT_create_bottom_shell,
    STEP_EXPORTER_OT_create_cylinder,
    STEP_EXPORTER_OT_create_parametric_cylinder,
    STEP_EXPORTER_PT_cylinder_panel,
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