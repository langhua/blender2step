#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
塑料底壳生成器
使用Mesh创建塑料底壳，导出时美化为解析曲面

结构组成：
1. 外盒体 - 带圆角的矩形盒
2. 内腔体 - 挖空形成托盘
3. 螺丝孔 x4（在底板表面）

使用方法：
1. 在Blender中打开Scripting工作区
2. 打开此脚本
3. 点击运行按钮
"""

import bpy
import bmesh
import math
import sys
import os
from collections import defaultdict


def get_script_dir():
    if __file__ and os.path.isfile(__file__):
        return os.path.dirname(os.path.abspath(__file__))
    for text in bpy.data.texts:
        if text.filepath and os.path.isfile(text.filepath):
            return os.path.dirname(os.path.abspath(text.filepath))
    return os.getcwd()


def measure_fillet_radius_from_mesh(obj, is_outer=True, tolerance=0.1):
    """
    从 mesh 测量底部圆倒角半径
    
    原理：
    1. 找到底部表面（z 坐标最低的水平面）
    2. 分析 z-level 分布，找到圆角结束、垂直壁开始的位置
    3. 圆倒角半径 = 垂直壁开始位置 - 底部位置
    
    参数:
        obj: Blender 对象
        is_outer: True=测量外壁圆角, False=测量内壁圆角
        tolerance: 容差值，用于判断顶点是否在同一平面
    
    返回:
        测量得到的圆角半径（mm），如果无法测量则返回 None
    """
    if obj.type != 'MESH':
        print(f"[Measure] Object {obj.name} is not a mesh")
        return None
    
    # 获取评估后的 mesh（应用所有修改器）
    depsgraph = bpy.context.evaluated_depsgraph_get()
    eval_obj = obj.evaluated_get(depsgraph)
    mesh_data = eval_obj.data
    
    # 创建 bmesh 从 mesh 数据（不需要进入编辑模式）
    bm = bmesh.new()
    bm.from_mesh(mesh_data)
    bm.verts.ensure_lookup_table()
    bm.edges.ensure_lookup_table()
    
    # 获取所有顶点的 Z 坐标
    z_coords = [v.co.z for v in bm.verts]
    min_z = min(z_coords)
    max_z = max(z_coords)
    height = max_z - min_z
    
    print(f"[Measure] Mesh bounds: z=[{min_z:.3f}, {max_z:.3f}], height={height:.3f}")
    
    # 按 z 坐标分组顶点（精度 0.01mm）
    z_layers = defaultdict(list)
    for v in bm.verts:
        z_key = round(v.co.z / 0.01) * 0.01
        z_layers[z_key].append(v)
    
    # 找到所有不同的 z 层级
    sorted_z_levels = sorted(z_layers.keys())
    
    print(f"[Measure] Found {len(sorted_z_levels)} z-levels")
    print(f"[Measure] All z-levels: {sorted_z_levels}")
    
    if len(sorted_z_levels) < 2:
        print("[Measure] Not enough z-levels")
        bm.free()
        return None
    
    # 底部表面是 z 坐标最低的层级
    bottom_z = sorted_z_levels[0]
    bottom_verts = z_layers[bottom_z]
    
    print(f"[Measure] Bottom surface at z={bottom_z:.3f} with {len(bottom_verts)} vertices")
    
    # 找到圆角结束、垂直壁开始的位置
    # 策略：找到第一个间隙，其后的 z-level 数量显著少于总数量
    # 这表示圆角区域结束，进入垂直壁区域（通常只有顶部几个层级）
    wall_start_z = None
    total_levels = len(sorted_z_levels)
    
    for i in range(1, len(sorted_z_levels)):
        gap = sorted_z_levels[i] - sorted_z_levels[i-1]
        levels_after = total_levels - i  # 间隙后的层级数量
        
        # 如果间隙后的层级数量少于总数的 25%，说明进入了垂直壁区域
        if levels_after < total_levels * 0.25 and gap > 0.1:
            wall_start_z = sorted_z_levels[i]
            print(f"[Measure] Found wall start at z={sorted_z_levels[i]:.3f} (gap={gap:.3f}, levels_after={levels_after})")
            break
    
    if wall_start_z is None:
        # 如果没找到，使用最后一个间隙前的位置
        wall_start_z = sorted_z_levels[-2] if len(sorted_z_levels) > 1 else sorted_z_levels[-1]
        print(f"[Measure] No clear wall start found, using z={wall_start_z:.3f}")
    
    # 圆倒角半径 = 垂直壁开始位置 - 底部位置
    fillet_radius = wall_start_z - bottom_z
    
    print(f"[Measure] Calculated fillet radius: {fillet_radius:.3f} mm")
    
    # 验证结果合理性
    if fillet_radius < 0.1 or fillet_radius > height * 0.8:
        print(f"[Measure] Warning: Fillet radius {fillet_radius:.3f} mm seems unreasonable")
        bm.free()
        return None
    
    bm.free()
    
    return fillet_radius


def measure_shell_fillet_radii(obj):
    """
    测量底壳的外壁和内壁圆倒角半径
    
    返回:
        (outer_radius, inner_radius) 元组
    """
    print(f"\n{'='*60}")
    print(f"Measuring fillet radii from mesh: {obj.name}")
    print(f"{'='*60}")
    
    # 获取评估后的 mesh（应用所有修改器）
    depsgraph = bpy.context.evaluated_depsgraph_get()
    eval_obj = obj.evaluated_get(depsgraph)
    mesh_data = eval_obj.data
    
    # 创建 bmesh 从 mesh 数据
    bm = bmesh.new()
    bm.from_mesh(mesh_data)
    bm.verts.ensure_lookup_table()
    
    # 按 z 坐标分组顶点
    z_layers = defaultdict(list)
    for v in bm.verts:
        z_key = round(v.co.z / 0.01) * 0.01
        z_layers[z_key].append(v)
    
    sorted_z_levels = sorted(z_layers.keys())
    
    print(f"[Measure] Found {len(sorted_z_levels)} z-levels")
    print(f"[Measure] All z-levels: {sorted_z_levels}")
    
    # 打印每个 z-level 的顶点数量（用于调试）
    print(f"[Measure] Vertex counts per z-level:")
    for z_level in sorted_z_levels[:10]:
        print(f"  z={z_level:.3f}: {len(z_layers[z_level])} vertices")
    
    # 外壁底部是 z 坐标最低的层级
    outer_bottom_z = sorted_z_levels[0]
    outer_verts = z_layers[outer_bottom_z]
    print(f"[Measure] Outer bottom at z={outer_bottom_z:.3f} with {len(outer_verts)} vertices")
    
    # 找到外壁垂直壁开始的位置
    # 策略：找到第一个间隙，其后的 z-level 数量显著少于总数量
    # 注意：使用 sorted_z_levels[i-1]（圆角结束的层级），而不是 sorted_z_levels[i]（间隙后的层级）
    outer_wall_start_z = None
    total_levels = len(sorted_z_levels)
    
    for i in range(1, len(sorted_z_levels)):
        gap = sorted_z_levels[i] - sorted_z_levels[i-1]
        levels_after = total_levels - i
        
        if levels_after < total_levels * 0.25 and gap > 0.1:
            outer_wall_start_z = sorted_z_levels[i-1]  # 圆角结束的层级
            print(f"[Measure] Found gap at z={sorted_z_levels[i-1]:.3f} -> {sorted_z_levels[i]:.3f} (gap={gap:.3f}, levels_after={levels_after})")
            break
    
    if outer_wall_start_z is None:
        outer_wall_start_z = sorted_z_levels[-2] if len(sorted_z_levels) > 1 else sorted_z_levels[-1]
        print(f"[Measure] No clear wall start found, using z={outer_wall_start_z:.3f}")
    
    outer_radius = outer_wall_start_z - outer_bottom_z
    print(f"[Measure] Outer wall starts at z={outer_wall_start_z:.3f}")
    print(f"[Measure] Calculated outer fillet radius: {outer_radius:.3f} mm")
    
    # 找到内壁底部
    # 内壁底部应该：
    # 1. 高于外壁底部至少 0.5mm
    # 2. 低于外壁垂直壁开始位置
    # 3. 顶点数量较多（表示一个平面）
    # 策略：找到范围内顶点数量最多的 z-level
    candidate_z_levels = []
    for z_level in sorted_z_levels[1:]:
        if z_level > outer_bottom_z + 0.5 and z_level < outer_wall_start_z:
            if len(z_layers[z_level]) > len(outer_verts) * 0.3:
                candidate_z_levels.append((z_level, len(z_layers[z_level])))
    
    if candidate_z_levels:
        # 选择顶点数量最多的 z-level 作为内壁底部
        inner_bottom_z = max(candidate_z_levels, key=lambda x: x[1])[0]
        print(f"[Measure] Inner bottom found at z={inner_bottom_z:.3f} with {len(z_layers[inner_bottom_z])} vertices")
        
        # 测量内壁圆角：找到内壁侧壁开始的位置
        # 策略：找到内壁底部上方的最大间隙
        max_gap = 0
        inner_wall_start_z = None
        for i in range(1, len(sorted_z_levels)):
            if sorted_z_levels[i-1] >= inner_bottom_z:
                gap = sorted_z_levels[i] - sorted_z_levels[i-1]
                if gap > max_gap:
                    max_gap = gap
                    inner_wall_start_z = sorted_z_levels[i-1]
                    print(f"[Measure] Inner gap candidate: z={sorted_z_levels[i-1]:.3f} -> {sorted_z_levels[i]:.3f} (gap={gap:.3f})")
        
        if inner_wall_start_z is not None:
            inner_radius = inner_wall_start_z - inner_bottom_z
            print(f"[Measure] Inner wall starts at z={inner_wall_start_z:.3f}")
            print(f"[Measure] Calculated inner fillet radius: {inner_radius:.3f} mm")
        else:
            inner_radius = outer_radius * 0.5 if outer_radius else None
            print(f"[Measure] Could not find inner wall start, using estimated value")
    else:
        inner_radius = outer_radius * 0.5 if outer_radius else None
        print(f"[Measure] Could not find inner bottom, using estimated value")
    
    bm.free()
    
    return outer_radius, inner_radius


def clear_scene():
    for obj in list(bpy.data.objects):
        obj.modifiers.clear()

    for obj in list(bpy.data.objects):
        bpy.data.objects.remove(obj, do_unlink=True)

    for mesh in list(bpy.data.meshes):
        if mesh.users == 0:
            bpy.data.meshes.remove(mesh)


def apply_boolean(obj, tool_obj, operation='DIFFERENCE'):
    mod = obj.modifiers.new(name="Boolean", type='BOOLEAN')
    mod.operation = operation
    mod.object = tool_obj
    mod.solver = 'EXACT'

    bpy.context.view_layer.objects.active = obj

    with bpy.context.temp_override(object=obj, active_object=obj, selected_objects=[obj]):
        bpy.ops.object.modifier_apply(modifier=mod.name)

    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.mesh.remove_doubles(threshold=0.0001)
    bpy.ops.object.mode_set(mode='OBJECT')


def add_material(obj, name=None):
    if not obj.data.materials:
        mat_name = name or f"{obj.name}_Material"
        mat = bpy.data.materials.new(name=mat_name)
        mat.use_nodes = False
        mat.diffuse_color = (0.4, 0.6, 0.9, 1.0)
        obj.data.materials.append(mat)


def create_rounded_box(name, width, depth, height, corner_radius, segments=32):
    """创建一个带有圆角的立方体，从顶视图看四个角是圆角
    使用 BMesh 手动创建干净的圆角矩形"""
    import math
    
    hw = width / 2.0
    hd = depth / 2.0
    hh = height / 2.0
    
    max_radius = min(hw, hd) * 0.99
    corner_radius = min(corner_radius, max_radius)
    
    top_profile = []
    bottom_profile = []
    
    for i in range(segments):
        angle = (math.pi/2) * i / segments
        x = hw - corner_radius + corner_radius * math.cos(angle)
        y = hd - corner_radius + corner_radius * math.sin(angle)
        top_profile.append((x, y, hh))
        bottom_profile.append((x, y, -hh))
    
    for i in range(segments):
        t = i / segments
        x = hw - corner_radius - t * (width - 2 * corner_radius)
        y = hd
        top_profile.append((x, y, hh))
        bottom_profile.append((x, y, -hh))
    
    for i in range(segments):
        angle = math.pi/2 + (math.pi/2) * i / segments
        x = -hw + corner_radius + corner_radius * math.cos(angle)
        y = hd - corner_radius + corner_radius * math.sin(angle)
        top_profile.append((x, y, hh))
        bottom_profile.append((x, y, -hh))
    
    for i in range(segments):
        t = i / segments
        x = -hw
        y = hd - corner_radius - t * (depth - 2 * corner_radius)
        top_profile.append((x, y, hh))
        bottom_profile.append((x, y, -hh))
    
    for i in range(segments):
        angle = math.pi + (math.pi/2) * i / segments
        x = -hw + corner_radius + corner_radius * math.cos(angle)
        y = -hd + corner_radius + corner_radius * math.sin(angle)
        top_profile.append((x, y, hh))
        bottom_profile.append((x, y, -hh))
    
    for i in range(segments):
        t = i / segments
        x = -hw + corner_radius + t * (width - 2 * corner_radius)
        y = -hd
        top_profile.append((x, y, hh))
        bottom_profile.append((x, y, -hh))
    
    for i in range(segments):
        angle = 3*math.pi/2 + (math.pi/2) * i / segments
        x = hw - corner_radius + corner_radius * math.cos(angle)
        y = -hd + corner_radius + corner_radius * math.sin(angle)
        top_profile.append((x, y, hh))
        bottom_profile.append((x, y, -hh))
    
    for i in range(segments):
        t = i / segments
        x = hw
        y = -hd + corner_radius + t * (depth - 2 * corner_radius)
        top_profile.append((x, y, hh))
        bottom_profile.append((x, y, -hh))
    
    me = bpy.data.meshes.new(name=name)
    bm = bmesh.new()
    
    top_verts = [bm.verts.new(v) for v in top_profile]
    bottom_verts = [bm.verts.new(v) for v in bottom_profile]
    
    num_profile = len(top_profile)
    for i in range(num_profile):
        next_i = (i + 1) % num_profile
        face = [top_verts[i], top_verts[next_i], bottom_verts[next_i], bottom_verts[i]]
        bm.faces.new(face)
    
    top_center = bm.verts.new((0, 0, hh))
    for i in range(num_profile):
        next_i = (i + 1) % num_profile
        face = [top_center, top_verts[i], top_verts[next_i]]
        bm.faces.new(face)
    
    bottom_center = bm.verts.new((0, 0, -hh))
    for i in range(num_profile):
        next_i = (i + 1) % num_profile
        face = [bottom_center, bottom_verts[next_i], bottom_verts[i]]
        bm.faces.new(face)
    
    bm.to_mesh(me)
    bm.free()
    
    obj = bpy.data.objects.new(name, me)
    bpy.context.collection.objects.link(obj)
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    
    bpy.ops.object.shade_smooth()
    
    print(f"  Created rounded box with {len(obj.data.vertices)} vertices and {len(obj.data.edges)} edges")
    
    return obj


def create_bottom_shell(
    name="BottomShell",
    location=(0, 0, 0),
):
    print(f"\n{'='*60}")
    print(f"Creating bottom shell: {name}")
    print(f"  Creating single rounded box")

    width = 100.0
    depth = 70.0
    height = 10.0
    corner_r = 20.0
    
    obj = create_rounded_box(
        name=name,
        width=width,
        depth=depth,
        height=height,
        corner_radius=corner_r,
        segments=32
    )
    obj.location = (location[0], location[1], location[2])
    add_material(obj)
    
    print(f"  [OK] Rounded box created: {width} x {depth} x {height} mm, corner radius={corner_r} mm")

    print(f"\n  [DONE] Bottom shell '{name}' created successfully!")
    print(f"{'='*60}\n")

    return [obj]


def create_bottom_shell_scene():
    print("\n" + "="*60)
    print("Plastic Bottom Shell Generator")
    print("="*60)

    print("[1/2] Clearing scene...")
    clear_scene()

    print("[2/2] Creating bottom shell...")
    shell = create_bottom_shell(
        name="BottomShell",
        location=(0, 0, 0),
    )

    for area in bpy.context.screen.areas:
        if area.type == 'VIEW_3D':
            for space in area.spaces:
                if space.type == 'VIEW_3D':
                    space.shading.type = 'SOLID'
                    space.overlay.show_wireframes = False

    print("\n" + "="*60)
    print("[OK] Bottom shell scene created!")
    print("="*60)
    print("\nNext: File -> Export -> STEP (Enhanced)")


def create_hollow_shell_blender(name, width, depth, outer_height, bottom_thickness,
                                   wall_thickness, corner_radius, location, segments=32,
                                   holes=None):
    """在Blender中创建中空底壳：内盒+短柱融合 → 外盒切除"""
    outer = create_rounded_box(
        name=f"{name}_Outer",
        width=width,
        depth=depth,
        height=outer_height,
        corner_radius=corner_radius,
        segments=segments
    )
    outer.location = location

    inner_width = width - 2 * wall_thickness
    inner_depth = depth - 2 * wall_thickness
    inner_height = outer_height - bottom_thickness + 0.1
    inner_corner_r = max(corner_radius - wall_thickness, 1.0)

    inner = create_rounded_box(
        name=f"{name}_Inner",
        width=inner_width,
        depth=inner_depth,
        height=inner_height,
        corner_radius=inner_corner_r,
        segments=segments
    )
    inner_z = location[2] - outer_height / 2.0 + bottom_thickness + inner_height / 2.0 + 0.05
    inner.location = (location[0], location[1], inner_z)

    if holes:
        hole_radius, hole_offset_x, hole_offset_y = holes
        hw = width / 2.0
        hd = depth / 2.0
        hh = outer_height / 2.0
        hole_cx = hw - hole_offset_x
        hole_cy = hd - hole_offset_y
        outer_bottom = location[2] - hh
        inner_bottom = inner_z - inner_height / 2.0
        cyl_z_bottom = outer_bottom
        cyl_z_top = location[2] + hh + 2.0
        cyl_height = cyl_z_top - cyl_z_bottom
        cyl_z = (cyl_z_top + cyl_z_bottom) / 2.0

        corner_positions = [
            ( hole_cx,  hole_cy),
            (-hole_cx,  hole_cy),
            (-hole_cx, -hole_cy),
            ( hole_cx, -hole_cy),
        ]
        cyl_objs = []
        for i, (cx, cy) in enumerate(corner_positions):
            bpy.ops.mesh.primitive_cylinder_add(
                vertices=64,
                radius=hole_radius,
                depth=cyl_height,
                location=(location[0] + cx, location[1] + cy, cyl_z),
            )
            cyl_obj = bpy.context.active_object
            cyl_obj.name = f"{name}_HoleCyl_{i}"
            cyl_objs.append(cyl_obj)

        for i, cyl_obj in enumerate(cyl_objs):
            mod_o = outer.modifiers.new(name=f"Boolean_Hole_Outer_{i}", type='BOOLEAN')
            mod_o.operation = 'DIFFERENCE'
            mod_o.object = cyl_obj
            mod_o.solver = 'FAST'
            mod_i = inner.modifiers.new(name=f"Boolean_Hole_Inner_{i}", type='BOOLEAN')
            mod_i.operation = 'DIFFERENCE'
            mod_i.object = cyl_obj
            mod_i.solver = 'FAST'

        bpy.context.view_layer.objects.active = outer
        for i in range(len(cyl_objs)):
            bpy.ops.object.modifier_apply(modifier=f"Boolean_Hole_Outer_{i}")
        bpy.context.view_layer.objects.active = inner
        for i in range(len(cyl_objs)):
            bpy.ops.object.modifier_apply(modifier=f"Boolean_Hole_Inner_{i}")

        for cyl_obj in cyl_objs:
            bpy.data.objects.remove(cyl_obj, do_unlink=True)

    apply_boolean(outer, inner, operation='DIFFERENCE')
    bpy.data.objects.remove(inner, do_unlink=True)

    outer.name = name
    return outer


def create_both_bottom_shells_scene():
    """同时生成两个底壳：一个带4个孔，另一个不带，都导出为完美STEP"""
    print("\n" + "="*60)
    print("Dual Bottom Shell Generator")
    print("="*60)

    print("[1/4] Clearing scene...")
    clear_scene()

    width = 100.0
    depth = 70.0
    outer_height = 10.0
    bottom_thickness = 2.0
    wall_thickness = 2.0
    corner_radius = 20.0
    hole_radius = 3.0
    hole_offset_x = 25.0
    hole_offset_y = 20.0

    print("[2/4] Creating bottom shell WITHOUT holes (Blender preview)...")
    shell_no_holes = create_hollow_shell_blender(
        name="BottomShell_NoHoles",
        width=width,
        depth=depth,
        outer_height=outer_height,
        bottom_thickness=bottom_thickness,
        wall_thickness=wall_thickness,
        corner_radius=corner_radius,
        location=(-60, 0, 0),
        segments=32
    )
    add_material(shell_no_holes, name="ShellNoHolesMaterial")
    print(f"  [OK] Bottom shell (no holes) created")

    print("[3/4] Creating bottom shell WITH holes (Blender preview)...")
    shell_with_holes = create_hollow_shell_blender(
        name="BottomShell_WithHoles",
        width=width,
        depth=depth,
        outer_height=outer_height,
        bottom_thickness=bottom_thickness,
        wall_thickness=wall_thickness,
        corner_radius=corner_radius,
        location=(60, 0, 0),
        segments=32,
        holes=(hole_radius, hole_offset_x, hole_offset_y),
    )
    add_material(shell_with_holes, name="ShellWithHolesMaterial")
    print(f"  [OK] Bottom shell (with holes) created")

    for area in bpy.context.screen.areas:
        if area.type == 'VIEW_3D':
            for space in area.spaces:
                if space.type == 'VIEW_3D':
                    space.shading.type = 'SOLID'
                    space.overlay.show_wireframes = False

    print("[4/4] Exporting perfect STEP via C++ extension...")
    script_dir = get_script_dir()
    lib_dir = os.path.abspath(os.path.join(script_dir, '..', 'lib'))
    sys.path.insert(0, lib_dir)
    os.environ['PATH'] = lib_dir + os.pathsep + os.environ.get('PATH', '')
    if hasattr(os, 'add_dll_directory'):
        os.add_dll_directory(lib_dir)

    import _step_exporter as cpp_exporter

    output_no_holes = os.path.join(script_dir, 'bottom_shell_no_holes.step')
    result1 = cpp_exporter.export_rounded_box_step(
        output_no_holes,
        width, depth, outer_height,
        bottom_thickness, wall_thickness, corner_radius,
    )
    if result1:
        print(f"  [OK] Bottom shell (no holes) -> {output_no_holes}")
    else:
        print(f"  [FAIL] Bottom shell (no holes) export failed")

    output_with_holes = os.path.join(script_dir, 'bottom_shell_with_holes.step')
    result2 = cpp_exporter.export_bottom_shell_with_holes_step(
        output_with_holes,
        width, depth, outer_height,
        bottom_thickness, wall_thickness,
        corner_radius, hole_radius,
        hole_offset_x, hole_offset_y,
    )
    if result2:
        print(f"  [OK] Bottom shell (with holes) -> {output_with_holes}")
    else:
        print(f"  [FAIL] Bottom shell (with holes) export failed")

    print("\n" + "="*60)
    print("[OK] Both bottom shells created and exported!")
    print("="*60)


def bevel_box_bottom_edges(obj, height, fillet_radius, bevel_segments=4):
    """对盒体所有底面边缘施加圆角（fillet），与C++ BRepFilletAPI_MakeFillet一致"""
    if fillet_radius <= 0.001:
        return

    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    bpy.ops.object.mode_set(mode='EDIT')

    me = obj.data
    bm = bmesh.from_edit_mesh(me)
    bm.edges.ensure_lookup_table()

    hh = height / 2.0

    # 计算盒体最大半宽/半深
    xs = [v.co.x for v in bm.verts]
    ys = [v.co.y for v in bm.verts]
    hw = max(abs(min(xs)), abs(max(xs)))
    hd = max(abs(min(ys)), abs(max(ys)))

    # 先溶解直壁上的多余顶点，使每条直壁底边合并为一条连续边
    verts_to_dissolve = []
    for v in bm.verts:
        if abs(v.co.z + hh) > 0.02:
            continue
        # 只处理直壁上的顶点（在最大X或最大Y处）
        on_straight = (abs(abs(v.co.x) - hw) < 0.05) or (abs(abs(v.co.y) - hd) < 0.05)
        if not on_straight:
            continue
        # 检查是否连接两条直壁底边
        straight_edge_count = 0
        for e in v.link_edges:
            other = e.other_vert(v)
            if abs(other.co.z + hh) < 0.02:
                other_on_straight = (abs(abs(other.co.x) - hw) < 0.05) or (abs(abs(other.co.y) - hd) < 0.05)
                if other_on_straight:
                    straight_edge_count += 1
        # 溶解中间顶点（连接两条直壁边）
        if straight_edge_count == 2:
            verts_to_dissolve.append(v)

    if verts_to_dissolve:
        bmesh.ops.dissolve_verts(bm, verts=verts_to_dissolve, use_face_split=False, use_boundary_tear=False)
        bm.edges.ensure_lookup_table()

    # 收集所有底面垂直边缘（连接底面和侧壁的边）
    bottom_edges = []
    for edge in bm.edges:
        v1, v2 = edge.verts
        # 只选择垂直边缘：一个顶点在底面，另一个不在底面
        v1_on_bottom = abs(v1.co.z + hh) < 0.02
        v2_on_bottom = abs(v2.co.z + hh) < 0.02
        if v1_on_bottom != v2_on_bottom:  # 一个在底面，一个不在
            # 检查是否在边界上
            v_on_boundary = (abs(abs(v1.co.x) - hw) < 0.05) or (abs(abs(v1.co.y) - hd) < 0.05)
            v2_on_boundary = (abs(abs(v2.co.x) - hw) < 0.05) or (abs(abs(v2.co.y) - hd) < 0.05)
            if v_on_boundary or v2_on_boundary:
                bottom_edges.append(edge)

    # 对所有底面外轮廓边施加圆角
    edges_to_fillet = bottom_edges

    if edges_to_fillet:
        bmesh.ops.bevel(
            bm,
            geom=edges_to_fillet,
            offset=fillet_radius,
            offset_type='OFFSET',
            segments=bevel_segments,
            profile=0.5,
            affect='EDGES',
            clamp_overlap=True,
            loop_slide=True
        )

    bmesh.update_edit_mesh(me)
    bpy.ops.object.mode_set(mode='OBJECT')


def create_filleted_shell_blender(name, width, depth, outer_height, bottom_thickness, wall_thickness, corner_radius, outer_fillet_radius, inner_fillet_radius, location=(0, 0, 0), segments=32, step_height=1.0, holes=None):
    """在Blender中创建带底面圆角的中空底壳：使用BMesh直接创建
    step_height: 顶部台阶高度，外侧壁比内侧壁低多少mm"""
    import math

    hw = width / 2.0
    hd = depth / 2.0
    hh = outer_height / 2.0
    max_radius = min(hw, hd) * 0.99
    corner_radius = min(corner_radius, max_radius)

    # 生成外轮廓
    outer_profile = []
    for i in range(segments):
        angle = (math.pi/2) * i / segments
        x = hw - corner_radius + corner_radius * math.cos(angle)
        y = hd - corner_radius + corner_radius * math.sin(angle)
        outer_profile.append((x, y))
    for i in range(segments):
        t = i / segments
        x = hw - corner_radius - t * (width - 2 * corner_radius)
        y = hd
        outer_profile.append((x, y))
    for i in range(segments):
        angle = math.pi/2 + (math.pi/2) * i / segments
        x = -hw + corner_radius + corner_radius * math.cos(angle)
        y = hd - corner_radius + corner_radius * math.sin(angle)
        outer_profile.append((x, y))
    for i in range(segments):
        t = i / segments
        x = -hw
        y = hd - corner_radius - t * (depth - 2 * corner_radius)
        outer_profile.append((x, y))
    for i in range(segments):
        angle = math.pi + (math.pi/2) * i / segments
        x = -hw + corner_radius + corner_radius * math.cos(angle)
        y = -hd + corner_radius + corner_radius * math.sin(angle)
        outer_profile.append((x, y))
    for i in range(segments):
        t = i / segments
        x = -hw + corner_radius + t * (width - 2 * corner_radius)
        y = -hd
        outer_profile.append((x, y))
    for i in range(segments):
        angle = 3*math.pi/2 + (math.pi/2) * i / segments
        x = hw - corner_radius + corner_radius * math.cos(angle)
        y = -hd + corner_radius + corner_radius * math.sin(angle)
        outer_profile.append((x, y))
    for i in range(segments):
        t = i / segments
        x = hw
        y = -hd + corner_radius + t * (depth - 2 * corner_radius)
        outer_profile.append((x, y))

    # 内轮廓（与外轮廓相同的结构，但偏移wall_thickness）
    inner_hw = hw - wall_thickness
    inner_hd = hd - wall_thickness
    inner_corner_r = max(corner_radius - wall_thickness, 1.0)
    inner_profile = []
    for i in range(segments):
        angle = (math.pi/2) * i / segments
        x = inner_hw - inner_corner_r + inner_corner_r * math.cos(angle)
        y = inner_hd - inner_corner_r + inner_corner_r * math.sin(angle)
        inner_profile.append((x, y))
    for i in range(segments):
        t = i / segments
        x = inner_hw - inner_corner_r - t * (inner_hw * 2 - 2 * inner_corner_r)
        y = inner_hd
        inner_profile.append((x, y))
    for i in range(segments):
        angle = math.pi/2 + (math.pi/2) * i / segments
        x = -inner_hw + inner_corner_r + inner_corner_r * math.cos(angle)
        y = inner_hd - inner_corner_r + inner_corner_r * math.sin(angle)
        inner_profile.append((x, y))
    for i in range(segments):
        t = i / segments
        x = -inner_hw
        y = inner_hd - inner_corner_r - t * (inner_hd * 2 - 2 * inner_corner_r)
        inner_profile.append((x, y))
    for i in range(segments):
        angle = math.pi + (math.pi/2) * i / segments
        x = -inner_hw + inner_corner_r + inner_corner_r * math.cos(angle)
        y = -inner_hd + inner_corner_r + inner_corner_r * math.sin(angle)
        inner_profile.append((x, y))
    for i in range(segments):
        t = i / segments
        x = -inner_hw + inner_corner_r + t * (inner_hw * 2 - 2 * inner_corner_r)
        y = -inner_hd
        inner_profile.append((x, y))
    for i in range(segments):
        angle = 3*math.pi/2 + (math.pi/2) * i / segments
        x = inner_hw - inner_corner_r + inner_corner_r * math.cos(angle)
        y = -inner_hd + inner_corner_r + inner_corner_r * math.sin(angle)
        inner_profile.append((x, y))
    for i in range(segments):
        t = i / segments
        x = inner_hw
        y = -inner_hd + inner_corner_r + t * (inner_hd * 2 - 2 * inner_corner_r)
        inner_profile.append((x, y))

    # 中间轮廓（外轮廓向内偏移1mm，用于两级台阶的第一级分割线）
    mid_hw = hw - 1.0
    mid_hd = hd - 1.0
    mid_corner_r = max(corner_radius - 1.0, 1.0)
    mid_profile = []
    for i in range(segments):
        angle = (math.pi/2) * i / segments
        x = mid_hw - mid_corner_r + mid_corner_r * math.cos(angle)
        y = mid_hd - mid_corner_r + mid_corner_r * math.sin(angle)
        mid_profile.append((x, y))
    for i in range(segments):
        t = i / segments
        x = mid_hw - mid_corner_r - t * (mid_hw * 2 - 2 * mid_corner_r)
        y = mid_hd
        mid_profile.append((x, y))
    for i in range(segments):
        angle = math.pi/2 + (math.pi/2) * i / segments
        x = -mid_hw + mid_corner_r + mid_corner_r * math.cos(angle)
        y = mid_hd - mid_corner_r + mid_corner_r * math.sin(angle)
        mid_profile.append((x, y))
    for i in range(segments):
        t = i / segments
        x = -mid_hw
        y = mid_hd - mid_corner_r - t * (mid_hd * 2 - 2 * mid_corner_r)
        mid_profile.append((x, y))
    for i in range(segments):
        angle = math.pi + (math.pi/2) * i / segments
        x = -mid_hw + mid_corner_r + mid_corner_r * math.cos(angle)
        y = -mid_hd + mid_corner_r + mid_corner_r * math.sin(angle)
        mid_profile.append((x, y))
    for i in range(segments):
        t = i / segments
        x = -mid_hw + mid_corner_r + t * (mid_hw * 2 - 2 * mid_corner_r)
        y = -mid_hd
        mid_profile.append((x, y))
    for i in range(segments):
        angle = 3*math.pi/2 + (math.pi/2) * i / segments
        x = mid_hw - mid_corner_r + mid_corner_r * math.cos(angle)
        y = -mid_hd + mid_corner_r + mid_corner_r * math.sin(angle)
        mid_profile.append((x, y))
    for i in range(segments):
        t = i / segments
        x = mid_hw
        y = -mid_hd + mid_corner_r + t * (mid_hd * 2 - 2 * mid_corner_r)
        mid_profile.append((x, y))

    num_profile = len(outer_profile)
    outer_bottom_z = -hh
    outer_top_z = hh - step_height
    inner_bottom_z = -hh + bottom_thickness
    inner_top_z = hh

    me = bpy.data.meshes.new(name=name)
    bm = bmesh.new()

    fillet_segments = 8

    # 计算底面轮廓（向内收缩outer_fillet_radius）
    bottom_profile = []
    for i in range(num_profile):
        x, y = outer_profile[i]
        dist = math.sqrt(x*x + y*y)
        if dist > 0.001:
            nx = x / dist
            ny = y / dist
        else:
            nx, ny = 1.0, 0.0
        bx = x - nx * outer_fillet_radius
        by = y - ny * outer_fillet_radius
        bottom_profile.append((bx, by))

    # 外底面（缩小后的底面）
    outer_bottom_verts = [bm.verts.new((x, y, outer_bottom_z)) for x, y in bottom_profile]
    outer_bottom_center = bm.verts.new((0, 0, outer_bottom_z))
    for i in range(num_profile):
        next_i = (i + 1) % num_profile
        bm.faces.new([outer_bottom_center, outer_bottom_verts[i], outer_bottom_verts[next_i]])

    # 外底面圆角过渡层（fillet）- 从缩小的底面平滑扩展到完整外轮廓
    fillet_layers = []
    for seg in range(1, fillet_segments + 1):
        t = seg / fillet_segments
        angle = math.pi/2 * t
        # 圆角：从缩小的底面逐渐向外扩展到完整轮廓，同时向上
        expand = outer_fillet_radius * math.sin(angle)  # 向外扩展量
        rise = outer_fillet_radius * (1.0 - math.cos(angle))  # 向上抬升量
        layer_verts = []
        for i in range(num_profile):
            bx, by = bottom_profile[i]
            # 计算该点的法线方向（从中心指向外）
            dist = math.sqrt(bx*bx + by*by)
            if dist > 0.001:
                nx = bx / dist
                ny = by / dist
            else:
                nx, ny = 1.0, 0.0
            # 沿法线方向扩展（向外）
            fx = bx + nx * expand
            fy = by + ny * expand
            fz = outer_bottom_z + rise
            layer_verts.append(bm.verts.new((fx, fy, fz)))
        fillet_layers.append(layer_verts)

    # 圆角面（连接底面边缘和第一层fillet）
    for i in range(num_profile):
        next_i = (i + 1) % num_profile
        bm.faces.new([outer_bottom_verts[i], outer_bottom_verts[next_i], fillet_layers[0][next_i], fillet_layers[0][i]])

    # 圆角面（fillet层之间）
    for seg in range(len(fillet_layers) - 1):
        for i in range(num_profile):
            next_i = (i + 1) % num_profile
            bm.faces.new([fillet_layers[seg][i], fillet_layers[seg][next_i], fillet_layers[seg+1][next_i], fillet_layers[seg+1][i]])

    # 外壁（从最后一层fillet到顶面）- 最后一层应该接近完整外轮廓
    outer_top_verts = [bm.verts.new((x, y, outer_top_z)) for x, y in outer_profile]
    last_fillet = fillet_layers[-1]
    for i in range(num_profile):
        next_i = (i + 1) % num_profile
        bm.faces.new([last_fillet[i], last_fillet[next_i], outer_top_verts[next_i], outer_top_verts[i]])

    # 内底面（缩小后的底面，为内圆角留出空间）
    inner_bottom_profile = []
    for i in range(num_profile):
        x, y = inner_profile[i]
        dist = math.sqrt(x*x + y*y)
        if dist > 0.001:
            nx = x / dist
            ny = y / dist
        else:
            nx, ny = 1.0, 0.0
        bx = x - nx * inner_fillet_radius
        by = y - ny * inner_fillet_radius
        inner_bottom_profile.append((bx, by))

    inner_bottom_verts = [bm.verts.new((x, y, inner_bottom_z)) for x, y in inner_bottom_profile]
    inner_bottom_center = bm.verts.new((0, 0, inner_bottom_z))
    for i in range(num_profile):
        next_i = (i + 1) % num_profile
        bm.faces.new([inner_bottom_center, inner_bottom_verts[next_i], inner_bottom_verts[i]])

    # 内壁圆角过渡层（fillet）- 从缩小的内底面平滑扩展到完整内轮廓
    inner_fillet_layers = []
    for seg in range(1, fillet_segments + 1):
        t = seg / fillet_segments
        angle = math.pi/2 * t
        expand = inner_fillet_radius * math.sin(angle)
        rise = inner_fillet_radius * (1.0 - math.cos(angle))
        layer_verts = []
        for i in range(num_profile):
            bx, by = inner_bottom_profile[i]
            dist = math.sqrt(bx*bx + by*by)
            if dist > 0.001:
                nx = bx / dist
                ny = by / dist
            else:
                nx, ny = 1.0, 0.0
            fx = bx + nx * expand
            fy = by + ny * expand
            fz = inner_bottom_z + rise
            layer_verts.append(bm.verts.new((fx, fy, fz)))
        inner_fillet_layers.append(layer_verts)

    # 内圆角面（连接内底面边缘和第一层fillet）
    for i in range(num_profile):
        next_i = (i + 1) % num_profile
        bm.faces.new([inner_bottom_verts[i], inner_bottom_verts[next_i], inner_fillet_layers[0][next_i], inner_fillet_layers[0][i]])

    # 内圆角面（fillet层之间）
    for seg in range(len(inner_fillet_layers) - 1):
        for i in range(num_profile):
            next_i = (i + 1) % num_profile
            bm.faces.new([inner_fillet_layers[seg][i], inner_fillet_layers[seg][next_i], inner_fillet_layers[seg+1][next_i], inner_fillet_layers[seg+1][i]])

    # 内壁（从最后一层fillet到顶面）
    inner_top_verts = [bm.verts.new((x, y, inner_top_z)) for x, y in inner_profile]
    last_inner_fillet = inner_fillet_layers[-1]
    for i in range(num_profile):
        next_i = (i + 1) % num_profile
        bm.faces.new([last_inner_fillet[i], last_inner_fillet[next_i], inner_top_verts[next_i], inner_top_verts[i]])

    # 两级台阶：第一级1mm宽（外壁→中间），第二级1mm宽（中间→内壁）
    # 中间顶点（mid_profile位置，两个Z高度）
    mid_outer_verts = [bm.verts.new((x, y, outer_top_z)) for x, y in mid_profile]
    mid_inner_verts = [bm.verts.new((x, y, inner_top_z)) for x, y in mid_profile]

    # 第一级水平台阶面（外壁 → 中间，1mm宽，同一Z高度）
    for i in range(num_profile):
        next_i = (i + 1) % num_profile
        bm.faces.new([outer_top_verts[i], outer_top_verts[next_i], mid_outer_verts[next_i], mid_outer_verts[i]])

    # 垂直台阶面（中间位置，从低Z到高Z，1mm高）
    for i in range(num_profile):
        next_i = (i + 1) % num_profile
        bm.faces.new([mid_outer_verts[i], mid_outer_verts[next_i], mid_inner_verts[next_i], mid_inner_verts[i]])

    # 第二级水平台阶面（中间 → 内壁，1mm宽，同一Z高度）
    for i in range(num_profile):
        next_i = (i + 1) % num_profile
        bm.faces.new([mid_inner_verts[i], mid_inner_verts[next_i], inner_top_verts[next_i], inner_top_verts[i]])

    bm.to_mesh(me)
    bm.free()

    obj = bpy.data.objects.new(name, me)
    bpy.context.collection.objects.link(obj)
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    obj.location = location
    bpy.ops.object.shade_smooth()

    if holes:
        hole_radius, hole_offset_x, hole_offset_y = holes
        hw = width / 2.0
        hd = depth / 2.0
        hh = outer_height / 2.0
        hole_cx = hw - hole_offset_x
        hole_cy = hd - hole_offset_y
        outer_bottom = location[2] - hh
        inner_bottom = location[2] - hh + bottom_thickness
        cyl_z_bottom = outer_bottom - 1.0
        cyl_z_top = location[2] + hh + 2.0
        cyl_height = cyl_z_top - cyl_z_bottom
        cyl_z = (cyl_z_top + cyl_z_bottom) / 2.0

        corner_positions = [
            ( hole_cx,  hole_cy),
            (-hole_cx,  hole_cy),
            (-hole_cx, -hole_cy),
            ( hole_cx, -hole_cy),
        ]
        cyl_objs = []
        for i, (cx, cy) in enumerate(corner_positions):
            bpy.ops.mesh.primitive_cylinder_add(
                vertices=64,
                radius=hole_radius,
                depth=cyl_height,
                location=(location[0] + cx, location[1] + cy, cyl_z),
            )
            cyl_obj = bpy.context.active_object
            cyl_obj.name = f"{name}_HoleCyl_{i}"
            cyl_objs.append(cyl_obj)

        for i, cyl_obj in enumerate(cyl_objs):
            mod = obj.modifiers.new(name=f"Boolean_Hole_{i}", type='BOOLEAN')
            mod.operation = 'DIFFERENCE'
            mod.object = cyl_obj
            mod.solver = 'FAST'

        bpy.context.view_layer.objects.active = obj
        for i in range(len(cyl_objs)):
            mod_name = f"Boolean_Hole_{i}"
            bpy.ops.object.modifier_apply(modifier=mod_name)

        for cyl_obj in cyl_objs:
            bpy.data.objects.remove(cyl_obj, do_unlink=True)

    print(f"  Created filleted shell with {len(obj.data.vertices)} vertices")
    return obj


def create_filleted_bottom_shells_scene():
    """生成带底面圆角的底壳（仅无孔），导出为完美STEP"""
    print("\n" + "="*60)
    print("Filleted Bottom Shell Generator (No Holes)")
    print("="*60)

    print("[1/4] Clearing scene...")
    clear_scene()

    width = 100.0
    depth = 70.0
    outer_height = 10.0
    bottom_thickness = 2.0
    wall_thickness = 2.0
    corner_radius = 20.0
    
    # 初始值（用于 Blender 预览创建）
    outer_fillet_radius = 3.0
    inner_fillet_radius = 1.5

    print("[2/4] Creating filleted bottom shell (Blender preview)...")
    shell = create_filleted_shell_blender(
        name="FilletedShell",
        width=width,
        depth=depth,
        outer_height=outer_height,
        bottom_thickness=bottom_thickness,
        wall_thickness=wall_thickness,
        corner_radius=corner_radius,
        outer_fillet_radius=outer_fillet_radius,
        inner_fillet_radius=inner_fillet_radius,
        location=(0, 0, 0),
        segments=32,
        step_height=1.0
    )
    add_material(shell, name="FilletedShellMaterial")
    print(f"  [OK] Filleted bottom shell created")

    for area in bpy.context.screen.areas:
        if area.type == 'VIEW_3D':
            for space in area.spaces:
                if space.type == 'VIEW_3D':
                    space.shading.type = 'SOLID'
                    space.overlay.show_wireframes = False

    print("[3/4] Measuring fillet radii from mesh...")
    measured_outer, measured_inner = measure_shell_fillet_radii(shell)
    
    if measured_outer is not None:
        outer_fillet_radius = measured_outer
        print(f"  [OK] Measured outer fillet radius: {outer_fillet_radius:.3f} mm")
    else:
        print(f"  [WARN] Could not measure outer fillet, using default: {outer_fillet_radius:.3f} mm")
    
    if measured_inner is not None:
        inner_fillet_radius = measured_inner
        print(f"  [OK] Measured inner fillet radius: {inner_fillet_radius:.3f} mm")
    else:
        print(f"  [WARN] Could not measure inner fillet, using default: {inner_fillet_radius:.3f} mm")

    print("[4/4] Exporting parametric STEP via C++ extension...")
    script_dir = get_script_dir()
    lib_dir = os.path.abspath(os.path.join(script_dir, '..', 'lib'))
    sys.path.insert(0, lib_dir)
    os.environ['PATH'] = lib_dir + os.pathsep + os.environ.get('PATH', '')
    if hasattr(os, 'add_dll_directory'):
        os.add_dll_directory(lib_dir)

    import _step_exporter as cpp_exporter

    output = os.path.join(script_dir, 'bottom_shell_filleted.step')
    result = cpp_exporter.export_bottom_shell_filleted_step(
        output,
        width, depth, outer_height,
        bottom_thickness, wall_thickness, corner_radius,
        outer_fillet_radius, inner_fillet_radius,
        1.0,  # step_height
        0.0, 0.0, 0.0,  # pos_x, pos_y, pos_z
        "AP214IS",
        "MILLIMETER",
        1,  # enable_logging
    )
    if result:
        print(f"  [OK] Filleted bottom shell -> {output}")
    else:
        print(f"  [FAIL] Filleted bottom shell export failed")

    print("\n" + "="*60)
    print("[OK] Filleted bottom shell created and exported!")
    print("="*60)


def create_filleted_bottom_shells_with_holes_scene():
    """生成带底面圆角的底壳（无孔+有孔），导出为完美STEP"""
    print("\n" + "="*60)
    print("Filleted Bottom Shell Generator (With & Without Holes)")
    print("="*60)

    print("[1/5] Clearing scene...")
    clear_scene()

    width = 100.0
    depth = 70.0
    outer_height = 10.0
    bottom_thickness = 2.0
    wall_thickness = 2.0
    corner_radius = 20.0
    outer_fillet_radius = 3.0
    inner_fillet_radius = 1.5
    hole_radius = 1.5
    hole_offset_x = 13.0
    hole_offset_y = 11.0

    print("[2/5] Creating filleted bottom shell WITHOUT holes (Blender preview)...")
    shell_no_holes = create_filleted_shell_blender(
        name="FilletedShell_NoHoles",
        width=width,
        depth=depth,
        outer_height=outer_height,
        bottom_thickness=bottom_thickness,
        wall_thickness=wall_thickness,
        corner_radius=corner_radius,
        outer_fillet_radius=outer_fillet_radius,
        inner_fillet_radius=inner_fillet_radius,
        location=(-60, 0, 0),
        segments=32,
        step_height=1.0
    )
    add_material(shell_no_holes, name="ShellNoHolesMaterial")
    print(f"  [OK] Filleted bottom shell (no holes) created")

    print("[3/5] Creating filleted bottom shell WITH holes (Blender preview)...")
    shell_with_holes = create_filleted_shell_blender(
        name="FilletedShell_WithHoles",
        width=width,
        depth=depth,
        outer_height=outer_height,
        bottom_thickness=bottom_thickness,
        wall_thickness=wall_thickness,
        corner_radius=corner_radius,
        outer_fillet_radius=outer_fillet_radius,
        inner_fillet_radius=inner_fillet_radius,
        location=(60, 0, 0),
        segments=32,
        step_height=1.0,
        holes=(hole_radius, hole_offset_x, hole_offset_y),
    )
    add_material(shell_with_holes, name="ShellWithHolesMaterial")
    print(f"  [OK] Filleted bottom shell (with holes) created")

    for area in bpy.context.screen.areas:
        if area.type == 'VIEW_3D':
            for space in area.spaces:
                if space.type == 'VIEW_3D':
                    space.shading.type = 'SOLID'
                    space.overlay.show_wireframes = False

    print("[4/5] Measuring fillet radii from mesh...")
    measured_outer, measured_inner = measure_shell_fillet_radii(shell_no_holes)

    if measured_outer is not None:
        outer_fillet_radius = measured_outer
        print(f"  [OK] Measured outer fillet radius: {outer_fillet_radius:.3f} mm")
    else:
        print(f"  [WARN] Could not measure outer fillet, using default: {outer_fillet_radius:.3f} mm")

    if measured_inner is not None:
        inner_fillet_radius = measured_inner
        print(f"  [OK] Measured inner fillet radius: {inner_fillet_radius:.3f} mm")
    else:
        print(f"  [WARN] Could not measure inner fillet, using default: {inner_fillet_radius:.3f} mm")

    print("[5/5] Exporting parametric STEP via C++ extension...")
    script_dir = get_script_dir()
    lib_dir = os.path.abspath(os.path.join(script_dir, '..', 'lib'))
    sys.path.insert(0, lib_dir)
    os.environ['PATH'] = lib_dir + os.pathsep + os.environ.get('PATH', '')
    if hasattr(os, 'add_dll_directory'):
        os.add_dll_directory(lib_dir)

    import _step_exporter as cpp_exporter

    output_no_holes = os.path.join(script_dir, 'bottom_shell_filleted.step')
    result1 = cpp_exporter.export_bottom_shell_filleted_step(
        output_no_holes,
        width, depth, outer_height,
        bottom_thickness, wall_thickness, corner_radius,
        outer_fillet_radius, inner_fillet_radius,
        1.0,
        0.0, 0.0, 0.0,  # pos_x, pos_y, pos_z
        "AP214IS",
        "MILLIMETER",
        1,
    )
    if result1:
        print(f"  [OK] Filleted bottom shell (no holes) -> {output_no_holes}")
    else:
        print(f"  [FAIL] Filleted bottom shell (no holes) export failed")

    output_with_holes = os.path.join(script_dir, 'bottom_shell_filleted_with_holes.step')
    result2 = cpp_exporter.export_bottom_shell_filleted_with_holes_step(
        output_with_holes,
        width, depth, outer_height,
        bottom_thickness, wall_thickness, corner_radius,
        outer_fillet_radius, inner_fillet_radius,
        1.0,
        hole_radius, hole_offset_x, hole_offset_y,
        0.0, 0.0, 0.0,  # pos_x, pos_y, pos_z
        "AP214IS",
        "MILLIMETER",
        1,
    )
    if result2:
        print(f"  [OK] Filleted bottom shell (with holes) -> {output_with_holes}")
    else:
        print(f"  [FAIL] Filleted bottom shell (with holes) export failed")

    print("\n" + "="*60)
    print("[OK] Both filleted bottom shells created and exported!")
    print("="*60)


if __name__ == "__main__":
    try:
        create_filleted_bottom_shells_with_holes_scene()
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()