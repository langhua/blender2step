"""Mesh and curve data extraction for STEP Exporter."""
import sys, math
from .utils import log_to_file
from . import _globals as _g

def _get_mesh_data_enhanced(obj, context, scale, apply_modifiers=True):
    """获取网格数据（增强版，包含更多检查和信息）"""
    if obj.type != 'MESH':
        return None
    
    mesh = obj.data
    
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
    
    # 如果所有顶点都为零，打印严重警告
    if zero_vertex_count == len(vertices) and len(vertices) > 0:
        log_to_file(f"[Python WARNING] ALL vertices have zero world coordinates! Check object transform and mesh data.")
    
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

