#!/usr/bin/env python3
# -*- coding: utf-8 -*-

filepath = r"f:\git\blender2step\step_exporter\test\create_bottom_shell.py"

with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

# Change FAST back to EXACT
content = content.replace("mod.solver = 'FAST'", "mod.solver = 'EXACT'")

# Remove normals_make_consistent from apply_boolean
old_block = """    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.mesh.remove_doubles(threshold=0.0001)
    bpy.ops.mesh.normals_make_consistent(inside=False)
    bpy.ops.object.mode_set(mode='OBJECT')"""

new_block = """    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.mesh.remove_doubles(threshold=0.0001)
    bpy.ops.object.mode_set(mode='OBJECT')"""

content = content.replace(old_block, new_block)

# Now replace the create_hollow_shell_blender function
# Find the function and replace it
old_func = '''def create_hollow_shell_blender(name, width, depth, outer_height, bottom_thickness,
                                   wall_thickness, corner_radius, location, segments=32,
                                   holes=None):
    """在Blender中创建中空底壳：先切孔，再挖空内腔"""
    outer = create_rounded_box(
        name=f"{name}_Outer",
        width=width,
        depth=depth,
        height=outer_height,
        corner_radius=corner_radius,
        segments=segments
    )
    outer.location = location

    if holes:
        hole_radius, hole_offset_x, hole_offset_y = holes
        hw = width / 2.0
        hd = depth / 2.0
        hole_cx = hw - hole_offset_x
        hole_cy = hd - hole_offset_y
        corner_positions = [
            ( hole_cx,  hole_cy),
            (-hole_cx,  hole_cy),
            (-hole_cx, -hole_cy),
            ( hole_cx, -hole_cy),
        ]
        cyl_height = outer_height * 2.0
        cyl_objs = []
        for i, (cx, cy) in enumerate(corner_positions):
            bpy.ops.mesh.primitive_cylinder_add(
                vertices=64,
                radius=hole_radius,
                depth=cyl_height,
                location=(location[0] + cx, location[1] + cy, location[2]),
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

        apply_boolean(outer, cyl_objs[0], operation='DIFFERENCE')
        bpy.data.objects.remove(cyl_objs[0], do_unlink=True)

    inner_width = width - 2 * wall_thickness
    inner_depth = depth - 2 * wall_thickness
    inner_height = outer_height - bottom_thickness + 1.0
    inner_corner_r = max(corner_radius - wall_thickness, 1.0)

    inner = create_rounded_box(
        name=f"{name}_Inner",
        width=inner_width,
        depth=inner_depth,
        height=inner_height,
        corner_radius=inner_corner_r,
        segments=segments
    )
    inner_z = location[2] - outer_height / 2.0 + bottom_thickness + inner_height / 2.0
    inner.location = (location[0], location[1], inner_z)

    apply_boolean(outer, inner, operation='DIFFERENCE')
    bpy.data.objects.remove(inner, do_unlink=True)

    outer.name = name
    return outer'''

new_func = '''def create_hollow_shell_blender(name, width, depth, outer_height, bottom_thickness,
                                   wall_thickness, corner_radius, location, segments=32,
                                   holes=None):
    """在Blender中创建中空底壳：先切孔，再挖空内腔（内腔也切孔避免孔壁被移除）"""
    outer = create_rounded_box(
        name=f"{name}_Outer",
        width=width,
        depth=depth,
        height=outer_height,
        corner_radius=corner_radius,
        segments=segments
    )
    outer.location = location

    cyl_height = outer_height * 2.0
    cyl_objs = None

    if holes:
        hole_radius, hole_offset_x, hole_offset_y = holes
        hw = width / 2.0
        hd = depth / 2.0
        hole_cx = hw - hole_offset_x
        hole_cy = hd - hole_offset_y
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
                location=(location[0] + cx, location[1] + cy, location[2]),
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

        apply_boolean(outer, cyl_objs[0], operation='DIFFERENCE')

    inner_width = width - 2 * wall_thickness
    inner_depth = depth - 2 * wall_thickness
    inner_height = outer_height - bottom_thickness + 1.0
    inner_corner_r = max(corner_radius - wall_thickness, 1.0)

    inner = create_rounded_box(
        name=f"{name}_Inner",
        width=inner_width,
        depth=inner_depth,
        height=inner_height,
        corner_radius=inner_corner_r,
        segments=segments
    )
    inner_z = location[2] - outer_height / 2.0 + bottom_thickness + inner_height / 2.0
    inner.location = (location[0], location[1], inner_z)

    if holes and cyl_objs:
        apply_boolean(inner, cyl_objs[0], operation='DIFFERENCE')
        bpy.data.objects.remove(cyl_objs[0], do_unlink=True

    apply_boolean(outer, inner, operation='DIFFERENCE')
    bpy.data.objects.remove(inner, do_unlink=True)

    outer.name = name
    return outer'''

content = content.replace(old_func, new_func)

with open(filepath, 'w', encoding='utf-8', newline='') as f:
    f.write(content)

print("Done! Inner box also gets holes cut before subtraction")