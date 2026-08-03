import bpy, io, traceback
LOG = r"f:\git\blender2step\_rim_measure.txt"
out = []
try:
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)

    results = []
    for corner in ('curved', 'rounded'):
        bpy.ops.object.select_all(action='DESELECT')
        bpy.ops.step_exporter.create_parametric_shell(
            corner_type=corner, width=100.0, depth=80.0, height=50.0,
            thickness=2.0, bottom_thickness=2.0, corner_radius=5.0, bottom_fillet=0.0,
            rim_type='outside', rim_width=1.0, rim_height=1.0,
            rim_shape='rect', rim_top_ratio=100.0,
            curve_ratio=50.0, curve_ratio_y=50.0, eccentric_y=0.0, unit='mm')
        obj = [o for o in bpy.data.objects if o.get('object_type') == 'parametric_shell'][-1]
        S = 0.001
        vs = [(v.co.x/S, v.co.y/S, v.co.z/S) for v in obj.data.vertices]
        zmax = max(v[2] for v in vs)
        rim_top = max((v[2] for v in vs if 48.8 <= v[0] <= 50.4 and -38 <= v[1] <= 38), default=None)
        shelf_top = max((v[2] for v in vs if 46.5 <= v[0] <= 48.5 and -38 <= v[1] <= 38), default=None)
        edge = sorted(set(round(v[2],3) for v in vs if 48.8 <= v[0] <= 50.4 and -38 <= v[1] <= 38 and v[2] > 45))
        results.append(f"{corner}: zmax={zmax:.3f} rim_top={rim_top} shelf_top={shelf_top}")
        results.append(f"  outer-edge z>45: {edge}")
    out = results
except Exception:
    out = ["ERROR:\n" + traceback.format_exc()]

with io.open(LOG,'w',encoding='utf-8') as f:
    f.write('\n'.join(out))
print("WROTE", LOG)
