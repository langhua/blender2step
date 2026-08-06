"""Parametric cylinder generation."""
import sys, os, math
import bpy, bmesh
from mathutils import Vector
from bpy.types import Operator
from bpy.props import StringProperty, FloatProperty, IntProperty, BoolProperty, EnumProperty
from ..core.utils import log_to_file
from ..core import _globals as _g
from ..core.i18n import _t

def _on_hole_param_change(self, context=None):
    """当孔位置或锥形选项改变时，确保开口半径 >= 孔底半径"""
    if not self.hole_is_tapered:
        return
    # 开口半径应 >= 孔底半径，若用户设反了则自动交换
    if self.hole_opening_radius < self.hole_end_radius:
        self.hole_opening_radius, self.hole_end_radius = self.hole_end_radius, self.hole_opening_radius

def _swap_radii_callback(self):
    """Swap top and bottom radius, then reset the toggle."""
    self.top_radius, self.bottom_radius = self.bottom_radius, self.top_radius
    self['swap_radii'] = False


def _load_params_from_object(props, obj):
    """把选中参数化对象的 param_* 属性回填到操作符属性（面板）。

    返回 True 表示成功（对象是带 param_cylinder_type 的 mesh）。"""
    if obj is None or obj.type != 'MESH':
        return False
    if obj.get('param_cylinder_type') is None:
        return False
    props.cylinder_type = obj['param_cylinder_type']
    props.height = obj.get('param_height', props.height)
    if props.cylinder_type == 'standard':
        props.radius = obj.get('param_radius', props.radius)
    else:
        props.bottom_radius = obj.get('param_bottom_radius', props.bottom_radius)
        props.top_radius = obj.get('param_top_radius', props.top_radius)
    props.chamfer_type = obj.get('param_chamfer_type', 'none')
    props.chamfer_size = obj.get('param_chamfer_size', 0.0)
    props.fillet_radius = obj.get('param_fillet_radius', 0.0)
    props.hole_type = obj.get('param_hole_type', 'none')
    props.hole_radius = obj.get('param_hole_radius', 0.0)
    props.hole_depth = obj.get('param_hole_depth_pct', 50.0)
    props.hole_is_tapered = obj.get('param_hole_is_tapered', False)
    props.hole_opening_radius = obj.get('param_hole_opening_radius', 0.0)
    props.hole_end_radius = obj.get('param_hole_end_radius', 0.0)
    props.hole_fillet_radius = obj.get('param_hole_fillet_radius', 0.0)
    props.stepped_large_radius = obj.get('param_stepped_large_radius', 0.0)
    props.stepped_large_height = obj.get('param_stepped_large_height_pct', 80.0)
    props.stepped_small_radius = obj.get('param_stepped_small_radius', 0.0)
    props.tapered_step_top_radius = obj.get('param_tapered_step_top_radius', 0.0)
    props.tapered_step_bottom_radius = obj.get('param_tapered_step_bottom_radius', 0.0)
    props.groove_enabled = obj.get('param_groove_enabled', False)
    props.groove_angle = math.radians(obj.get('param_groove_angle_deg', 45.0))
    props.groove_top_width = obj.get('param_groove_top_width', 0.0)
    props.groove_depth_pct = obj.get('param_groove_depth_pct', 20.0)
    props.groove_cone_depth_mult = obj.get('param_groove_cone_depth_mult', 1.0)
    return True


