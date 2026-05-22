"""Debug: analyze radius profiles of problematic cylinder objects"""
import bpy, sys, os, bmesh, math
from collections import defaultdict

sys.path.insert(0, r'f:\git\blender2step')
import importlib
import step_exporter.__init__ as init_mod
importlib.reload(init_mod)

targets = [
    'Cylinder_Chamfer_45deg',
    'Cylinder_Fillet_Top', 
    'Cylinder_Fillet_Small',
    'Cylinder_Tapered_Fillet_Chamfer',
    'Cylinder_Tapered_Hollow_Chamfer',
]

for name in targets:
    obj = bpy.context.scene.objects.get(name)
    if not obj:
        continue
    
    print(f'\n{"="*60}')
    print(f'=== {name} ===')
    
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bm.verts.ensure_lookup_table()
    
    verts_local = [(v.co.x, v.co.y, v.co.z) for v in bm.verts]
    
    z_layers = defaultdict(list)
    for x, y, z in verts_local:
        z_key = round(z / 0.05) * 0.05
        z_layers[z_key].append((x, y))
    
    sorted_z_all = sorted(z_layers.keys())
    sorted_z = [zl for zl in sorted_z_all if len(z_layers[zl]) >= 4]
    
    # Use bottom layer for center
    bottom_z = sorted_z[0]
    bottom_pts = z_layers[bottom_z]
    cx = sum(p[0] for p in bottom_pts) / len(bottom_pts)
    cy = sum(p[1] for p in bottom_pts) / len(bottom_pts)
    
    # Compute per-level statistics
    height = sorted_z[-1] - sorted_z[0]
    print(f'Height: {height:.1f}, Z range: [{sorted_z[0]:.1f}, {sorted_z[-1]:.1f}]')
    print(f'Center: ({cx:.3f}, {cy:.3f})')
    
    # For each Z level, compute max radius (outer surface)
    print(f'\nPer-level outer radii (top 20% of each level):')
    for zl in sorted_z:
        pts = z_layers[zl]
        radii = sorted([
            math.sqrt((p[0] - cx)**2 + (p[1] - cy)**2)
            for p in pts
        ])
        n = len(radii)
        # Outer 25% of radii (to exclude inner ring for hollow objects)
        outer_radii = radii[n - n//4:]
        avg_r = sum(outer_radii) / len(outer_radii)
        
        progress = (zl - sorted_z[0]) / height * 100 if height > 0 else 0
        print(f'  z={zl:7.2f} ({progress:5.1f}%): avg_outer_r={avg_r:7.3f}, all_radii=[{radii[0]:.2f}..{radii[n//2]:.2f}..{radii[-1]:.2f}]')
    
    # Analyze the top region for chamfer/fillet characteristics
    top_region = [zl for zl in sorted_z if zl > sorted_z[-1] * 0.5]
    if len(top_region) >= 3:
        print(f'\nTop region slope analysis:')
        for i in range(1, len(top_region)):
            zl = top_region[i]
            prev_zl = top_region[i-1]
            pts = z_layers[zl]
            radii = sorted([math.sqrt((p[0] - cx)**2 + (p[1] - cy)**2) for p in pts])
            prev_pts = z_layers[prev_zl]
            prev_radii = sorted([math.sqrt((p[0] - cx)**2 + (p[1] - cy)**2) for p in prev_pts])
            
            outer_r = sum(radii[-len(radii)//4:]) / (len(radii)//4)
            prev_outer_r = sum(prev_radii[-len(prev_radii)//4:]) / (len(prev_radii)//4)
            
            dz = zl - prev_zl
            dr = outer_r - prev_outer_r
            if dz > 0.01:
                slope = dr / dz
                print(f'  {prev_zl:7.2f} -> {zl:7.2f}: dr={dr:+.4f}, dz={dz:.4f}, slope={slope:+.4f}')
    
    bm.free()

print('\nDone!')