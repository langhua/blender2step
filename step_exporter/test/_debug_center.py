"""Check if there's a top face at the center."""
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
    
    # Find faces whose center is near (0, 0, z_max)
    z_max = max(v.co.z for v in mesh.vertices)
    center_faces = [f for f in mesh.polygons 
                   if abs(f.center.x) < 10 and abs(f.center.y) < 10 
                   and abs(f.center.z - z_max) < 0.5]
    
    print(f"\n=== {obj.name} ===")
    print(f"  faces near center-top ({z_max:.1f}): {len(center_faces)}")
    for f in center_faces[:5]:
        print(f"    face {f.index}: center=({f.center.x:.1f},{f.center.y:.1f},{f.center.z:.3f}), n=({f.normal.x:.2f},{f.normal.y:.2f},{f.normal.z:.2f}), area={f.area:.3f}")
    
    # Check up-facing faces distribution
    up_faces = [f for f in mesh.polygons if f.normal.z > 0.5]
    x_range = (min(f.center.x for f in up_faces), max(f.center.x for f in up_faces))
    y_range = (min(f.center.y for f in up_faces), max(f.center.y for f in up_faces))
    print(f"  up faces x-range: [{x_range[0]:.1f}, {x_range[1]:.1f}], y-range: [{y_range[0]:.1f}, {y_range[1]:.1f}]")
    
    # Check faces near z=0 (inner floor level)
    inner_faces = [f for f in mesh.polygons if abs(f.center.z) < 2 and abs(f.center.z) > 0.5 and f.normal.z > 0.3]
    print(f"  inner up faces (z≈mid, nz>0.3): {len(inner_faces)}")
    for f in inner_faces[:5]:
        print(f"    face {f.index}: center=({f.center.x:.1f},{f.center.y:.1f},{f.center.z:.3f}), n=({f.normal.x:.2f},{f.normal.y:.2f},{f.normal.z:.2f})")
    
    # For the up faces, check the z distribution
    from collections import Counter
    up_zs = [round(f.center.z, 2) for f in up_faces]
    z_counter = Counter(up_zs)
    print(f"  up face z-distribution: {dict(z_counter.most_common())}")