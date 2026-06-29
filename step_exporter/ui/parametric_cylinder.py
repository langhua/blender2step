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
    # Stepped hole parameters
    stepped_large_radius: FloatProperty(
        name="Large Hole R", default=7.0, min=0.1, max=100.0,
        description="Radius of the large (top) section of the stepped hole",
    )
    stepped_large_height: FloatProperty(
        name="Large Hole H %", default=80, min=1, max=99, subtype='PERCENTAGE',
        description="Height of the large hole section as percentage of cylinder height",
    )
    stepped_small_radius: FloatProperty(
        name="Small Hole R", default=4.0, min=0.1, max=100.0,
        description="Radius of the small (bottom) section of the stepped hole",
    )
    # Tapered stepped hole parameters
    tapered_step_top_radius: FloatProperty(
        name="Tapered Top R", default=9.0, min=0.1, max=100.0,
        description="Radius of the tapered hole at the top surface (wider)",
    )
    tapered_step_bottom_radius: FloatProperty(
        name="Tapered Step R", default=7.0, min=0.1, max=100.0,
        description="Radius of the tapered hole at the step (narrower)",
    )
    # Groove parameters
    groove_enabled: BoolProperty(
        name="External Groove", default=False,
        description="Add a trapezoidal groove around the cylinder at mid-height",
    )
    groove_angle: FloatProperty(
        name="Groove Angle", default=math.radians(45.0),
        min=math.radians(30.0), max=math.radians(90.0),
        subtype='ANGLE',
        description="Angle of each side-wall measured from the groove floor (vertical)",
    )
    groove_top_width: FloatProperty(
        name="Top Width", default=2.0, min=0.1, max=100.0,
        description="Width of the groove at the groove floor (inner edge)",
    )
    groove_depth_pct: FloatProperty(
        name="Depth % of R", default=20.0, min=5.0, max=80.0, step=5.0,
        description="Groove depth as percentage of mid-radius",
    )
    groove_cone_depth_mult: FloatProperty(
        name="Cone Depth ×", default=1.5, min=1.0, max=3.0, step=0.1,
        description="Multiplier for groove depth on tapered cylinders (compensates slanted surface)",
    )
    
    def invoke(self, context, event):
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
            box.prop(self, 'top_radius')
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
            if self.hole_type in ('stepped', 'tapered_stepped'):
                box.prop(self, 'stepped_large_radius')
                box.prop(self, 'stepped_large_height')
                box.prop(self, 'stepped_small_radius')
                if self.hole_type == 'tapered_stepped':
                    box.prop(self, 'tapered_step_top_radius')
                    box.prop(self, 'tapered_step_bottom_radius')
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
    
    def execute(self, context):
        try:
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
    
    # === 3. 创建孔 ===
    if props.hole_type != 'none':
        _create_holes(obj, props, S)

    # === 4. 创建外壁梯形槽 ===
    if props.groove_enabled:
        _create_groove(obj, props, S)
    
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

    elif props.hole_type == 'stepped':
        # 台阶孔：大孔从顶部到台阶，小孔从台阶到底部
        large_r = props.stepped_large_radius * S
        large_h = props.stepped_large_height / 100.0 * H
        small_r = props.stepped_small_radius * S
        step_z = hh / 2 - large_h
        ext_ov = H * 0.15  # 15% of height — robust overlap for clean boolean
        # 大孔切割体（从顶部延伸到台阶下方）
        cutters.append(make_hole_cutter(
            "HoleCutter_StepLarge",
            step_z - ext_ov, hh / 2 + ext_ov, large_r, large_r
        ))
        # 小孔切割体（从台阶上方延伸到底部下方）
        cutters.append(make_hole_cutter(
            "HoleCutter_StepSmall",
            -hh / 2 - ext_ov, step_z + ext_ov, small_r, small_r
        ))

    elif props.hole_type == 'tapered_stepped':
        # 锥形台阶孔：锥形孔从顶部到台阶（大口在上），小直孔从台阶到底部
        taper_top_r = props.tapered_step_top_radius * S
        taper_step_r = props.tapered_step_bottom_radius * S
        large_h = props.stepped_large_height / 100.0 * H
        small_r = props.stepped_small_radius * S
        step_z = hh / 2 - large_h
        ext_ov = H * 0.15  # 15% of height — robust overlap + fully penetrate cone wall
        # Compute extrapolated radii so design radii match exactly at step_z and hh/2
        grad = (taper_top_r - taper_step_r) / large_h  # radius change per unit z
        r_cutter_bot = taper_step_r - ext_ov * grad   # narrower at extended bottom
        r_cutter_top = taper_top_r + ext_ov * grad     # wider at extended top
        # 创建两个切割体
        cutter_top = make_hole_cutter(
            "HoleCutter_TprStepTop",
            step_z - ext_ov, hh / 2 + ext_ov, r_cutter_bot, r_cutter_top
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
    
    # 清理布尔运算产生的退化几何（合并重复顶点、删除零面积面）
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.mesh.remove_doubles(threshold=0.0001)
    bpy.ops.mesh.delete_loose()
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
        obj['hole_type'] = 'stepped'  # 导出时使用直台阶孔参数化路径（锥度在STEP中近似为直孔）
        obj['hole_position'] = 'stepped'
        obj['hole_depth'] = large_h
        obj['hole_is_stepped'] = True   # 触发 cylinder_tapered_stepped_hole 参数化导出
        obj['hole_is_tapered'] = True
        obj['hole_opening_radius'] = props.tapered_step_top_radius  # mm (供参考)
        obj['hole_end_radius'] = props.tapered_step_bottom_radius  # mm (供参考)
        obj['hole_stepped_large_r'] = props.stepped_large_radius  # mm — 用大孔默认值保证参数化导出安全
        obj['hole_stepped_large_h'] = props.stepped_large_height / 100.0 * props.height  # mm
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
    bpy.ops.mesh.normals_make_consistent(inside=False)
    bpy.ops.object.mode_set(mode='OBJECT')

    # Store groove parameters (mm) for analysis & parametric export
    obj['step_groove_depth'] = groove_depth_mm
    obj['step_groove_bottom_width'] = groove_bot_w_mm
    obj['step_groove_top_width'] = props.groove_top_width
    obj['step_groove_extrusion_length'] = 2.0 * (R_mid / S) + 4.0  # through-slot, convert back to mm


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
        for edge in bm.edges:
            vz0 = edge.verts[0].co.z
            vz1 = edge.verts[1].co.z
            if props.hole_type in ('top', 'through', 'both'):
                dz_top_min = min(abs(vz0 - top_z), abs(vz1 - top_z))
                if dz_top_min < 0.01:
                    dist0 = math.sqrt(edge.verts[0].co.x**2 + edge.verts[0].co.y**2)
                    dist1 = math.sqrt(edge.verts[1].co.x**2 + edge.verts[1].co.y**2)
                    if dist0 < outer_r_top * 0.9 and dist1 < outer_r_top * 0.9:
                        edge.select = True
            
            if props.hole_type in ('bottom', 'through', 'both'):
                dz_btm_min = min(abs(vz0 - btm_z), abs(vz1 - btm_z))
                if dz_btm_min < 0.01:
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

