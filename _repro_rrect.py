"""Reproduce: Blender preview (generate_parametric_shell_mesh) for rrect holes.
User reports:
1. bottom-face rrect OUTER/INNER/BOTH all show BOTH-side fillet
2. side-wall rrect shows plain rectangle (no rrect corner radius, no rim fillet)
Analyze preview mesh: bottom rim z-distribution, side wall shape.
"""
import sys, os

_lib_dir = os.path.join(os.path.dirname(__file__), 'step_exporter', 'lib')
os.add_dll_directory(_lib_dir)
sys.path.insert(0, _lib_dir)
import _step_exporter as cpp

width, depth, height = 100.0, 80.0, 50.0
thickness = 2.0
bottom_thickness = 2.0
corner_radius = 5.0
corner_type = "curved"
rim_type = "inside"
rim_width = 1.5
rim_height = 1.0
rim_shape = "rect"
rim_top_ratio = 1.0
bottom_fillet = 2.0
curve_ratio = 0.5
eccentric_y = 0.0
pos_x, pos_y, pos_z = 0.0, 0.0, 0.0
OUT = os.path.dirname(__file__)

def preview_mesh(wd):
    return cpp.generate_parametric_shell_mesh(
        width, depth, height, thickness, bottom_thickness,
        corner_type, corner_radius, rim_type, rim_width, rim_height,
        rim_shape, rim_top_ratio, bottom_fillet, curve_ratio, eccentric_y,
        wd, 64)

lines = []
# ============ BOTTOM rrect: hole (0,0,1) w=14 h=10 cr=1.5 fr=0.8 ============
print("=== BOTTOM rrect (fc=0) 0,0,1,14,2,10,1.5 ===")
for ft, lbl in [(0,'OUTER'),(1,'INNER'),(2,'BOTH'),(-1,'NONE')]:
    fr = 0.0 if ft == -1 else 0.8
    ftc = ft if ft >= 0 else 0
    wd = f"0,0,1,14,2,10,1.5,{fr},{ftc},0"
    mesh = preview_mesh(wd)
    if mesh is None:
        lines.append(f"bottom {lbl}: NO MESH")
        print(f"  {lbl}: NO MESH")
        continue
    verts = mesh['vertices']
    # bottom hole rim: x in [-7,7], y in [-5,5], classify by z
    # outer rim at z~0 (exterior bottom), inner rim at z~2 (inside)
    # fillet surface vertices appear at z between... count verts near rim outline
    def on_rrect_outline(x, y):
        hw, hh, crr = 7.0, 5.0, 1.5
        dx, dy = abs(x), abs(y)
        if dx <= hw - crr and dy <= hh: return True
        if dy <= hh - crr and dx <= hw: return True
        cdx = max(dx - (hw - crr), 0.0)
        cdy = max(dy - (hh - crr), 0.0)
        if cdx > 0 and cdy > 0:
            return abs((cdx*cdx + cdy*cdy)**0.5 - crr) < 0.3
        return False
    # find rim verts: on outline and near z=0 (outer) or z=2 (inner)
    outer = inner = mid = 0
    for (x, y, z) in verts:
        if on_rrect_outline(x, y):
            if z < 0.6: outer += 1
            elif z > 1.4: inner += 1
            else: mid += 1
    print(f"  {lbl}: outer_rim(z<0.6)={outer} inner_rim(z>1.4)={inner} mid={mid}")
    lines.append(f"bottom {lbl}: outer={outer} inner={inner} mid={mid}")

print()
print("=== SIDE rrect (fc=2) cx=45.5,0,22,12,2,8,1.5 ===")
CX = 45.5
for ft, lbl in [(0,'OUTER'),(1,'INNER'),(2,'BOTH'),(-1,'NONE')]:
    fr = 0.0 if ft == -1 else 0.8
    ftc = ft if ft >= 0 else 0
    wd = f"{CX},0,22,12,2,8,1.5,{fr},{ftc},2"
    mesh = preview_mesh(wd)
    if mesh is None:
        print(f"  {lbl}: NO MESH")
        continue
    verts = mesh['vertices']
    # rrect in YZ: w=12(Y) h=8(Z) cr=1.5, through X
    # check for rounded corners: vertex y/z distribution on the hole wall
    # wall spans x~[44.5,46.5]
    ys, zs = [], []
    for (x, y, z) in verts:
        if 44.0 <= x <= 47.0:
            ys.append(y); zs.append(z)
    # count distinct y/z to see if corners are rounded (should have y=±6, z=22±4 with corner arcs)
    import math
    # sample near hole outline in YZ
    def on_rr_outline(y, z, cy=0.0, cz=22.0):
        hw, hh, crr = 6.0, 4.0, 1.5
        dy, dz = abs(y-cy), abs(z-cz)
        if dy <= hw - crr and dz <= hh: return True
        if dz <= hh - crr and dy <= hw: return True
        cdy = max(dy - (hw - crr), 0.0)
        cdz = max(dz - (hh - crr), 0.0)
        if cdy > 0 and cdz > 0:
            return abs((cdy*cdy + cdz*cdz)**0.5 - crr) < 0.3
        return False
    outer = inner = 0
    for (x, y, z) in verts:
        if 44.0 <= x <= 47.0 and on_rr_outline(y, z):
            if x > CX: outer += 1
            else: inner += 1
    print(f"  {lbl}: side outer_rim(x>{CX})={outer} inner_rim(x<{CX})={inner}")
    lines.append(f"side {lbl}: outer={outer} inner={inner}")

lines.append("DONE")
with open(os.path.join(OUT, '_repro_rrect.txt'), 'w', encoding='utf-8') as f:
    f.write("\n".join(lines) + "\n")
