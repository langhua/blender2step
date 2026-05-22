"""Debug vertex z distribution for bottom shells."""
import bpy
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))
import create_bottom_shell

create_bottom_shell.create_both_bottom_shells_scene()

for obj in bpy.context.scene.objects:
    if obj.type != 'MESH':
        continue
    
    mesh = obj.data
    from collections import Counter
    z_vals = [round(v.co.z, 5) for v in mesh.vertices]
    z_counter = Counter(z_vals)
    unique_z = sorted(z_counter.keys())
    
    print(f"\n=== {obj.name} ===")
    print(f"  total verts: {len(mesh.vertices)}")
    print(f"  unique z-levels: {len(unique_z)}")
    print(f"  z-range: [{min(unique_z):.2f}, {max(unique_z):.2f}]")
    print(f"  top 10 z-levels by count:")
    for z, count in z_counter.most_common(10):
        print(f"    z={z:.4f}: {count} verts")