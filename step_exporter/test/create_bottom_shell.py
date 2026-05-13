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


def clear_scene():
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)

    for data_block in list(bpy.data.meshes):
        if data_block.users == 0:
            bpy.data.meshes.remove(data_block)


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
        cyl_z = location[2] - hh - 0.05
        cyl_height = bottom_thickness + 0.1

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

        if len(cyl_objs) > 1:
            bpy.context.view_layer.objects.active = cyl_objs[0]
            bpy.ops.object.select_all(action='DESELECT')
            for c in cyl_objs:
                c.select_set(True)
            bpy.ops.object.join()
            cyl_objs = [bpy.context.active_object]

        apply_boolean(inner, cyl_objs[0], operation='UNION')
        bpy.data.objects.remove(cyl_objs[0], do_unlink=True)

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
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lib'))
    os.environ['PATH'] = os.path.join(os.path.dirname(__file__), '..', 'lib') + os.pathsep + os.environ.get('PATH', '')
    if hasattr(os, 'add_dll_directory'):
        os.add_dll_directory(os.path.join(os.path.dirname(__file__), '..', 'lib'))

    import _step_exporter as cpp_exporter

    output_no_holes = os.path.join(os.path.dirname(__file__), 'bottom_shell_no_holes.step')
    result1 = cpp_exporter.export_rounded_box_step(
        output_no_holes,
        width, depth, outer_height,
        bottom_thickness, wall_thickness, corner_radius,
    )
    if result1:
        print(f"  [OK] Bottom shell (no holes) -> {output_no_holes}")
    else:
        print(f"  [FAIL] Bottom shell (no holes) export failed")

    output_with_holes = os.path.join(os.path.dirname(__file__), 'bottom_shell_with_holes.step')
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


if __name__ == "__main__":
    try:
        create_both_bottom_shells_scene()
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()