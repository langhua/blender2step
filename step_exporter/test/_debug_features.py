"""Debug: check chamfer/fillet detection values"""
import bpy, importlib, os, sys, bmesh, math
from collections import defaultdict

sys.path.insert(0, r'f:\git\blender2step')
import step_exporter.__init__ as init_mod
importlib.reload(init_mod)

ctx = bpy.context
targets = ['Cylinder_Chamfer_45deg', 'Cylinder_Fillet_Top', 'Cylinder_Fillet_Small', 'Cylinder_Tapered_Fillet_Chamfer', 'Cylinder_Tapered_Hollow_Chamfer']

for name in targets:
    obj = bpy.context.scene.objects.get(name)
    if not obj:
        continue
    print(f'\n=== {name} ===')
    
    bm = bmesh.new()
    depsgraph = ctx.evaluated_depsgraph_get()
    eval_obj = obj.evaluated_get(depsgraph)
    bm.from_mesh(eval_obj.data)
    bm.verts.ensure_lookup_table()
    
    z_layers = defaultdict(list)
    for v in bm.verts:
        z_key = round(v.co.z / 0.05) * 0.05
        z_layers[z_key].append((v.co.x, v.co.y))
    
    sorted_z = sorted(z_layers.keys())
    sorted_z = [zl for zl in sorted_z if len(z_layers[zl]) >= 4]
    
    height = sorted_z[-1] - sorted_z[0]
    bottom_pts = z_layers[sorted_z[0]]
    cx = sum(p[0] for p in bottom_pts) / len(bottom_pts)
    cy = sum(p[1] for p in bottom_pts) / len(bottom_pts)
    
    # Compute outer radii per level
    level_data = []
    for zl in sorted_z:
        pts = z_layers[zl]
        radii = [math.sqrt((p[0]-cx)**2 + (p[1]-cy)**2) for p in pts]
        n = len(radii)
        sorted_r = sorted(radii)
        outer_r = sum(sorted_r[n - n//4:]) / max(1, n//4)
        level_data.append((zl, outer_r))
    
    # Check if middle 60% has constant radius
    mid_start = int(len(level_data) * 0.2)
    mid_end = int(len(level_data) * 0.8)
    mid_radii = [level_data[i][1] for i in range(mid_start, mid_end)]
    mid_min = min(mid_radii)
    mid_max = max(mid_radii)
    radius_spread = mid_max - mid_min
    print(f'  Middle region ({mid_start}-{mid_end}): r=[{mid_min:.3f}, {mid_max:.3f}], spread={radius_spread:.3f}')
    is_cyl_body = radius_spread < mid_max * 0.03
    print(f'  Is cylinder body: {is_cyl_body}')
    
    # Top analysis
    top_start = sorted_z[-1] - 0.2 * height
    top_zls = [zl for zl in sorted_z if zl >= top_start]
    top_rps = [(zl, level_data[[ld[0] for ld in level_data].index(zl)][1]) if zl in [ld[0] for ld in level_data] else (zl, 0) for zl in top_zls]
    
    # Rebuild more carefully
    top_levels = [(zl, ld[1]) for ld in level_data if ld[0] >= top_start]
    
    print(f'  Top region: {len(top_levels)} levels, z=[{top_levels[0][0]:.1f}..{top_levels[-1][0]:.1f}]')
    print(f'  First/last r: {top_levels[0][1]:.3f} -> {top_levels[-1][1]:.3f}, dr={top_levels[-1][1]-top_levels[0][1]:.3f}')
    
    if len(top_levels) >= 5:
        slopes = []
        for i in range(1, len(top_levels)):
            dz = top_levels[i][0] - top_levels[i-1][0]
            dr = top_levels[i][1] - top_levels[i-1][1]
            if dz > 0.001:
                slopes.append(dr/dz)
        if len(slopes) >= 3:
            accels = [slopes[j] - slopes[j-1] for j in range(1, len(slopes))]
            avg_accel = sum(abs(a) for a in accels) / len(accels)
            avg_slope = abs(sum(slopes) / len(slopes))
            print(f'  Slopes: {[f"{s:.3f}" for s in slopes]}')
            print(f'  Accels: {[f"{a:.3f}" for a in accels]}')
            print(f'  avg_slope={avg_slope:.3f}, avg_accel={avg_accel:.3f}, ratio={avg_accel/(avg_slope+0.001):.3f}')
            threshold = avg_slope * 0.25
            print(f'  threshold (0.25*slope)={threshold:.3f}, accel<threshold? {avg_accel < threshold}')
    
    bm.free()
print('\nDone!')