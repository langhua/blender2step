"""Shared trapezoidal groove utilities for cylinder, cone, and inverted cone galleries.

Usage:
    from groove_utils import add_trapezoidal_groove, apply_groove, GRV_DEPTH, GRV_TOP_W

    # Cylinder: pass bot_r only, top_r defaults to bot_r
    add_trapezoidal_groove(obj, bot_r=R)

    # Cone: pass both radii
    add_trapezoidal_groove(obj, bot_r=0.5, top_r=0.25)

    # Apply and clean up after all modifiers are ready
    apply_groove(obj)
"""

import math
import bpy

# Trapezoidal groove parameters
GRV_DEPTH = 0.06
GRV_TOP_W = 0.08
GRV_ANGLE = math.radians(45)


def add_trapezoidal_groove(obj, bot_r, top_r=None, *,
                           depth=GRV_DEPTH, top_width=GRV_TOP_W, angle=GRV_ANGLE):
    """Add a trapezoidal groove Boolean cutter to the given mesh object.

    Works for both cylinders (pass bot_r only) and cones (pass bot_r + top_r).
    The groove is a through-slot in Y direction with 45° trapezoidal profile in XZ.

    Args:
        obj: Blender mesh object to add groove to.
        bot_r: Bottom radius in meters.
        top_r: Top radius in meters (None = cylinder, uses bot_r for both).
        depth: Groove depth in meters (default GRV_DEPTH).
        top_width: Groove opening width at surface (default GRV_TOP_W).
        angle: Side wall angle in radians (default GRV_ANGLE = 45°).
    """
    if top_r is None:
        top_r = bot_r  # cylinder

    max_r = max(bot_r, top_r)
    r_cone_mid = (bot_r + top_r) / 2.0

    # Groove floor: at depth from the middle-height radius
    r_floor = r_cone_mid - depth
    # Groove surface: just outside the widest part of the shape
    r_surface = max_r + 0.01

    # Follow cylinder gallery pattern: bot_w from actual cutter_span for correct angle
    cutter_span = r_surface - r_floor
    bot_w = top_width + 2.0 * cutter_span * math.tan(angle)
    hb = bot_w / 2.0      # wide opening at surface (X+)
    ht = top_width / 2.0  # narrow at floor (X-)

    ext_len = 2.0 * max_r + 0.04  # through entire diameter + margin
    half_ext = ext_len / 2.0

    cx = obj.location.x
    cy = obj.location.y
    cz = obj.location.z

    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(cx, cy, cz))
    cutter = bpy.context.active_object
    cutter.name = f"GCUT_{obj.name}"
    cutter.hide_render = True

    bpy.ops.object.mode_set(mode='EDIT')
    import bmesh
    bm = bmesh.from_edit_mesh(cutter.data)
    for v in bm.verts:
        x_sign = 1 if v.co.x > 0 else -1
        y_sign = 1 if v.co.y > 0 else -1
        z_sign = 1 if v.co.z > 0 else -1
        v.co = (
            r_surface if x_sign > 0 else r_floor,
            half_ext if y_sign > 0 else -half_ext,
            hb if x_sign > 0 and z_sign > 0 else      # surface = wide opening
            -hb if x_sign > 0 and z_sign < 0 else
            ht if z_sign > 0 else -ht                  # floor = narrow
        )
    bmesh.update_edit_mesh(cutter.data)
    bpy.ops.object.mode_set(mode='OBJECT')

    mod = obj.modifiers.new(name="Groove", type='BOOLEAN')
    mod.object = cutter
    mod.operation = 'DIFFERENCE'
    mod.solver = 'EXACT'

    # Store groove params for STEP export (mm convention)
    obj['step_groove_depth'] = depth * 1000
    obj['step_groove_bottom_width'] = bot_w * 1000
    obj['step_groove_top_width'] = top_width * 1000
    obj['step_groove_extrusion_length'] = ext_len * 1000


def apply_groove(obj):
    """Apply the Groove modifier and clean up mesh + cutter object."""
    bpy.context.view_layer.objects.active = obj
    for mod in obj.modifiers:
        if mod.name == "Groove" and mod.type == 'BOOLEAN':
            cutter = mod.object
            bpy.ops.object.modifier_apply(modifier="Groove")
            if cutter:
                bpy.data.objects.remove(cutter, do_unlink=True)
            break
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.mesh.remove_doubles(threshold=0.0001)
    bpy.ops.mesh.delete_loose()
    bpy.ops.mesh.normals_make_consistent(inside=False)
    bpy.ops.object.mode_set(mode='OBJECT')
