"""STEP export operator."""
import sys, os, math, time
import bpy
from bpy.types import Operator
from bpy_extras.io_utils import ExportHelper
from bpy.props import StringProperty, FloatProperty, IntProperty, BoolProperty, EnumProperty
from ..core.utils import log_to_file, _merge_step_files, _merge_log_files
from ..export.progress_report import start_progress, update_progress, end_progress, set_operator, clear_operator
from ..analysis import _analyze_cylinder_from_mesh, _analyze_bottom_shell_from_mesh, _analyze_top_shell_from_mesh
from ..export import _export_worker_timer, _parametric_export_staged
from ..core import _globals as _g

"""Operators and panels for STEP Exporter."""
import sys, os, math, time
import bpy, bmesh
from mathutils import Vector
from bpy.types import Operator, Panel
from bpy_extras.io_utils import ExportHelper
from bpy.props import StringProperty, FloatProperty, IntProperty, BoolProperty, EnumProperty
from ..core.utils import log_to_file, _merge_step_files, _merge_log_files
from ..export.progress_report import start_progress, update_progress, end_progress, set_operator, clear_operator
from ..analysis import _analyze_cylinder_from_mesh, _analyze_bottom_shell_from_mesh, _analyze_top_shell_from_mesh
from ..export import _export_worker_timer, _parametric_export_staged
from ..core import _globals as _g

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
        if _g.CPP_MODULE_LOADED and _g.step_exporter:
            try:
                version = _g.step_exporter.get_version()
                box.label(text=f"C++ module v{version} loaded", icon='CHECKMARK')
            except:
                box.label(text="C++ module loaded", icon='CHECKMARK')
        else:
            box.label(text="C++ extension not loaded", icon='ERROR')
            if _g.MODULE_LOAD_ERROR:
                box.label(text=f"Error: {_g.MODULE_LOAD_ERROR[:50]}...", icon='ERROR')
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
        
        if event.type == 'TIMER':
            if _g._export_complete:
                log_to_file(f"[STEP Exporter] Modal: export complete, success={_g._export_success}, cleaning up...")
                
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
                if _g._export_log_file and not _g._export_log_file.closed:
                    _g._export_log_file.close()
                    _g._export_log_file = None
                
                # 合并日志文件（参数化路径）
                try:
                    _merge_log_files(os.path.dirname(self.filepath), self.filepath)
                except:
                    pass
                
                if _g._export_success:
                    self.report({'INFO'}, "STEP 导出完成")
                else:
                    self.report({'ERROR'}, "STEP 导出失败，请查看日志")
                
                return {'FINISHED'}
            
            # 在modal handler中执行分阶段导出，确保UI能刷新进度条
            try:
                if _g._bottom_shell_export_data:
                    next_tick = _parametric_export_staged()
                    if next_tick is None:
                        _g._export_complete = True
                        return {'PASS_THROUGH'}
                else:
                    # Regular export path: let app timer handle it
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
                _g._export_success = False
                _g._export_complete = True
                return {'PASS_THROUGH'}
        
        return {'PASS_THROUGH'}

    def execute(self, context):
        if not _g.CPP_MODULE_LOADED or not _g.step_exporter:
            self.report({'ERROR'}, "C++ extension module '_step_exporter' not loaded. Check console for details.")
            return {'CANCELLED'}
        
        # 尽早打开日志文件，确保所有 [STEP Exporter] 日志都写入 .step.log
        if _g._export_log_file is None or _g._export_log_file.closed:
            try:
                log_path = self.filepath + ".log"
                _g._export_log_file = open(log_path, 'w', encoding='utf-8')
                # 将之前缓冲的消息写入日志文件
                if _g._log_buffer:
                    for buf_msg in _g._log_buffer:
                        _g._export_log_file.write(buf_msg)
                    _g._export_log_file.flush()
                    _g._log_buffer = []
            except:
                pass
        
        # 启动进度条显示（使用 built-in wm.progress API）
        set_operator(self)
        log_to_file(f"[STEP Exporter] === Calling start_progress ===")
        start_progress(context)
        update_progress(0, "正在分析物体...", context)  # 立即显示进度，避免空白等待
        
        # 注册模态处理器，让 UI 可以立即刷新
        wm = context.window_manager
        self._timer = wm.event_timer_add(0.1, window=context.window)
        wm.modal_handler_add(self)
        
        # 存储基本参数供异步回调使用
        _g._export_setup_params = {
            'use_selected': self.use_selected,
            'unit': self.unit,
            'step_schema': self.step_schema,
            'enable_logging': self.enable_logging,
            'fix_geometry': self.fix_geometry,
            'create_solid': self.create_solid,
            'advanced_brep': self.advanced_brep,
            'sew_tolerance': self.sew_tolerance,
            'filepath': self.filepath,
            'context': context,
        }
        
        # 用 app timer 延迟执行物体分析，让 UI 先刷新显示进度条
        def _deferred_analyze_and_export():
            try:
                _execute_analysis_and_export(self, _g._export_setup_params)
            except Exception as e:
                log_to_file(f"[STEP Exporter] Deferred analysis error: {e}")
                import traceback
                log_to_file(traceback.format_exc())
                _g._export_success = False
                _g._export_complete = True
            return None  # 一次性 timer
        
        bpy.app.timers.register(_deferred_analyze_and_export, first_interval=0.01)
        log_to_file(f"[STEP Exporter] Modal handler registered, analysis deferred to timer")
        
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