class STEP_EXPORTER_OT_create_parametric_cylinder(Operator):
    """创建参数化圆柱体（标准/锥形，带倒角/开孔）"""
    bl_idname = "step_exporter.create_parametric_cylinder"
    bl_label = _t("Parametric Cylinder")
    bl_options = {'REGISTER', 'UNDO'}
    
    # === 圆柱类型 ===
    cylinder_type: EnumProperty(
        name=_t("Type"),
        description="Cylinder type",
        items=[
            ('standard', "Standard", "Standard cylinder"),
            ('tapered', "Tapered", "Tapered cylinder (truncated cone)"),
        ],
        default='standard',
    )
    # 标准圆柱
    radius: FloatProperty(
        name=_t("Radius"), default=15.0, min=0.5, max=500.0,
    )
    # 锥形圆柱
    top_radius: FloatProperty(
        name=_t("Top R"), default=10.0, min=0.1, max=500.0,
    )
    bottom_radius: FloatProperty(
        name=_t("Bottom R"), default=20.0, min=0.1, max=500.0,
    )
    swap_radii: BoolProperty(
        name=_t("Swap"), default=False,
        description=_t("Swap top and bottom radius"),
        update=lambda self, ctx: _swap_radii_callback(self),
    )
    # 通用
    height: FloatProperty(
        name=_t("Height"), default=40.0, min=0.5, max=500.0,
    )
    segments: IntProperty(
        name=_t("Segments"), default=64, min=8, max=256,
    )
    update_selected: BoolProperty(
        name=_t("Write to Selected"),
        default=False,
        description=_t("Write these parameters to the selected object's properties instead of creating a new one (for fixing existing parametric objects)"),
    )
    
    # === 单位 ===
    unit: EnumProperty(
        name=_t("Unit"),
        items=[
            ('mm', "mm", "Millimeters (input ×0.001 → meters)"),
            ('m', "m", "Meters (input ×1.0, no conversion)"),
        ],
        default='mm',
    )
    
    # === 倒角 ===
    chamfer_type: EnumProperty(
        name=_t("Chamfer"),
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
        name=_t("Chamfer Size"), default=2.0, min=0.1, max=50.0,
    )
    fillet_radius: FloatProperty(
        name=_t("Fillet R"), default=2.0, min=0.1, max=50.0,
    )
    
    # === 孔 ===
    hole_type: EnumProperty(
        name=_t("Hole"),
        items=[
            ('none', "None", "Solid cylinder, no hole"),
            ('top', "Top Blind", "Blind hole from top"),
            ('bottom', "Bottom Blind", "Blind hole from bottom"),
            ('both', "Both Blind", "Blind holes from top and bottom"),
            ('through', "Through", "Through hole (top to bottom)"),
            ('stepped', "Stepped", "Stepped through hole (large from top, small through bottom)"),
            ('tapered_stepped', "Tapered Stepped", "Tapered stepped hole (conical top + small cylinder bottom)"),
        ],
        default='none',
        update=lambda self, ctx: _on_hole_param_change(self),
    )
    hole_radius: FloatProperty(
        name=_t("Hole R"), default=5.0, min=0.1, max=100.0,
    )
    hole_depth: FloatProperty(
        name=_t("Hole Depth %"), default=50.0, min=1.0, max=100.0, subtype='PERCENTAGE',
        description="Hole depth as percentage of cylinder height (for blind holes)",
    )
    hole_is_tapered: BoolProperty(
        name=_t("Tapered Hole"), default=False,
        update=lambda self, ctx: _on_hole_param_change(self),
    )
    hole_opening_radius: FloatProperty(
        name=_t("Hole Opening R"), default=6.0, min=0.1, max=100.0,
        description="Radius at hole opening (cylinder face)",
    )
    hole_end_radius: FloatProperty(
        name=_t("Hole End R"), default=4.0, min=0.1, max=100.0,
        description="Radius at hole bottom/end (inside cylinder)",
    )
    hole_fillet_radius: FloatProperty(
        name=_t("Hole Fillet R"), default=0.5, min=0.0, max=50.0,
        description="Fillet radius for hole opening edge (0 = no fillet)",
    )
    # Stepped hole parameters
    stepped_large_radius: FloatProperty(
        name=_t("Large Hole R"), default=7.0, min=0.1, max=100.0,
        description="Radius of the large (top) section of the stepped hole",
    )
    stepped_large_height: FloatProperty(
        name=_t("Large Hole H %"), default=80, min=1, max=99, subtype='PERCENTAGE',
        description="Height of the large hole section as percentage of cylinder height",
    )
    stepped_small_radius: FloatProperty(
        name=_t("Small Hole R"), default=4.0, min=0.1, max=100.0,
        description="Radius of the small (bottom) section of the stepped hole",
    )
    # Tapered stepped hole parameters
    tapered_step_top_radius: FloatProperty(
        name=_t("Tapered Top R"), default=9.0, min=0.1, max=100.0,
        description="Radius of the tapered hole at the top surface (wider)",
    )
    tapered_step_bottom_radius: FloatProperty(
        name=_t("Tapered Step R"), default=7.0, min=0.1, max=100.0,
        description="Radius of the tapered hole at the step (narrower)",
    )
    # Groove parameters
    groove_enabled: BoolProperty(
        name=_t("External Groove"), default=False,
        description="Add a trapezoidal groove around the cylinder at mid-height",
    )
    groove_angle: FloatProperty(
        name=_t("Groove Angle"), default=math.radians(45.0),
        min=math.radians(30.0), max=math.radians(90.0),
        subtype='ANGLE',
        description="Angle of each side-wall measured from the groove floor (vertical)",
    )
    groove_top_width: FloatProperty(
        name=_t("Top Width"), default=2.0, min=0.1, max=100.0,
        description="Width of the groove at the groove floor (inner edge)",
    )
    groove_depth_pct: FloatProperty(
        name=_t("Depth % of R"), default=20.0, min=5.0, max=80.0, step=5.0,
        description="Groove depth as percentage of mid-radius",
    )
    groove_cone_depth_mult: FloatProperty(
        name=_t("Cone Depth ×"), default=1.5, min=1.0, max=3.0, step=0.1,
        description="Multiplier for groove depth on tapered cylinders (compensates slanted surface)",
    )
    
    def invoke(self, context, event):
        # 选中了参数化圆柱/锥柱 → 自动把对象的当前参数回填到面板，方便直接修改
        obj = context.active_object
        if obj is not None and obj.type == 'MESH' and obj.get('param_cylinder_type') is not None:
            _load_params_from_object(self, obj)
        return context.window_manager.invoke_props_dialog(self, width=320)

    def _get_auto_depth(self):
        """Return auto-scaled groove depth = pct% of mid-radius"""
        if self.cylinder_type == 'tapered':
            mid_r = (self.bottom_radius + self.top_radius) / 2.0
        else:
            mid_r = self.radius
        depth = round(mid_r * self.groove_depth_pct / 100.0, 1)
        if self.cylinder_type == 'tapered':
            depth *= self.groove_cone_depth_mult
        return round(depth, 1)
    
    def draw(self, context):
        layout = self.layout
        
        # Cylinder type
        box = layout.box()
        box.label(text=_t("Cylinder"), icon='MESH_CYLINDER')
        box.prop(self, 'unit')
        box.prop(self, 'cylinder_type')
        if self.cylinder_type == 'standard':
            box.prop(self, 'radius')
        else:
            row = box.row(align=True)
            row.prop(self, 'top_radius')
            row.prop(self, 'swap_radii', text='', icon='UV_SYNC_SELECT', toggle=False)
            box.prop(self, 'bottom_radius')
        box.prop(self, 'height')
        box.prop(self, 'segments')
        
        # Chamfer/Fillet
        box = layout.box()
        box.label(text=_t("Edge Treatment"), icon='MOD_BEVEL')
        box.prop(self, 'chamfer_type')
        if self.chamfer_type in ('chamfer', 'both'):
            box.prop(self, 'chamfer_size')
        if self.chamfer_type in ('fillet', 'both'):
            box.prop(self, 'fillet_radius')
        
        # Hole
        box = layout.box()
        box.label(text=_t("Hole"), icon='MESH_CYLINDER')
        box.prop(self, 'hole_type')
        if self.hole_type != 'none':
            if self.hole_type == 'stepped':
                # 普通台阶孔：大孔是等径直孔，只需 大孔半径 + 大孔高% + 小孔半径
                box.prop(self, 'stepped_large_radius')
                box.prop(self, 'stepped_large_height')
                box.prop(self, 'stepped_small_radius')
                box.prop(self, 'hole_fillet_radius')
            elif self.hole_type == 'tapered_stepped':
                # 锥形台阶孔：大孔段是锥形，由 锥形顶半径(顶面开口) + 锥形台阶半径(台阶处) 决定，
                # 大孔半径(stepped_large_radius) 不参与，隐藏避免误解
                box.prop(self, 'tapered_step_top_radius')
                box.prop(self, 'tapered_step_bottom_radius')
                box.prop(self, 'stepped_large_height')
                box.prop(self, 'stepped_small_radius')
                box.prop(self, 'hole_fillet_radius')
            else:
                box.prop(self, 'hole_is_tapered')
                if self.hole_is_tapered:
                    box.prop(self, 'hole_opening_radius')
                    box.prop(self, 'hole_end_radius')
                else:
                    box.prop(self, 'hole_radius')
                if self.hole_type in ('top', 'bottom', 'both'):
                    box.prop(self, 'hole_depth')
                box.prop(self, 'hole_fillet_radius')

        # Groove
        box = layout.box()
        box.label(text=_t("Groove"), icon='MOD_BOOLEAN')
        box.prop(self, 'groove_enabled')
        if self.groove_enabled:
            box.prop(self, 'groove_angle')
            box.prop(self, 'groove_top_width')
            box.prop(self, 'groove_depth_pct')
            if self.cylinder_type == 'tapered':
                box.prop(self, 'groove_cone_depth_mult')
            # Derived dimensions (read-only info)
            auto_depth = self._get_auto_depth()
            angle_rad = self.groove_angle
            derived_bot_w = self.groove_top_width + 2.0 * auto_depth * math.tan(angle_rad)
            info = layout.box()
            info.label(text=_t("Depth: {depth:.1f} mm  |  Bottom W: {bot_w:.1f} mm", depth=auto_depth, bot_w=derived_bot_w))
            info.label(text=_t("  (bot_w = top_w + 2×depth×tan(angle))"))
        
        # 写入选中对象（放在对话框最下方）
        layout.separator()
        layout.prop(self, 'update_selected')
    
    def execute(self, context):
        try:
            # 勾选"写入选中对象"时：不创建新对象，把参数写入当前选中的 mesh 对象
            if self.update_selected:
                obj = context.active_object
                if obj is None or obj.type != 'MESH':
                    self.report({'ERROR'}, _t("Select a mesh object to write params to"))
                    return {'CANCELLED'}
                _store_creation_params(obj, self)
                # 用 OCCT 重新生成预览网格（若该对象是参数化圆柱类）
                if obj.get('param_cylinder_type') is not None:
                    S = 0.001 if self.unit == 'mm' else 1.0
                    _apply_occt_preview_mesh(obj, self, S)
                self.report({'INFO'}, _t("Params written to {name}", name=obj.name))
                return {'FINISHED'}
            obj = _generate_parametric_cylinder(self)
            if obj:
                obj.select_set(True)
                context.view_layer.objects.active = obj
                self.report({'INFO'}, _t("Cylinder created: {name}", name=obj.name))
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
    
    # === 3. 创建外壁梯形槽（必须在孔之前，避免凹槽与孔几何交叉产生残留） ===
    if props.groove_enabled:
        _create_groove(obj, props, S)

    # === 4. 创建孔 ===
    if props.hole_type != 'none':
        _create_holes(obj, props, S)
    
    # 存储圆倒角参数到自定义属性，供导出时读取
    if props.hole_fillet_radius > 0:
        obj['hole_fillet_radius'] = props.hole_fillet_radius

    # === 5. 存储所有创建参数（mm），供导出时直接读取，避免依赖 mesh 检测 ===
    _store_creation_params(obj, props)

    # === 6. 用 OCCT 生成预览网格（与 STEP 导出完全一致），失败时保留 bmesh 预览 ===
    _apply_occt_preview_mesh(obj, props, S)
    
    return obj


