"""
Create a simple rectangular box without lid (open-top box).
Default: 100×80×50 mm, wall thickness 2 mm.

Run this script directly in Blender to generate the box.
"""
import bpy
import bmesh
import math

# ── Default Parameters ────────────────────────────────────
WIDTH = 100.0       # mm, X direction
DEPTH = 80.0        # mm, Y direction
HEIGHT = 50.0       # mm, Z direction
THICKNESS = 2.0     # mm, wall thickness
CENTER = (0, 0, 0)  # center of the base


def create_rect_box(name="RectBox", width=WIDTH, depth=DEPTH, height=HEIGHT,
                    thickness=THICKNESS, center=CENTER):
    """
    Create an open-top rectangular box using bmesh.
    Returns the created Blender object.
    """
    bm = bmesh.new()

    cx, cy, cz = center
    hw, hd, hh = width / 2.0, depth / 2.0, height

    # ── Outer shell (bottom + 4 walls) ──
    # Outer vertices (8 corners of the full box, then remove top face)
    outer_verts = [
        bm.verts.new((cx - hw, cy - hd, cz)),           # 0: bottom-FL
        bm.verts.new((cx + hw, cy - hd, cz)),           # 1: bottom-FR
        bm.verts.new((cx + hw, cy + hd, cz)),           # 2: bottom-BR
        bm.verts.new((cx - hw, cy + hd, cz)),           # 3: bottom-BL
        bm.verts.new((cx - hw, cy - hd, cz + hh)),      # 4: top-FL
        bm.verts.new((cx + hw, cy - hd, cz + hh)),      # 5: top-FR
        bm.verts.new((cx + hw, cy + hd, cz + hh)),      # 6: top-BR
        bm.verts.new((cx - hw, cy + hd, cz + hh)),      # 7: top-BL
    ]

    # Inner vertices (offset inward by thickness, bottom z offset up by thickness)
    th = thickness
    iv = [
        bm.verts.new((cx - hw + th, cy - hd + th, cz + th)),     # 8
        bm.verts.new((cx + hw - th, cy - hd + th, cz + th)),     # 9
        bm.verts.new((cx + hw - th, cy + hd - th, cz + th)),     # 10
        bm.verts.new((cx - hw + th, cy + hd - th, cz + th)),     # 11
        bm.verts.new((cx - hw + th, cy - hd + th, cz + hh)),     # 12
        bm.verts.new((cx + hw - th, cy - hd + th, cz + hh)),     # 13
        bm.verts.new((cx + hw - th, cy + hd - th, cz + hh)),     # 14
        bm.verts.new((cx - hw + th, cy + hd - th, cz + hh)),     # 15
    ]

    bm.verts.ensure_lookup_table()

    def face(vi):
        return bm.faces.new([bm.verts[i] for i in vi])

    # Outer faces (bottom, 4 walls)
    face([0, 1, 2, 3])   # bottom
    face([0, 4, 5, 1])   # front wall
    face([1, 5, 6, 2])   # right wall
    face([2, 6, 7, 3])   # back wall
    face([3, 7, 4, 0])   # left wall
    # No top face (open)

    # Inner faces (bottom, 4 walls, no top)
    face([8, 11, 10, 9])  # inner bottom
    face([12, 8, 9, 13])  # inner front
    face([13, 9, 10, 14]) # inner right
    face([14, 10, 11, 15])# inner back
    face([15, 11, 8, 12]) # inner left

    # Top rim (connect outer top to inner top)
    face([4, 12, 15, 7])  # left rim
    face([7, 15, 14, 6])  # back rim
    face([6, 14, 13, 5])  # right rim
    face([5, 13, 12, 4])  # front rim

    # Recalculate normals
    bm.normal_update()

    # Create mesh and object
    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()

    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)

    # Store parameters as custom properties
    obj['width'] = width
    obj['depth'] = depth
    obj['height'] = height
    obj['wall_thickness'] = thickness
    obj['object_type'] = 'rect_box'

    return obj


if __name__ == '__main__':
    create_rect_box()
    print("[RectBox] Created: 100×80×50mm, wall=2mm, open top")
