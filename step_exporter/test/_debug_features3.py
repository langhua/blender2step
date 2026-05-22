"""Quick targeted debug for the problematic objects"""
import bpy, importlib, os, sys, math, bmesh
from collections import defaultdict

sys.path.insert(0, r'f:\git\blender2step')
import step_exporter.__init__ as init_mod
importlib.reload(init_mod)

ctx = bpy.context
for obj in ctx.scene.objects:
    if obj.name not in ['Cylinder_Chamfer_45deg', 'Cylinder_Fillet_Top', 'Cylinder_Tapered_Fillet_Chamfer']:
        continue
    if obj.type != 'MESH':
        continue
    
    print(f'\n=== {obj.name} ===')
    
    depsgraph = ctx.evaluated_depsgraph_get()
    eval_obj = obj.evaluated_get(depsgraph)
    bm = bmesh.new()
    bm.from_mesh(eval_obj.data)
    bm.verts.ensure_lookup_table()
    
    z_layers = defaultdict(list)
    for v in bm.verts:
        z_key = round(v.co.z / 0.05) * 0.05
        z_layers[z_key].append((v.co.x, v.co.y))
    
    sorted_z_all = sorted(z_layers.keys())
    sorted_z = [zl for zl in sorted_z_all if len(z_layers[zl]) >= 4]
    height = sorted_z[-1] - sorted_z[0]
    
    bottom_pts = z_layers[sorted_z[0]]
    cx = sum(p[0] for p in bottom_pts) / len(bottom_pts)
    cy = sum(p[1] for p in bottom_pts) / len(bottom_pts)
    
    def compute_radii(layer_pts):
        return [math.sqrt((p[0]-cx)**2 + (p[1]-cy)**2) for p in layer_pts]
    
    def has_two_clusters(radii_sorted):
        n = len(radii_sorted)
        if n < 16:
            return False, radii_sorted
        min_r, max_r = radii_sorted[0], radii_sorted[-1]
        if max_r - min_r < max_r * 0.15:
            return False, radii_sorted
        best_gap = 0
        best_split = n // 2
        for i in range(n // 4, 3 * n // 4):
            gap = radii_sorted[i] - radii_sorted[i - 1]
            if gap > best_gap:
                best_gap = gap
                best_split = i
        if best_gap > max_r * 0.08:
            return True, radii_sorted[best_split:]
        return False, radii_sorted
    
    def level_outer_radius(pts):
        radii = sorted(compute_radii(pts))
        n = len(radii)
        if n < 4:
            return None
        if n >= 16:
            is_cluster, outer_vals = has_two_clusters(radii)
            if is_cluster:
                return sorted(outer_vals)[len(outer_vals)//2]
        return sum(radii[n - n//4:]) / max(1, n//4)
    
    bottom_radius = level_outer_radius(z_layers[sorted_z[0]])
    top_radius = level_outer_radius(z_layers[sorted_z[-1]])
    print(f'  Height: {height:.1f}, Z: [{sorted_z[0]:.1f}, {sorted_z[-1]:.1f}]')
    print(f'  bottom_r={bottom_radius:.3f}, top_r={top_radius:.3f}')
    
    # Mid level analysis
    mid_start = sorted_z[0] + 0.2 * height
    mid_end = sorted_z[-1] - 0.2 * height
    mid_zls = [zl for zl in sorted_z if mid_start <= zl <= mid_end]
    print(f'  Mid region ({mid_start:.1f}..{mid_end:.1f}): {len(mid_zls)} levels')
    mid_radii = [level_outer_radius(z_layers[zl]) for zl in mid_zls if level_outer_radius(z_layers[zl]) is not None]
    print(f'  mid_radii: {mid_radii[:5]}...{mid_radii[-3:] if len(mid_radii)>3 else ""}')
    if mid_radii:
        mid_sorted = sorted(mid_radii)
        body_r = mid_sorted[len(mid_sorted)//2]
        mid_range = mid_sorted[-1] - mid_sorted[0]
        is_cyl = mid_range < body_r * 0.03
        print(f'  body_r={body_r:.3f}, mid_range={mid_range:.3f}, is_cyl_body={is_cyl}')
    else:
        body_r = bottom_radius
        is_cyl = False
        print(f'  body_r=bottom_radius={body_r:.3f}, NO mid levels!')
    
    # Transition search
    transition_start = len(sorted_z) - 1
    for i in range(len(sorted_z) - 2, 0, -1):
        zl = sorted_z[i]
        r = level_outer_radius(z_layers[zl])
        if r is not None:
            dev = abs(r - body_r) / max(body_r, 0.01)
            print(f'  searching z={zl:.2f}: r={r:.3f}, dev={dev:.4f}')
            if dev < 0.015:
                transition_start = i + 1
                print(f'    -> transition starts at idx {transition_start} (z={sorted_z[transition_start]:.2f})')
                break
    
    top_zls = sorted_z[transition_start:]
    print(f'  Transition zone: {len(top_zls)} levels, z=[{top_zls[0]:.2f}..{top_zls[-1]:.2f}]')
    
    if len(top_zls) >= 2:
        t_radii = [(zl, level_outer_radius(z_layers[zl])) for zl in top_zls if level_outer_radius(z_layers[zl]) is not None]
        print(f'  t_radii: {[(f"{zl:.2f}", f"{r:.3f}") for zl, r in t_radii[:5]]}...{[(f"{zl:.2f}", f"{r:.3f}") for zl, r in t_radii[-3:]]}')
        if len(t_radii) >= 2:
            top_dr = t_radii[-1][1] - t_radii[0][1]
            print(f'  top_dr={top_dr:.3f}')
            slopes = []
            for j in range(1, len(t_radii)):
                dz = t_radii[j][0] - t_radii[j-1][0]
                dr = t_radii[j][1] - t_radii[j-1][1]
                if dz > 0.0001:
                    slopes.append(dr/dz)
            print(f'  slopes: {[f"{s:.3f}" for s in slopes[:5]]}...{slopes[-3:]}')
            avg_slope = abs(sum(slopes)/len(slopes))
            print(f'  avg_slope={avg_slope:.4f}')
            if len(slopes) >= 3:
                accels = [slopes[j]-slopes[j-1] for j in range(1,len(slopes))]
                avg_accel = sum(abs(a) for a in accels) / len(accels)
                print(f'  accels: {[f"{a:.3f}" for a in accels[:5]]}...')
                print(f'  avg_accel={avg_accel:.4f}, threshold={max(avg_slope*0.3,0.05):.4f}, is_chamfer={avg_accel < max(avg_slope*0.3,0.05)}')
    
    result = init_mod._analyze_cylinder_from_mesh(obj, ctx, 1000)
    if result:
        print(f'  RESULT: {result["obj_type"]}, top={result.get("top_feature")}, bot={result.get("bottom_feature")}, '
              f'top_size={result.get("top_feature_size", 0):.3f}, bot_size={result.get("bottom_feature_size", 0):.3f}')
    
    bm.free()

print('\nDone!')