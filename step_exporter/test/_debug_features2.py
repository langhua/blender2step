"""Test chamfer/fillet detection with debug"""
import bpy, importlib, os, sys

sys.path.insert(0, r'f:\git\blender2step')
import step_exporter.__init__ as init_mod
importlib.reload(init_mod)

# Monkey-patch to add debug
orig_analyze = init_mod._analyze_cylinder_from_mesh
def patched_analyze(obj, ctx, scale):
    # Add debug before calling
    if 'Chamfer' in obj.name or 'Fillet' in obj.name:
        import bmesh, math
        from collections import defaultdict
        depsgraph = ctx.evaluated_depsgraph_get()
        eval_obj = obj.evaluated_get(depsgraph)
        bm = bmesh.new()
        bm.from_mesh(eval_obj.data)
        bm.verts.ensure_lookup_table()
        z_layers = defaultdict(list)
        for v in bm.verts:
            z_key = round(v.co.z / 0.05) * 0.05
            z_layers[z_key].append((v.co.x, v.co.y))
        all_z = sorted(z_layers.keys())
        rich_z = [zl for zl in all_z if len(z_layers[zl]) >= 4]
        print(f'[DEBUG {obj.name}] Total Z levels: {len(all_z)}, rich: {len(rich_z)}, range: [{all_z[0]:.1f}, {all_z[-1]:.1f}]')
        top_20 = [zl for zl in rich_z if zl >= rich_z[-1] - 0.2 * (rich_z[-1] - rich_z[0])]
        print(f'[DEBUG {obj.name}] Top 20%: {len(top_20)} levels')
        if top_20:
            bottom_pts = z_layers[rich_z[0]]
            cx = sum(p[0] for p in bottom_pts) / len(bottom_pts)
            cy = sum(p[1] for p in bottom_pts) / len(bottom_pts)
            for zl in top_20[:3]:
                pts = z_layers[zl]
                radii = sorted([math.sqrt((p[0]-cx)**2 + (p[1]-cy)**2) for p in pts])
                n = len(radii)
                outer_r = sum(radii[n - n//4:]) / max(1, n//4)
                print(f'[DEBUG {obj.name}]   z={zl:.2f}: {len(pts)} pts, outer_r={outer_r:.3f}')
        bm.free()
    return orig_analyze(obj, ctx, scale)

init_mod._analyze_cylinder_from_mesh = patched_analyze

# Now run the e2e test
ctx = bpy.context
for obj in ctx.scene.objects:
    if obj.type == 'MESH':
        result = patched_analyze(obj, ctx, 1000.0)
        if result:
            print(f"  {obj.name}: -> {result['obj_type']}, top={result.get('top_feature')}, bot={result.get('bottom_feature')}")
        else:
            print(f"  {obj.name}: -> NOT detected")