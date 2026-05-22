"""Debug mesh face structure."""
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
    z_min = min(v.co.z for v in mesh.vertices)
    z_max = max(v.co.z for v in mesh.vertices)
    
    print(f"\n=== {obj.name} ===")
    print(f"  faces: {len(mesh.polygons)}")
    
    # Check faces at/near top
    top_faces = [f for f in mesh.polygons if any(abs(mesh.vertices[v].co.z - z_max) < 0.01 for v in f.vertices)]
    print(f"  faces near top (z={z_max:.2f}): {len(top_faces)}")
    for f in top_faces[:5]:
        n = f.normal
        print(f"    face {f.index}: normal=({n[0]:.2f},{n[1]:.2f},{n[2]:.2f}), center=({f.center[0]:.1f},{f.center[1]:.1f},{f.center[2]:.2f})")
    
    # Check faces near center-top
    center_top_faces = [f for f in mesh.polygons if all(abs(mesh.vertices[v].co.z - z_max) < 0.01 for v in f.vertices) and abs(f.center[0]) < 10 and abs(f.center[1]) < 10]
    print(f"  center-top faces: {len(center_top_faces)}")
    
    # Check faces at middle height
    mid_z = (z_max + z_min) / 2
    mid_faces = [f for f in mesh.polygons if any(abs(mesh.vertices[v].co.z - mid_z) < 0.5 for v in f.vertices)]
    print(f"  faces near mid (z={mid_z:.1f}): {len(mid_faces)}")
    for f in mid_faces[:5]:
        zs = [mesh.vertices[v].co.z for v in f.vertices]
        n = f.normal
        print(f"    face {f.index}: z-range=[{min(zs):.2f},{max(zs):.2f}], normal=({n[0]:.2f},{n[1]:.2f},{n[2]:.2f})")
    
    # Count faces by normal direction
    up_faces = len([f for f in mesh.polygons if f.normal.z > 0.5])
    down_faces = len([f for f in mesh.polygons if f.normal.z < -0.5])
    side_faces = len(mesh.polygons) - up_faces - down_faces
    print(f"  normals: up={up_faces}, down={down_faces}, side={side_faces}")
    
    # Check center (0,0,z_max) vertex existence
    center_top_verts = [v for v in mesh.vertices if abs(v.co.x) < 5 and abs(v.co.y) < 5 and abs(v.co.z - z_max) < 0.1]
    print(f"  center-top verts (x<5, y<5, z≈{z_max:.0f}): {len(center_top_verts)}")
    
    center_bottom_verts = [v for v in mesh.vertices if abs(v.co.x) < 5 and abs(v.co.y) < 5 and abs(v.co.z - z_min) < 0.1]
    print(f"  center-bottom verts (x<5, y<5, z≈{z_min:.0f}): {len(center_bottom_verts)}")