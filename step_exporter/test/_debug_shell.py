"""Debug bottom shell mesh structure"""
import bpy, sys, os
from collections import defaultdict
import bmesh

sys.path.insert(0, r'f:\git\blender2step')
os.environ['STEP_EXPORTER_DEBUG'] = '1'

ctx = bpy.context

def clear_scene():
    for obj in list(bpy.data.objects):
        bpy.data.objects.remove(obj, do_unlink=True)

clear_scene()

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'test'))
import create_bottom_shell
create_bottom_shell.create_both_bottom_shells_scene()

for obj in ctx.scene.objects:
    if obj.type != 'MESH' or 'BottomShell' not in obj.name:
        continue
    print(f"\n{'='*60}")
    print(f"Analyzing: {obj.name}")
    print(f"Location: {obj.location}")
    print(f"{'='*60}")
    
    depsgraph = ctx.evaluated_depsgraph_get()
    eval_obj = obj.evaluated_get(depsgraph)
    mesh_data = eval_obj.data
    
    bm = bmesh.new()
    bm.from_mesh(mesh_data)
    bm.verts.ensure_lookup_table()
    
    print(f"Total vertices: {len(bm.verts)}")
    
    z_layers = defaultdict(list)
    for v in bm.verts:
        z_key = round(v.co.z / 0.01) * 0.01
        z_layers[z_key].append(v)
    
    sorted_z = sorted(z_layers.keys())
    print(f"Total z-levels: {len(sorted_z)}")
    print(f"Z range: {sorted_z[0]:.2f} to {sorted_z[-1]:.2f}")
    print(f"Height: {sorted_z[-1] - sorted_z[0]:.2f}")
    
    print(f"\nAll z-levels:")
    for zl in sorted_z:
        verts = z_layers[zl]
        xs = [v.co.x for v in verts]
        ys = [v.co.y for v in verts]
        print(f"  z={zl:+.2f}  n={len(verts):4d}  x=[{min(xs):.1f},{max(xs):.1f}]  y=[{min(ys):.1f},{max(ys):.1f}]")
    
    # Check bottom surface
    bottom_z = sorted_z[0]
    bottom_verts = z_layers[bottom_z]
    print(f"\nBottom surface: z={bottom_z}, {len(bottom_verts)} verts")
    
    # Check top surface
    top_z = sorted_z[-1]
    top_verts = z_layers[top_z]
    print(f"Top surface: z={top_z}, {len(top_verts)} verts")
    
    # Check inner bottom detection
    total_levels = len(sorted_z)
    outer_wall_start_z = None
    for i in range(1, len(sorted_z)):
        gap = sorted_z[i] - sorted_z[i-1]
        levels_after = total_levels - i
        if levels_after < total_levels * 0.25 and gap > 0.1:
            outer_wall_start_z = sorted_z[i-1]
            print(f"Found outer wall start: z={outer_wall_start_z} (gap={gap:.3f}, levels_after={levels_after})")
            break
    
    if outer_wall_start_z is None:
        outer_wall_start_z = sorted_z[-2] if len(sorted_z) > 1 else sorted_z[-1]
        print(f"No clear outer wall start, using: {outer_wall_start_z}")
    
    outer_fillet_radius = outer_wall_start_z - bottom_z
    print(f"Outer fillet radius: {outer_fillet_radius:.2f}")
    
    # Find inner bottom
    inner_bottom_z = None
    max_count = 0
    for z_level in sorted_z[1:]:
        if z_level > bottom_z + 0.5 and z_level < outer_wall_start_z:
            count = len(z_layers[z_level])
            if count > max_count:
                max_count = count
                inner_bottom_z = z_level
    
    if inner_bottom_z:
        inner_verts = z_layers[inner_bottom_z]
        inner_xs = [v.co.x for v in inner_verts]
        inner_ys = [v.co.y for v in inner_verts]
        center_nearby = [v for v in inner_verts if abs(v.co.x) < 5 and abs(v.co.y) < 5]
        print(f"Inner bottom: z={inner_bottom_z}, {len(inner_verts)} verts, center_count={len(center_nearby)}")
    else:
        print("Inner bottom NOT FOUND!")
    
    bm.free()

print("\nDone!")