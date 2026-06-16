"""Parametric cylinder generation."""
import sys, os, math
import bpy, bmesh
from mathutils import Vector
from bpy.types import Operator
from bpy.props import StringProperty, FloatProperty, IntProperty, BoolProperty, EnumProperty
from ..core.utils import log_to_file
from ..core import _globals as _g

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

