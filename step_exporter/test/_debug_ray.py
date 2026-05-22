"""Debug ray cast on bottom shell meshes."""
import bpy
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))
import create_bottom_shell

create_bottom_shell.create_both_bottom_shells_scene()

depsgraph = bpy.context.evaluated_depsgraph_get()

for obj in bpy.context.scene.objects:
    if obj.type != 'MESH':
        continue
    
    eval_obj = obj.evaluated_get(depsgraph)
    z_min = min(v.co.z for v in obj.data.vertices)
    z_max = max(v.co.z for v in obj.data.vertices)
    
    print(f"\n=== {obj.name} ===")
    print(f"  location: {obj.location}")
    print(f"  verts: {len(obj.data.vertices)}, z-range: [{z_min:.2f}, {z_max:.2f}]")
    
    # Ray from top center
    ray_origin = (0, 0, z_max + 1)
    ray_dir = (0, 0, -1)
    ray_len = z_max - z_min + 4
    
    hits = []
    org = ray_origin
    for _ in range(50):
        hit, loc, normal, face_idx = eval_obj.ray_cast(org, ray_dir, distance=ray_len)
        if not hit:
            break
        hits.append((loc.z, normal))
        org = loc[0] + ray_dir[0]*0.001, loc[1] + ray_dir[1]*0.001, loc[2] + ray_dir[2]*0.001
    
    print(f"  ray from (0,0,{z_max+1}) down, {len(hits)} hits:")
    for z, n in hits:
        print(f"    z={z:.3f}, normal=({n[0]:.2f},{n[1]:.2f},{n[2]:.2f})")
    
    # Also test ray at off-center position
    for test_x, test_y in [(20,0), (40,0), (30,15)]:
        org = (test_x, test_y, z_max + 1)
        hit, loc, normal, face_idx = eval_obj.ray_cast(org, ray_dir, distance=ray_len)
        if hit:
            print(f"  off-center ({test_x},{test_y}): hit at z={loc[2]:.3f}, n=({normal[0]:.2f},{normal[1]:.2f},{normal[2]:.2f})")
        else:
            print(f"  off-center ({test_x},{test_y}): NO HIT")