def _apply_occt_preview_mesh(obj, props, S):
    """用 OCCT 参数化实体生成预览网格（与 STEP 导出几何完全一致）。

    取代 bmesh/布尔预览，消除 bmesh 与 OCCT 之间的几何漂移（倒角/圆角补偿、
    布尔残留等）。失败时静默保留原 bmesh 预览。
    """
    import math as _m
    try:
        from ..core import _globals as _g
        cpp = _g.step_exporter
        if cpp is None:
            import _step_exporter as cpp
        if not hasattr(cpp, 'generate_cylinder_mesh'):
            log_to_file("[STEP Exporter] OCCT preview unavailable (old pyd), keeping bmesh preview")
            return
        result = cpp.generate_cylinder_mesh(
            props.cylinder_type, props.height,
            props.radius, props.bottom_radius, props.top_radius,
            props.chamfer_type, props.chamfer_size, props.fillet_radius,
            props.hole_type, props.hole_radius, props.hole_depth,
            1 if props.hole_is_tapered else 0,
            props.hole_opening_radius, props.hole_end_radius, props.hole_fillet_radius,
            props.stepped_large_radius, props.stepped_large_height, props.stepped_small_radius,
            props.tapered_step_top_radius, props.tapered_step_bottom_radius,
            1 if props.groove_enabled else 0,
            _m.degrees(props.groove_angle), props.groove_top_width,
            props.groove_depth_pct, props.groove_cone_depth_mult,
            0.02)  # deflection (mm) — 光滑预览
        if result is None:
            log_to_file("[STEP Exporter] OCCT preview returned None, keeping bmesh preview")
            return
        verts = result['vertices']
        tris = result['triangles']
        if len(verts) < 4 or len(tris) < 4:
            log_to_file("[STEP Exporter] OCCT preview empty mesh, keeping bmesh preview")
            return
        import bmesh as _bm
        bm = _bm.new()
        bm_verts = [bm.verts.new((v[0] * S, v[1] * S, v[2] * S)) for v in verts]
        bm.verts.ensure_lookup_table()
        for tri in tris:
            try:
                bm.faces.new([bm_verts[tri[0]], bm_verts[tri[1]], bm_verts[tri[2]]])
            except ValueError:
                pass
        bm.normal_update()
        bm.to_mesh(obj.data)
        bm.free()
        # 自动平滑：曲面（锥面/圆柱面/孔壁）平滑，棱边（底部/台阶等直角边）保持锐利
        _apply_preview_shading(obj)
        log_to_file(f"[STEP Exporter] OCCT preview mesh applied: {len(verts)} verts, {len(tris)} tris")
    except Exception as e:
        log_to_file(f"[STEP Exporter] OCCT preview failed, keeping bmesh preview: {e}")


