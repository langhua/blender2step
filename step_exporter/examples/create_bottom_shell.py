#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Bottom shell generator using shared profile_utils.
Creates a filleted open-top shell with rounded corners.
"""

import bpy
import bmesh
import math
import sys
import os

try:
    from step_exporter.core.profile_utils import make_profile
except ImportError:
    # Fallback inline definition
    def make_profile(hw, hd, cr_val, segments):
        n = segments
        rhw, rhd = hw, hd
        cc = [(-rhw+cr_val, -rhd+cr_val), (rhw-cr_val, -rhd+cr_val),
              (rhw-cr_val, rhd-cr_val), (-rhw+cr_val, rhd-cr_val)]
        pts = []
        for i in range(1, n+1):
            y = -rhd + cr_val + (2*(rhd-cr_val))*i/n; pts.append((rhw, y))
        cx, cy = cc[2]
        for j in range(1, n+1):
            a = j*(math.pi/2)/n; pts.append((cx+cr_val*math.cos(a), cy+cr_val*math.sin(a)))
        for i in range(1, n+1):
            x = rhw-cr_val-(2*(rhw-cr_val))*i/n; pts.append((x, rhd))
        cx, cy = cc[3]
        for j in range(1, n+1):
            a = math.pi/2+j*(math.pi/2)/n; pts.append((cx+cr_val*math.cos(a), cy+cr_val*math.sin(a)))
        for i in range(1, n+1):
            y = rhd-cr_val-(2*(rhd-cr_val))*i/n; pts.append((-rhw, y))
        cx, cy = cc[0]
        for j in range(1, n+1):
            a = math.pi+j*(math.pi/2)/n; pts.append((cx+cr_val*math.cos(a), cy+cr_val*math.sin(a)))
        for i in range(1, n+1):
            x = -rhw+cr_val+(2*(rhw-cr_val))*i/n; pts.append((x, -rhd))
        cx, cy = cc[1]
        for j in range(1, n+1):
            a = 3*math.pi/2+j*(math.pi/2)/n; pts.append((cx+cr_val*math.cos(a), cy+cr_val*math.sin(a)))
        return pts


def create_filleted_shell_blender(name, width, depth, outer_height,
                                   bottom_thickness, wall_thickness,
                                   corner_radius, outer_fillet_radius,
                                   inner_fillet_radius, location=(0, 0, 0),
                                   segments=32, step_height=1.0, holes=None):
    """Create a filleted bottom shell using profile-based arc-ring construction."""
    hw = width / 2.0
    hd = depth / 2.0
    hh = outer_height / 2.0
    max_radius = min(hw, hd) * 0.99
    corner_radius = min(corner_radius, max_radius)

    # Profiles
    outer_profile = make_profile(hw, hd, corner_radius, segments)
    inner_wall_hw = hw - wall_thickness
    inner_wall_hd = hd - wall_thickness
    inner_wall_cr = max(corner_radius - wall_thickness, 1.0)
    inner_profile = make_profile(inner_wall_hw, inner_wall_hd, inner_wall_cr, segments)

    # Mid profile (two-level step)
    mid_hw = hw - 1.0
    mid_hd = hd - 1.0
    mid_cr = max(corner_radius - 1.0, 1.0)
    mid_profile = make_profile(mid_hw, mid_hd, mid_cr, segments)

    num_profile = len(outer_profile)
    outer_bottom_z = -hh
    outer_top_z = hh - step_height
    inner_bottom_z = -hh + bottom_thickness
    inner_top_z = hh

    me = bpy.data.meshes.new(name=name)
    bm = bmesh.new()

    fillet_segments = 16

    # --- Outer bottom + fillet rings ---
    outer_bot_hw = hw - outer_fillet_radius
    outer_bot_hd = hd - outer_fillet_radius
    outer_bot_cr = max(corner_radius - outer_fillet_radius, 0.0)
    outer_bottom_pts = make_profile(outer_bot_hw, outer_bot_hd, outer_bot_cr, segments)
    outer_bottom_v = [bm.verts.new((x, y, outer_bottom_z)) for x, y in outer_bottom_pts]
    bm.faces.new(list(reversed(outer_bottom_v)))

    fillet_layers = []
    outer_prev = outer_bottom_v
    r_bot_o = max(corner_radius - outer_fillet_radius, 0.0)
    for seg_idx in range(1, fillet_segments + 1):
        frac = seg_idx / fillet_segments
        ang = math.pi / 2.0 * frac
        sin_a = math.sin(ang)
        rise = outer_fillet_radius * (1.0 - math.cos(ang))
        ring_cr = r_bot_o + (corner_radius - r_bot_o) * sin_a
        ring_off = outer_fillet_radius * (1.0 - sin_a)
        ring_pts = make_profile(hw - ring_off, hd - ring_off, ring_cr, segments)
        layer_v = [bm.verts.new((x, y, outer_bottom_z + rise)) for x, y in ring_pts]
        for i in range(num_profile):
            j = (i + 1) % num_profile
            bm.faces.new([outer_prev[i], outer_prev[j], layer_v[j], layer_v[i]])
        outer_prev = layer_v
        fillet_layers.append(layer_v)

    # Outer wall to top
    outer_top_v = [bm.verts.new((x, y, outer_top_z)) for x, y in outer_profile]
    for i in range(num_profile):
        j = (i + 1) % num_profile
        bm.faces.new([outer_prev[i], outer_prev[j], outer_top_v[j], outer_top_v[i]])

    # --- Inner bottom + fillet rings ---
    inner_bot_hw = inner_wall_hw - inner_fillet_radius
    inner_bot_hd = inner_wall_hd - inner_fillet_radius
    inner_bot_cr = max(inner_wall_cr - inner_fillet_radius, 0.0)
    inner_bottom_pts = make_profile(inner_bot_hw, inner_bot_hd, inner_bot_cr, segments)
    inner_bottom_v = [bm.verts.new((x, y, inner_bottom_z)) for x, y in inner_bottom_pts]
    bm.faces.new(inner_bottom_v)

    inner_fillet_layers = []
    inner_prev = inner_bottom_v
    r_bot_i = max(inner_wall_cr - inner_fillet_radius, 0.0)
    for seg_idx in range(1, fillet_segments + 1):
        frac = seg_idx / fillet_segments
        ang = math.pi / 2.0 * frac
        sin_a = math.sin(ang)
        rise = inner_fillet_radius * (1.0 - math.cos(ang))
        ring_cr = r_bot_i + (inner_wall_cr - r_bot_i) * sin_a
        ring_off = inner_fillet_radius * (1.0 - sin_a)
        ring_pts = make_profile(inner_wall_hw - ring_off, inner_wall_hd - ring_off, ring_cr, segments)
        layer_v = [bm.verts.new((x, y, inner_bottom_z + rise)) for x, y in ring_pts]
        for i in range(num_profile):
            j = (i + 1) % num_profile
            bm.faces.new([inner_prev[i], inner_prev[j], layer_v[j], layer_v[i]])
        inner_prev = layer_v
        inner_fillet_layers.append(layer_v)

    # Inner wall to top
    inner_top_v = [bm.verts.new((x, y, inner_top_z)) for x, y in inner_profile]
    for i in range(num_profile):
        j = (i + 1) % num_profile
        bm.faces.new([inner_prev[i], inner_prev[j], inner_top_v[j], inner_top_v[i]])

    # Two-level step faces
    mid_outer_v = [bm.verts.new((x, y, outer_top_z)) for x, y in mid_profile]
    mid_inner_v = [bm.verts.new((x, y, inner_top_z)) for x, y in mid_profile]
    for i in range(num_profile):
        j = (i + 1) % num_profile
        bm.faces.new([outer_top_v[i], outer_top_v[j], mid_outer_v[j], mid_outer_v[i]])
    for i in range(num_profile):
        j = (i + 1) % num_profile
        bm.faces.new([mid_outer_v[i], mid_outer_v[j], mid_inner_v[j], mid_inner_v[i]])
    for i in range(num_profile):
        j = (i + 1) % num_profile
        bm.faces.new([mid_inner_v[i], mid_inner_v[j], inner_top_v[j], inner_top_v[i]])

    bm.to_mesh(me)
    bm.free()

    obj = bpy.data.objects.new(name, me)
    bpy.context.collection.objects.link(obj)
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    obj.location = location
    # Tag for STEP export: both use bottom_shell for two-level step support
    obj['object_type'] = 'bottom_shell'
    obj['_params_from_props'] = True
    obj['width'] = width
    obj['depth'] = depth
    obj['outer_height'] = outer_height
    obj['bottom_thickness'] = bottom_thickness
    obj['wall_thickness'] = wall_thickness
    obj['corner_radius'] = corner_radius
    obj['outer_fillet_radius'] = outer_fillet_radius
    obj['inner_fillet_radius'] = inner_fillet_radius
    obj['step_height'] = step_height
    if holes:
        obj['has_holes'] = True
        obj['hole_radius'] = holes[0]
        obj['hole_offset_x'] = holes[1]
        obj['hole_offset_y'] = holes[2]
    else:
        obj['has_holes'] = False
    # Recalculate normals + flat shading
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.mesh.normals_make_consistent(inside=False)
    bpy.ops.object.mode_set(mode='OBJECT')
    bpy.ops.object.shade_flat()

    # Optional corner holes
    if holes:
        hole_radius, hole_offset_x, hole_offset_y = holes
        hole_cx = hw - hole_offset_x
        hole_cy = hd - hole_offset_y
        cyl_z_bottom = location[2] - hh - 1.0
        cyl_z_top = location[2] + hh + 2.0
        cyl_height = cyl_z_top - cyl_z_bottom
        cyl_z = (cyl_z_top + cyl_z_bottom) / 2.0
        corner_positions = [
            (hole_cx, hole_cy), (-hole_cx, hole_cy),
            (-hole_cx, -hole_cy), (hole_cx, -hole_cy),
        ]
        for i, (cx, cy) in enumerate(corner_positions):
            bpy.ops.mesh.primitive_cylinder_add(
                vertices=64, radius=hole_radius, depth=cyl_height,
                location=(location[0] + cx, location[1] + cy, cyl_z),
            )
            cyl_obj = bpy.context.active_object
            cyl_obj.hide_viewport = True
            mod = obj.modifiers.new(name=f"Boolean_Hole_{i}", type='BOOLEAN')
            mod.operation = 'DIFFERENCE'
            mod.solver = 'EXACT'
            mod.object = cyl_obj
            bpy.context.view_layer.objects.active = obj
            bpy.ops.object.modifier_apply(modifier=mod.name)
            bpy.data.objects.remove(cyl_obj, do_unlink=True)

    return obj


def create_filleted_bottom_shells_scene():
    """Create 2 filleted bottom shells: plain (high-res) + with holes (lower-res for mesh export)."""
    # Plain shell: high resolution for Blender preview
    create_filleted_shell_blender(
        "Shell_R10_F10x10", 100, 80, 30, 2, 2, 10, 10, 8,
        (-80, 50, 0), segments=64)
    # Hole version: lower resolution so mesh-to-STEP doesn't hang
    create_filleted_shell_blender(
        "Shell_Holes", 100, 80, 30, 2, 2, 10, 10, 8,
        (80, 50, 0), segments=16, holes=(3.0, 15.0, 15.0))
    print("Created 2 filleted bottom shells.")


def create_filleted_bottom_shells_with_holes_scene():
    """Create filleted bottom shells with corner holes."""
    create_filleted_shell_blender(
        "Shell_Holes", 100, 80, 30, 2, 2,
        5, 10, 8, (0, 0, 0), segments=32,
        holes=(3.0, 15.0, 15.0))
    print("Created filleted bottom shell with corner holes.")


if __name__ == "__main__":
    if len(sys.argv) > 1 and "with_holes" in sys.argv:
        create_filleted_bottom_shells_with_holes_scene()
    elif len(sys.argv) > 1 and "gallery" in sys.argv:
        create_filleted_bottom_shells_scene()
    else:
        # Default: create both
        create_filleted_bottom_shells_scene()
