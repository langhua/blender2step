"""Operators and panels for STEP Exporter."""
import sys, os, math, time
import bpy, bmesh
from mathutils import Vector
from bpy.types import Operator, Panel
from bpy_extras.io_utils import ExportHelper
from bpy.props import StringProperty, FloatProperty, IntProperty, BoolProperty, EnumProperty
from ..core.utils import log_to_file, _merge_step_files, _merge_log_files
from ..export.progress_report import start_progress, update_progress, end_progress, set_operator, clear_operator
from ..analysis.shape_analysis import _analyze_cylinder_from_mesh, _analyze_bottom_shell_from_mesh, _analyze_top_shell_from_mesh
from ..export.export_parametric import _export_worker_timer, _parametric_export_staged
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
                next_tick = _parametric_export_staged()
                if next_tick is None:
                    # 导出完成
                    _g._export_complete = True
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
        
        # 将导出参数存储到全局变量
        
        # 确定要导出的对象列表
        if self.use_selected and context.selected_objects:
            _g._export_objects = [obj for obj in context.selected_objects if obj.type in ('MESH', 'CURVE')]
        else:
            _g._export_objects = [obj for obj in context.scene.objects if obj.type in ('MESH', 'CURVE')]
        
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
        
        for obj in _g._export_objects:
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
        log_to_file(f"[STEP Exporter] Total objects: {len(_g._export_objects)}, bottom_shells: {len(bottom_shells)}, top_shells: {len(top_shells)}, cylinders: {len(cylinder_objects)}, regular: {len(regular_export_objects)}")
        
        if bottom_shells or top_shells or cylinder_objects:
            log_to_file(f"[STEP Exporter] Found {total_parametric} parametric object(s) (+ {len(regular_export_objects)} regular), using parametric export")
            update_progress(10, "检测到参数化对象，正在导出...", context)

            # 日志文件已在 execute() 开头打开，此处确保可用即可

            _g._bottom_shell_export_data = {
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

            _g._export_complete = False
            _g._export_success = False
            
            # 重置分阶段导出状态
            _g._parametric_export_stage = 0
            _g._parametric_export_idx = 0
            _g._parametric_temp_files = []
            _g._parametric_progress_val = 0.0
            
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
                    _g._export_success = False
                    _g._export_complete = True
                
                # 清理
                end_progress(context)
                clear_operator()
                if _g._export_log_file and not _g._export_log_file.closed:
                    _g._export_log_file.close()
                    _g._export_log_file = None
                try:
                    _merge_log_files(os.path.dirname(self.filepath), self.filepath)
                except:
                    pass
                
                log_to_file(f"[STEP Exporter] Background export done, success={_g._export_success}")
                self.report({'INFO' if _g._export_success else 'ERROR'}, "STEP 导出完成" if _g._export_success else "STEP 导出失败")
                return {'FINISHED'}
            
            # UI模式：注册事件定时器用于modal进度更新
            wm = context.window_manager
            self._timer = wm.event_timer_add(0.1, window=context.window)
            wm.modal_handler_add(self)
            log_to_file(f"[STEP Exporter] Modal handler and event timer registered")

            return {'RUNNING_MODAL'}
        
        _g._export_params = {
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
        _g._export_complete = False
        _g._export_success = False
        _g._export_stage = 0
        _g._export_objects_data = []
        _g._export_current_index = 0

        # 注册事件定时器用于modal进度更新
        wm = context.window_manager
        self._timer = wm.event_timer_add(0.2, window=context.window)
        wm.modal_handler_add(self)
        log_to_file(f"[STEP Exporter] Modal handler and event timer registered (regular path)")

        log_to_file(f"[STEP Exporter] === Registering app timer ===")
        log_to_file(f"[STEP Exporter] Objects to export: {len(_g._export_objects)}")

        # 包装 _export_worker_timer，完成后设置完成标志
        def _async_regular_worker():
            try:
                result = _export_worker_timer()
                if result is None:
                    # timer 停止，导出完成（可能成功也可能失败，由内部决定）
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
        
        if _g.CPP_MODULE_LOADED and _g.step_exporter:
            try:
                version = _g.step_exporter.get_version()
                box.label(text=f"✓ Module v{version} loaded", icon='CHECKMARK')
                oc_ver = _g.step_exporter.get_occt_version() if hasattr(_g.step_exporter, 'get_occt_version') else "7.7.2"
                box.label(text=f"✓ OpenCASCADE {oc_ver} ready", icon='CHECKMARK')
            except:
                box.label(text="✓ C++ module loaded", icon='CHECKMARK')
        else:
            box.label(text="✗ C++ extension not loaded", icon='ERROR')
            box.label(text="Check system console", icon='ERROR')
        
        # 快速导出按钮
        layout.separator()
        if _g.CPP_MODULE_LOADED:
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

def _on_hole_param_change(self, context=None):
    """当孔位置或锥形选项改变时，确保开口半径 >= 孔底半径"""
    if not self.hole_is_tapered:
        return
    # 开口半径应 >= 孔底半径，若用户设反了则自动交换
    if self.hole_opening_radius < self.hole_end_radius:
        self.hole_opening_radius, self.hole_end_radius = self.hole_end_radius, self.hole_opening_radius

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
        update=lambda self, ctx: _on_hole_param_change(self),
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
        update=lambda self, ctx: _on_hole_param_change(self),
    )
    hole_opening_radius: FloatProperty(
        name="Hole Opening R", default=6.0, min=0.1, max=100.0,
        description="Radius at hole opening (cylinder face)",
    )
    hole_end_radius: FloatProperty(
        name="Hole End R", default=4.0, min=0.1, max=100.0,
        description="Radius at hole bottom/end (inside cylinder)",
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
                box.prop(self, 'hole_opening_radius')
                box.prop(self, 'hole_end_radius')
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
        # 存储倒角/圆角参数及原始半径，供检测阶段直接使用（避免 mesh 分析受通孔干扰）
        obj['chamfer_type'] = props.chamfer_type
        obj['chamfer_size'] = props.chamfer_size
        obj['fillet_radius_edge'] = props.fillet_radius
        obj['cylinder_original_radius'] = props.radius
    
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
        hr_opening = props.hole_opening_radius * S
        hr_end = props.hole_end_radius * S
    else:
        hr_opening = props.hole_radius * S
        hr_end = props.hole_radius * S
    
    cutters = []
    
    def make_hole_cutter(cut_name, z_bottom, z_top, r_bottom, r_top):
        """创建锥形/直孔切割体"""
        cutter_height = z_top - z_bottom
        cutter_z = (z_top + z_bottom) / 2.0
        
        # 直孔用原生圆柱体
        if abs(r_bottom - r_top) < 0.0001:
            bpy.ops.mesh.primitive_cylinder_add(
                vertices=64, radius=r_bottom, depth=cutter_height,
                location=(0, 0, cutter_z)
            )
        else:
            # 锥形孔用原生锥体
            bpy.ops.mesh.primitive_cone_add(
                vertices=64, radius1=r_bottom, radius2=r_top, depth=cutter_height,
                location=(0, 0, cutter_z)
            )
        obj_c = bpy.context.active_object
        obj_c.name = cut_name
        obj_c.hide_set(True)
        obj_c.hide_render = True
        return obj_c
    
    hh = H
    ext = max(hr_end, hole_d * 0.5) if props.hole_type != 'through' else max(hr_end, H * 0.5)
    
    log_to_file(f"[STEP Exporter] _create_holes: H={H:.4f} hole_d={hole_d:.4f} opening_r={hr_opening:.4f} end_r={hr_end:.4f} ext={ext:.4f} type={props.hole_type}")
    
    if props.hole_type == 'through':
        cutters.append(make_hole_cutter(
            "HoleCutter_Through",
            -hh / 2 - ext, hh / 2 + ext, hr_end, hr_opening
        ))
    elif props.hole_type == 'top':
        # 顶部孔：开口在顶面(z=hh/2)，孔底在(z=hh/2-hole_d)
        cutters.append(make_hole_cutter(
            "HoleCutter_Top",
            hh / 2 - hole_d, hh / 2 + ext, hr_end, hr_opening
        ))
    elif props.hole_type == 'bottom':
        # 底部孔：开口在底面(z=-hh/2)，孔底在(z=-hh/2+hole_d)
        cutters.append(make_hole_cutter(
            "HoleCutter_Bottom",
            -hh / 2 - ext, -hh / 2 + hole_d, hr_opening, hr_end
        ))
    elif props.hole_type == 'both':
        # 顶部孔：开口在顶面
        cutters.append(make_hole_cutter(
            "HoleCutter_Top",
            hh / 2 - hole_d, hh / 2 + ext, hr_end, hr_opening
        ))
        # 底部孔：开口在底面
        cutters.append(make_hole_cutter(
            "HoleCutter_Bottom",
            -hh / 2 - ext, -hh / 2 + hole_d, hr_opening, hr_end
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
    if props.hole_type in ('top', 'bottom', 'both', 'through'):
        if props.hole_type != 'through':
            obj['hole_depth'] = hole_d
            obj['hole_position'] = props.hole_type
        obj['hole_radius'] = hr_opening  # 开口半径
        obj['hole_opening_radius'] = hr_opening
        obj['hole_end_radius'] = hr_end
        obj['hole_is_tapered'] = props.hole_is_tapered
        obj['hole_type'] = props.hole_type
        log_to_file(f"[STEP Exporter] _create_holes: stored type={props.hole_type} opening_r={hr_opening:.4f} end_r={hr_end:.4f} tapered={props.hole_is_tapered}")
    
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