def _apply_preview_shading(obj, threshold_deg=30.0):
    """预览着色：曲面平滑、大角度棱边锐利（使底部/台阶边缘在实体模式下清晰）。"""
    import math as _m
    import bmesh as _bms
    data = obj.data
    for f in data.polygons:
        f.use_smooth = True
    try:
        data.use_auto_smooth = True
        data.auto_smooth_angle = _m.radians(threshold_deg)
    except Exception:
        pass
    thr = _m.radians(threshold_deg)
    bm = _bms.new()
    bm.from_mesh(data)
    bm.edges.ensure_lookup_table()
    bm.faces.ensure_lookup_table()
    for e in bm.edges:
        if len(e.link_faces) != 2:
            continue
        n0 = e.link_faces[0].normal
        n1 = e.link_faces[1].normal
        try:
            ang = n0.angle(n1)
        except ValueError:
            continue
        if ang > thr:
            e.smooth = False
    bm.to_mesh(data)
    bm.free()
    data.update()


def _store_creation_params(obj, props):
    """把创建时的所有参数写入对象自定义属性（param_*，mm/度），供导出直接读取。"""
    obj['param_cylinder_type'] = props.cylinder_type          # 'standard' | 'tapered'
    obj['param_height'] = props.height
    if props.cylinder_type == 'standard':
        obj['param_radius'] = props.radius
    else:
        obj['param_bottom_radius'] = props.bottom_radius
        obj['param_top_radius'] = props.top_radius
    obj['param_chamfer_type'] = props.chamfer_type
    obj['param_chamfer_size'] = props.chamfer_size
    obj['param_fillet_radius'] = props.fillet_radius
    obj['param_hole_type'] = props.hole_type
    obj['param_hole_radius'] = props.hole_radius
    obj['param_hole_depth_pct'] = props.hole_depth
    obj['param_hole_is_tapered'] = props.hole_is_tapered
    obj['param_hole_opening_radius'] = props.hole_opening_radius
    obj['param_hole_end_radius'] = props.hole_end_radius
    obj['param_hole_fillet_radius'] = props.hole_fillet_radius
    obj['param_stepped_large_radius'] = props.stepped_large_radius
    obj['param_stepped_large_height_pct'] = props.stepped_large_height
    obj['param_stepped_small_radius'] = props.stepped_small_radius
    obj['param_tapered_step_top_radius'] = props.tapered_step_top_radius
    obj['param_tapered_step_bottom_radius'] = props.tapered_step_bottom_radius
    obj['param_groove_enabled'] = props.groove_enabled
    if props.groove_enabled:
        obj['param_groove_angle_deg'] = math.degrees(props.groove_angle)
        obj['param_groove_top_width'] = props.groove_top_width
        obj['param_groove_depth_pct'] = props.groove_depth_pct
        if props.cylinder_type == 'tapered':
            obj['param_groove_cone_depth_mult'] = props.groove_cone_depth_mult


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
    # Blind holes: extend cutter past the hole bottom by only a TINY boolean margin.
    # (Was max(hr_end*2, H*0.05) ≈ 1.8mm → made 50% blind holes ~72% deep. C++ export
    #  already cuts to exactly hole_depth; keep the preview consistent.)
    if props.hole_type in ('top', 'bottom', 'both'):
        ext_bottom = max(hr_end * 0.005, H * 0.0005)
    else:
        ext_bottom = 0.0
    
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
            hh / 2 - hole_d - ext_bottom, hh / 2 + ext, hr_end, hr_opening
        ))
    elif props.hole_type == 'bottom':
        # 底部孔：开口在底面(z=-hh/2)，孔底在(z=-hh/2+hole_d)
        cutters.append(make_hole_cutter(
            "HoleCutter_Bottom",
            -hh / 2 - ext, -hh / 2 + hole_d + ext_bottom, hr_opening, hr_end
        ))
    elif props.hole_type == 'both':
        # 顶部孔：开口在顶面
        cutters.append(make_hole_cutter(
            "HoleCutter_Top",
            hh / 2 - hole_d - ext_bottom, hh / 2 + ext, hr_end, hr_opening
        ))
        # 底部孔：开口在底面
        cutters.append(make_hole_cutter(
            "HoleCutter_Bottom",
            -hh / 2 - ext, -hh / 2 + hole_d + ext_bottom, hr_opening, hr_end
        ))

    elif props.hole_type == 'stepped':
        # 台阶孔：大孔从顶部到台阶，小孔从台阶到底部
        large_r = props.stepped_large_radius * S
        large_h = props.stepped_large_height / 100.0 * H
        small_r = props.stepped_small_radius * S
        step_z = hh / 2 - large_h
        ext_ov = H * 0.05  # 5% of height — overlap for clean union at the step
        # 创建两个切割体。大孔段恰好结束于 step_z（不再向台阶下方延伸 ext_ov，
        # 否则大孔会超深 5%）；小孔段向上多延伸 ext_ov，重叠区被大孔半径覆盖。
        cutter_large = make_hole_cutter(
            "HoleCutter_StepLarge_Tmp",
            step_z, hh / 2 + ext_ov, large_r, large_r
        )
        cutter_small = make_hole_cutter(
            "HoleCutter_StepSmall_Tmp",
            -hh / 2 - ext_ov, step_z + ext_ov, small_r, small_r
        )
        # 先合并两个切割体（Boolean UNION），消除内部重叠面
        cutter_large.hide_set(False)
        cutter_small.hide_set(False)
        bpy.ops.object.select_all(action='DESELECT')
        cutter_large.select_set(True)
        bpy.context.view_layer.objects.active = cutter_large
        mod_union = cutter_large.modifiers.new(name="Bool_Union_Step", type='BOOLEAN')
        mod_union.object = cutter_small
        mod_union.operation = 'UNION'
        bpy.ops.object.modifier_apply(modifier="Bool_Union_Step")
        cutter_large.name = "HoleCutter_StepCombined"
        cutter_large.hide_set(True)
        cutter_large.hide_render = True
        bpy.data.objects.remove(cutter_small, do_unlink=True)
        cutters.append(cutter_large)

    elif props.hole_type == 'tapered_stepped':
        # 锥形台阶孔：锥形孔从顶部到台阶（大口在上），小直孔从台阶到底部
        taper_top_r = props.tapered_step_top_radius * S
        taper_step_r = props.tapered_step_bottom_radius * S
        large_h = props.stepped_large_height / 100.0 * H
        small_r = props.stepped_small_radius * S
        step_z = hh / 2 - large_h
        ext_ov = H * 0.05  # 5% of height — overlap for clean union at the step
        # Compute extrapolated radii so design radii match exactly at step_z and hh/2.
        # Tapered cutter ends exactly at step_z (no extension below → no over-depth),
        # with r=taper_step_r there; the small cutter overlaps above step_z (hidden
        # inside the wider taper). r_cutter_top keeps radius == taper_top_r at top face.
        grad = (taper_top_r - taper_step_r) / large_h  # radius change per unit z
        r_cutter_bot = taper_step_r                     # exact radius at step plane
        r_cutter_top = taper_top_r + ext_ov * grad      # wider at extended top
        # 创建两个切割体
        cutter_top = make_hole_cutter(
            "HoleCutter_TprStepTop",
            step_z, hh / 2 + ext_ov, r_cutter_bot, r_cutter_top
        )
        cutter_bot = make_hole_cutter(
            "HoleCutter_TprStepSmall",
            -hh / 2 - ext_ov, step_z + ext_ov, small_r, small_r
        )
        # 融合为一个切割体（Boolean UNION 消除内部重叠面，避免直孔被堵）
        cutter_top.hide_set(False)
        cutter_bot.hide_set(False)
        bpy.ops.object.select_all(action='DESELECT')
        cutter_top.select_set(True)
        bpy.context.view_layer.objects.active = cutter_top
        mod_union = cutter_top.modifiers.new(name="Bool_Union", type='BOOLEAN')
        mod_union.object = cutter_bot
        mod_union.operation = 'UNION'
        bpy.ops.object.modifier_apply(modifier="Bool_Union")
        cutter_top.name = "HoleCutter_TprStepCombined"
        cutter_top.hide_set(True)
        cutter_top.hide_render = True
        bpy.data.objects.remove(cutter_bot, do_unlink=True)
        cutters.append(cutter_top)
    
    # 布尔减：逐个创建并立即应用 modifier（顺序应用，避免重叠切割体导致破损）
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    for i, cutter in enumerate(cutters):
        mod_name = "Bool_Hole_" + cutter.name
        mod = obj.modifiers.new(name=mod_name, type='BOOLEAN')
        mod.object = cutter
        mod.operation = 'DIFFERENCE'
        log_to_file(f"[STEP Exporter] _boolean_difference: applying {mod_name} (cutter at z={cutter.location.z:.4f}, r={cutter.dimensions.x/2:.4f}, h={cutter.dimensions.z:.4f})")
        try:
            bpy.ops.object.modifier_apply(modifier=mod_name)
        except RuntimeError as e:
            log_to_file(f"[STEP Exporter] _boolean_difference: WARNING {mod_name} apply failed: {e}")
    log_to_file(f"[STEP Exporter] _boolean_difference: all {len(cutters)} modifiers applied, target verts={len(obj.data.vertices)}")
    
    # 清理布尔运算产生的退化几何
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.mesh.remove_doubles(threshold=0.0001)
    bpy.ops.mesh.delete_loose()
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.mesh.dissolve_degenerate(threshold=0.0001)  # 溶解零面积面
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.mesh.normals_make_consistent(inside=False)
    bpy.ops.object.mode_set(mode='OBJECT')
    log_to_file(f"[STEP Exporter] _boolean_difference: mesh cleaned, verts={len(obj.data.vertices)}")
    
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
    elif props.hole_type == 'stepped':
        large_r = props.stepped_large_radius * S
        large_h = props.stepped_large_height / 100.0 * H
        small_r = props.stepped_small_radius * S
        obj['hole_type'] = 'stepped'
        obj['hole_position'] = 'stepped'
        obj['hole_depth'] = large_h
        obj['hole_is_stepped'] = True
        obj['hole_stepped_large_r'] = props.stepped_large_radius  # store in mm (user-facing unit)
        obj['hole_stepped_large_h'] = props.stepped_large_height / 100.0 * props.height  # mm
        obj['hole_stepped_small_r'] = props.stepped_small_radius  # mm
        log_to_file(f"[STEP Exporter] _create_holes: stored stepped large_r={props.stepped_large_radius:.1f}mm large_h={props.stepped_large_height/100.0*props.height:.1f}mm small_r={props.stepped_small_radius:.1f}mm")
    elif props.hole_type == 'tapered_stepped':
        large_h = props.stepped_large_height / 100.0 * H
        small_r = props.stepped_small_radius * S
        taper_top_r = props.tapered_step_top_radius * S
        taper_step_r = props.tapered_step_bottom_radius * S
        obj['hole_type'] = 'tapered_stepped'  # 必须区分，检测代码据此判断锥形台阶孔
        obj['hole_position'] = 'tapered_stepped'
        obj['hole_depth'] = large_h
        obj['hole_is_stepped'] = True
        obj['hole_is_tapered'] = True
        obj['hole_taper_top_r'] = props.tapered_step_top_radius    # mm — top opening
        obj['hole_taper_step_r'] = props.tapered_step_bottom_radius  # mm — at step
        obj['hole_stepped_small_r'] = props.stepped_small_radius   # mm
        obj['hole_opening_radius'] = props.tapered_step_top_radius  # mm — used by detection
        obj['hole_end_radius'] = props.tapered_step_bottom_radius   # mm — used by detection
        obj['hole_stepped_large_h'] = props.stepped_large_height / 100.0 * props.height  # mm
        log_to_file(f"[STEP Exporter] _create_holes: stored tapered_stepped large_r={props.stepped_large_radius:.1f}mm large_h={props.stepped_large_height/100.0*props.height:.1f}mm small_r={props.stepped_small_radius:.1f}mm")
        obj['hole_stepped_small_r'] = props.stepped_small_radius  # mm
        obj['hole_taper_top_r'] = props.tapered_step_top_radius  # mm
        obj['hole_taper_step_r'] = props.tapered_step_bottom_radius  # mm
        log_to_file(f"[STEP Exporter] _create_holes: stored tapered_stepped (→parametric stepped) top_r={props.tapered_step_top_radius:.1f}mm step_r={props.tapered_step_bottom_radius:.1f}mm small_r={props.stepped_small_radius:.1f}mm large_h={props.stepped_large_height/100.0*props.height:.1f}mm")
    
    # 孔口圆倒角
    if props.hole_fillet_radius > 0 and cutters:
        _apply_hole_fillet(obj, props, S)


