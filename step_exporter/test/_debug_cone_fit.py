"""Debug cone linear fit for tapered objects"""
import bpy, sys, importlib, bmesh, math, os
from collections import defaultdict

sys.path.insert(0, r'f:\git\blender2step')
os.environ['STEP_EXPORTER_DEBUG'] = '1'

import step_exporter.__init__ as init_mod
importlib.reload(init_mod)

ctx = bpy.context
target = 'Cylinder_Tapered_Fillet_Chamfer'

obj = ctx.scene.objects.get(target)
if not obj or obj.type != 'MESH':
    print(f'{target} not found')
    raise SystemExit

print(f'\n=== Debug {target} ===')

# Replicate z-layer analysis
depsgraph = ctx.evaluated_depsgraph_get()
bm = bmesh.new()
bm.from_object(obj, depsgraph)
bm.verts.ensure_lookup_table()

# Compute z layers
z_layers = defaultdict(list)
for v in bm.verts:
    z = round(v.co.z, 2)
    z_layers[z].append((v.co.x, v.co.y, v.co.z))
bm.free()

sorted_z = sorted(z_layers.keys())
print(f'\nTotal Z levels: {len(sorted_z)}')
print(f'Z range: {sorted_z[0]:.2f} to {sorted_z[-1]:.2f}')
height = sorted_z[-1] - sorted_z[0]
print(f'Height: {height:.2f}')

# Compute radii per layer
def compute_radii(pts):
    if len(pts) < 4: return []
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    cx = sum(xs)/len(xs)
    cy = sum(ys)/len(ys)
    return [math.hypot(p[0]-cx, p[1]-cy) for p in pts]

def has_two_clusters(vals):
    med = sorted(vals)[len(vals)//2]
    lo = [v for v in vals if v < med*0.9]
    hi = [v for v in vals if v > med*1.1]
    return len(lo) >= 4 and len(hi) >= 4, lo, hi

def _layer_outer_radius(pts):
    radii = sorted(compute_radii(pts))
    n = len(radii)
    if n < 4: return None
    if n >= 16:
        is_cluster, lo, hi = has_two_clusters(radii)
        if is_cluster:
            return sorted(hi)[len(hi)//2]
    return sum(radii[n - n//4:]) / max(1, n//4)

z_radius_data = {}
for zl in sorted_z:
    r = _layer_outer_radius(z_layers[zl])
    if r is not None:
        z_radius_data[zl] = r

print(f'\nAll 38 Z levels:')
for zl in sorted_z:
    r_str = f'{z_radius_data[zl]:.2f}' if zl in z_radius_data else 'no_data'
    print(f'  z={zl:+.2f}  r={r_str}')

valid_zls = [zl for zl in sorted_z if zl in z_radius_data]
n = len(valid_zls)
# Position-based trimming (matching updated __init__.py)
height = sorted_z[-1] - sorted_z[0]
fit_z_bottom = sorted_z[0] + height * 0.15
fit_z_top = sorted_z[-1] - height * 0.15
fit_zls = [zl for zl in valid_zls if fit_z_bottom <= zl <= fit_z_top]

print(f'\nValid levels: {n}')
print(f'Height: {height:.1f}, fit Z range: {fit_z_bottom:.1f} to {fit_z_top:.1f}')
print(f'Fit Z levels: {len(fit_zls)} (range: {fit_zls[0]:.2f} to {fit_zls[-1]:.2f})')

# Linear regression
sum_z = sum(zl for zl in fit_zls)
sum_r = sum(z_radius_data[zl] for zl in fit_zls)
sz = sum_z / len(fit_zls)
sr = sum_r / len(fit_zls)
s_zz = sum((zl - sz)*(zl - sz) for zl in fit_zls)
s_zr = sum((zl - sz)*(z_radius_data[zl] - sr) for zl in fit_zls)

a = s_zr / s_zz
b = sr - a * sz

print(f'\nFit line: r = {a:.6f}*z + {b:.4f}')
print(f'Body bottom r (z={sorted_z[0]:.1f}): {a*sorted_z[0] + b:.3f}')
print(f'Body top r (z={sorted_z[-1]:.1f}): {a*sorted_z[-1] + b:.3f}')
print(f'Actual bottom r: {z_radius_data.get(sorted_z[0], "N/A")}')
print(f'Actual top r: {z_radius_data.get(sorted_z[-1], "N/A")}')

deviation_thresh = max(abs(a) * height * 0.02 + 0.1, 0.3)
print(f'\nDeviation threshold: {deviation_thresh:.4f}')

print(f'\nTop levels (after fit):')
for zl in valid_zls:
    if zl <= fit_z_top:
        continue
    expected_r = a * zl + b
    actual_r = z_radius_data[zl]
    dev = abs(actual_r - expected_r)
    flag = ' *** DEVIATING ***' if dev > deviation_thresh else ''
    print(f'  z={zl:.2f}  expected_r={expected_r:.3f}  actual_r={actual_r:.3f}  dev={dev:.4f}{flag}')

print(f'\nBottom levels (before fit):')
for zl in valid_zls:
    if zl >= fit_z_bottom:
        continue
    expected_r = a * zl + b
    actual_r = z_radius_data[zl]
    dev = abs(actual_r - expected_r)
    flag = ' *** DEVIATING ***' if dev > deviation_thresh else ''
    print(f'  z={zl:.2f}  expected_r={expected_r:.3f}  actual_r={actual_r:.3f}  dev={dev:.4f}{flag}')

print('\nDone!')