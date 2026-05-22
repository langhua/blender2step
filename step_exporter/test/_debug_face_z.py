"""Check face centers for bottom shells."""
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
    print(f"\n=== {obj.name} ===")
    
    # Find up-facing faces
    up_faces = [f for f in mesh.polygons if f.normal.z > 0.5]
    down_faces = [f for f in mesh.polygons if f.normal.z < -0.5]
    side_faces = [f for f in mesh.polygons if abs(f.normal.z) <= 0.5]
    
    print(f"  up faces: {len(up_faces)}, down: {len(down_faces)}, side: {len(side_faces)}")
    
    if up_faces:
        from statistics import mean, median
        up_zs = [f.center.z for f in up_faces]
        print(f"  up face z stats: min={min(up_zs):.3f}, max={max(up_zs):.3f}, median={median(up_zs):.3f}, mean={mean(up_zs):.3f}")
        
        # Show sample
        for f in up_faces[:5]:
            print(f"    face {f.index}: z={f.center.z:.3f}, nz={f.normal.z:.3f}")
        
        # Find groups by z
        from collections import Counter
        z_groups = Counter(round(z, 2) for z in up_zs)
        print(f"  up face z groups: {z_groups.most_common(10)}")
    
    if down_faces:
        down_zs = [f.center.z for f in down_faces]
        from statistics import mean, median
        print(f"  down face z stats: min={min(down_zs):.3f}, max={max(down_zs):.3f}, median={median(down_zs):.3f}, mean={mean(down_zs):.3f}")