def _create_groove(obj, props, S):
    """创建外壁梯形槽：用梯形棱柱切割体做布尔减（单侧直槽，非环切）"""
    import bmesh

    # Use mid-height radius: for cones, the groove is at z=0 where radius = (BR+TR)/2
    if props.cylinder_type == 'tapered':
        R_mid = (props.bottom_radius + props.top_radius) / 2.0 * S
        R_mid_mm = (props.bottom_radius + props.top_radius) / 2.0
    else:
        R_mid = props.radius * S
        R_mid_mm = props.radius

    # Penetration depth (actual groove depth into the body)
    groove_depth_mm = round(R_mid_mm * props.groove_depth_pct / 100.0, 1)
    # User-set top width
    groove_top_w_mm = props.groove_top_width
    angle_rad = props.groove_angle

    if props.cylinder_type == 'tapered':
        # Cutter extends beyond the surface (multiplier enlarges cutter, not penetration)
        cutter_depth_mm = groove_depth_mm * props.groove_cone_depth_mult
        r_surface = R_mid + (cutter_depth_mm - groove_depth_mm) * S + 0.0001  # extend outward
        r_floor = R_mid - groove_depth_mm * S  # penetration unchanged
    else:
        cutter_depth_mm = groove_depth_mm
        r_surface = R_mid + 0.0001
        r_floor = R_mid - groove_depth_mm * S

    # bottom_w follows from (r_surface - r_floor) and angle
    cutter_span_mm = (r_surface - r_floor) / S  # radial span of cutter in mm
    groove_bot_w_mm = groove_top_w_mm + 2.0 * cutter_span_mm * math.tan(angle_rad)

    bot_w = groove_bot_w_mm * S
    top_w = groove_top_w_mm * S
    hb = bot_w / 2.0
    ht = top_w / 2.0

    ext_len = 2.0 * R_mid + 0.04            # through entire diameter + margin
    half_ext = ext_len / 2.0

    log_to_file(f"[STEP Exporter] _create_groove: type={props.cylinder_type} R_mid={R_mid_mm:.1f}mm "
                f"depth={groove_depth_mm:.1f}mm r_floor={r_floor/S:.1f}mm r_surf={r_surface/S:.1f}mm "
                f"bot_w={groove_bot_w_mm:.1f}mm top_w={groove_top_w_mm:.2f}mm "
                f"angle={math.degrees(angle_rad):.1f}°"
                f"{' mult='+str(props.groove_cone_depth_mult) if props.cylinder_type=='tapered' else ''}")

    # Use cube primitive (proven to work with EXACT solver) + vertex move
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(0, 0, 0))
    cutter = bpy.context.active_object
    cutter.name = "GrooveCutter"

    bpy.ops.object.mode_set(mode='EDIT')
    bm = bmesh.from_edit_mesh(cutter.data)

    for v in bm.verts:
        x_sign = 1 if v.co.x > 0 else -1
        y_sign = 1 if v.co.y > 0 else -1
        z_sign = 1 if v.co.z > 0 else -1

        # X: outer (+X) → r_surface, inner (-X) → r_floor
        new_x = r_surface if x_sign > 0 else r_floor
        # Y: along circumference
        new_y = half_ext if y_sign > 0 else -half_ext
        # Z: wider at surface (X+), narrower at floor (X-)
        half_w = hb if x_sign > 0 else ht
        new_z = half_w if z_sign > 0 else -half_w

        v.co = (new_x, new_y, new_z)

    bmesh.update_edit_mesh(cutter.data)
    bpy.ops.object.mode_set(mode='OBJECT')

    # Boolean difference
    _boolean_difference(obj, cutter)
    bpy.data.objects.remove(cutter, do_unlink=True)

    # Clean up mesh after groove
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.mesh.remove_doubles(threshold=0.0001)
    bpy.ops.mesh.delete_loose()
    bpy.ops.object.mode_set(mode='OBJECT')

    # Store groove parameters (mm) for analysis & parametric export
    obj['step_groove_depth'] = groove_depth_mm
    obj['step_groove_bottom_width'] = groove_bot_w_mm
    obj['step_groove_top_width'] = props.groove_top_width
    obj['step_groove_extrusion_length'] = 2.0 * (R_mid / S) + 4.0
    obj['step_groove_angle'] = math.degrees(angle_rad)  # degrees, for C++ export


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

    outer_r_top = (props.radius if props.cylinder_type == 'standard' else props.top_radius) * S
    outer_r_btm = (props.radius if props.cylinder_type == 'standard' else props.bottom_radius) * S

    if props.hole_type in ('stepped', 'tapered_stepped'):
        # === Stepped / Tapered Stepped: fillet all hole edges ===
        step_z = H / 2.0 - (props.stepped_large_height / 100.0 * H)
        small_r = props.stepped_small_radius * S

        if props.hole_type == 'stepped':
            large_r = props.stepped_large_radius * S
            step_r = large_r  # step outer edge has same radius as large hole
        else:
            large_r = props.tapered_step_top_radius * S
            step_r = props.tapered_step_bottom_radius * S  # tapered hole narrows to this at step

        # Build list of (z_position, expected_radius) for each edge
        targets = [
            (top_z, large_r),    # top surface opening
            (step_z, step_r),     # step outer edge (bottom of large/tapered section)
            (step_z, small_r),    # step inner edge (top of small hole)
            (btm_z, small_r),     # bottom surface opening
        ]

        for edge in bm.edges:
            vz0 = edge.verts[0].co.z
            vz1 = edge.verts[1].co.z
            mid_z = (vz0 + vz1) / 2.0
            mid_xy = math.sqrt(
                ((edge.verts[0].co.x + edge.verts[1].co.x) / 2) ** 2 +
                ((edge.verts[0].co.y + edge.verts[1].co.y) / 2) ** 2
            )
            dz = abs(vz0 - vz1)
            for tz, tr in targets:
                if abs(mid_z - tz) < 0.02 and abs(mid_xy - tr) < tr * 0.5 and dz < 0.01:
                    edge.select = True
                    break

    else:
        # Original logic for through / top / bottom / both
        # NOTE: must select only HORIZONTAL rim edges (BOTH endpoints on the
        # top/bottom plane). Using min() on the two endpoint z-distances wrongly
        # also selects the VERTICAL hole-wall edges (one endpoint touches the
        # face plane), which then get beveled into a thick residual ring around
        # the hole opening. Use max() so only in-plane rim edges are selected.
        tol = 0.0005  # 0.5mm — plane tolerance for horizontal rim edges
        for edge in bm.edges:
            vz0 = edge.verts[0].co.z
            vz1 = edge.verts[1].co.z
            if props.hole_type in ('top', 'through', 'both'):
                dz_top = max(abs(vz0 - top_z), abs(vz1 - top_z))
                if dz_top < tol:
                    dist0 = math.sqrt(edge.verts[0].co.x**2 + edge.verts[0].co.y**2)
                    dist1 = math.sqrt(edge.verts[1].co.x**2 + edge.verts[1].co.y**2)
                    if dist0 < outer_r_top * 0.9 and dist1 < outer_r_top * 0.9:
                        edge.select = True
            
            if props.hole_type in ('bottom', 'through', 'both'):
                dz_btm = max(abs(vz0 - btm_z), abs(vz1 - btm_z))
                if dz_btm < tol:
                    dist0 = math.sqrt(edge.verts[0].co.x**2 + edge.verts[0].co.y**2)
                    dist1 = math.sqrt(edge.verts[1].co.x**2 + edge.verts[1].co.y**2)
                    if dist0 < outer_r_btm * 0.9 and dist1 < outer_r_btm * 0.9:
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