# ====================== 延迟分析 + 导出 ======================

def _execute_analysis_and_export(operator, params):
    """在 app timer 中执行物体分析，然后启动参数化或常规导出。
    延迟执行确保 UI 先刷新显示进度条，避免用户看到空白等待。
    """
    context = params['context']
    use_selected = params['use_selected']
    unit = params['unit']
    step_schema = params['step_schema']
    enable_logging = params['enable_logging']
    fix_geometry = params['fix_geometry']
    create_solid = params['create_solid']
    advanced_brep = params['advanced_brep']
    sew_tolerance = params['sew_tolerance']
    filepath = params['filepath']
    
    import bpy
    from ..core import _globals as _g
    from ..core.utils import log_to_file, _merge_log_files
    from ..analysis import _analyze_cylinder_from_mesh, _analyze_bottom_shell_from_mesh, _analyze_top_shell_from_mesh
    from ..export import _export_worker_timer, _parametric_export_staged
    from ..export.progress_report import start_progress, update_progress, end_progress, set_operator, clear_operator
    
    # 确定要导出的对象列表
    if use_selected and context.selected_objects:
        _g._export_objects = [obj for obj in context.selected_objects if obj.type in ('MESH', 'CURVE')]
    else:
        _g._export_objects = [obj for obj in context.scene.objects if obj.type in ('MESH', 'CURVE')]
    
    # 根据选择的单位确定缩放值
    if unit == 'mm':
        scale = 1000.0
    else:
        scale = 1.0
    
    step_unit = 'MILLIMETER' if unit == 'mm' else 'METER'
    
    # 检测底壳和圆柱对象，使用参数化导出
    bottom_shells = []
    top_shells = []
    cylinder_objects = []
    regular_export_objects = []
    
    total_objects = len(_g._export_objects)
    for idx, obj in enumerate(_g._export_objects):
        if obj.type == 'MESH':
            log_to_file(f"[STEP Exporter] Checking: {obj.name}")
            
            # 如果对象标记了需要使用网格导出
            if obj.get("step_use_mesh", False):
                log_to_file(f"[STEP Exporter]   -> marked for mesh export (has holes/cuts)")
                regular_export_objects.append(obj)
                continue
            
            # 先检测圆柱/圆锥
            cyl_params = _analyze_cylinder_from_mesh(obj, context, scale)
            if cyl_params:
                cylinder_objects.append(cyl_params)
                log_to_file(f"[STEP Exporter] Found {cyl_params['obj_type']}: {obj.name}")
                continue
            
            # 再检测底壳
            shell_params = _analyze_bottom_shell_from_mesh(obj, context, scale)
            if shell_params:
                bottom_shells.append(shell_params)
                log_to_file(f"[STEP Exporter] Found bottom shell: {obj.name}")
                continue

            # 最后检测顶壳
            top_shell_params = _analyze_top_shell_from_mesh(obj, context, scale)
            if top_shell_params:
                top_shells.append(top_shell_params)
                log_to_file(f"[STEP Exporter] Found top shell: {obj.name}")
                continue
            
            log_to_file(f"[STEP Exporter]   -> NOT a parametric object")
            regular_export_objects.append(obj)
        elif obj.type == 'CURVE':
            regular_export_objects.append(obj)
        
        # 每分析约 10% 物体更新一次进度 (1% → 8%)
        if idx % max(1, total_objects // 10) == 0:
            pct = int(1 + 7 * idx / max(1, total_objects))
            update_progress(pct, f"分析物体 {idx+1}/{total_objects}...", context)
    
    total_parametric = len(bottom_shells) + len(top_shells) + len(cylinder_objects)
    log_to_file(f"[STEP Exporter] Total objects: {len(_g._export_objects)}, bottom_shells: {len(bottom_shells)}, top_shells: {len(top_shells)}, cylinders: {len(cylinder_objects)}, regular: {len(regular_export_objects)}")
    
    if bottom_shells or top_shells or cylinder_objects:
        log_to_file(f"[STEP Exporter] Found {total_parametric} parametric object(s), using parametric export")
        update_progress(10, f"分析完成，开始导出 {total_parametric} 个参数化物体...", context)

        _g._bottom_shell_export_data = {
            'filepath': filepath,
            'shells': bottom_shells,
            'top_shells': top_shells,
            'cylinders': cylinder_objects,
            'regular_objects': regular_export_objects,
            'step_schema': step_schema,
            'step_unit': step_unit,
            'enable_logging': enable_logging,
            'fix_geometry': fix_geometry,
            'create_solid': create_solid,
            'advanced_brep': advanced_brep,
            'sew_tolerance': sew_tolerance,
            'context': context,
        }

        _g._export_complete = False
        _g._export_success = False
        
        # 重置分阶段导出状态
        _g._parametric_export_stage = 0
        _g._parametric_export_idx = 0
        _g._parametric_temp_files = []
        _g._parametric_progress_val = 0.0
        
        # 后台模式：同步运行
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
                _g._export_success = False
                _g._export_complete = True
            
            end_progress(context)
            clear_operator()
            log_to_file(f"[STEP Exporter] Background export done, success={_g._export_success}")
            return
        
        # UI模式：modal handler 已在 execute() 中注册，直接开始分阶段导出
        log_to_file(f"[STEP Exporter] Staged export will run in modal handler")
        # 不需要额外操作——modal handler 中的 TIMER 事件会自动调用 _parametric_export_staged()
    else:
        # 常规导出路径
        log_to_file(f"[STEP Exporter] No parametric objects, using regular export")
        
        _g._export_params = {
            'filepath': filepath,
            'use_selected': use_selected,
            'unit': unit,
            'fix_geometry': fix_geometry,
            'create_solid': create_solid,
            'advanced_brep': advanced_brep,
            'step_schema': step_schema,
            'sew_tolerance': sew_tolerance,
            'enable_logging': enable_logging,
            'context': context,
            'scale': scale,
            'apply_modifiers': True,
        }
        
        _g._export_complete = False
        _g._export_success = False
        _g._export_stage = 0
        _g._export_objects_data = []
        _g._export_current_index = 0
        
        def _async_regular_worker():
            try:
                result = _export_worker_timer()
                if result is None:
                    _g._export_success = True
                    _g._export_complete = True
                    return None
                return result
            except Exception as e:
                log_to_file(f"[STEP Exporter] Async regular export error: {e}")
                import traceback
                log_to_file(traceback.format_exc())
                _g._export_success = False
                _g._export_complete = True
                return None
        
        bpy.app.timers.register(_async_regular_worker, first_interval=0.1)
        log_to_file(f"[STEP Exporter] App timer registered for regular export")

# ====================== 菜单函数 ======================

