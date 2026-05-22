"""Debug: analyze radius profiles - compact version"""
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
    
    print(f'\n=== {name} ===')
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bm.verts.ensure_lookup_table()
    
    verts_local = [(v.co.x, v.co.y, v.co.z) for v in bm.verts]
    
    z_layers = defaultdict(list)
    for x, y, z in verts_local:
        z_key = round(z / 0.1) * 0.1  # coarser grouping
        z_layers[z_key].append((x, y))
    
    sorted_z = sorted(z_layers.keys())
    
    # Use bottom layer for center
    bottom_pts = z_layers[min(sorted_z)]
    cx = sum(p[0] for p in bottom_pts) / len(bottom_pts)
    cy = sum(p[1] for p in bottom_pts) / len(bottom_pts)
    
    z_min = sorted_z[0]
    z_max = sorted_z[-1]
    height = z_max - z_min
    
    print(f'  Height: {height:.1f}, Z: [{z_min:.1f}, {z_max:.1f}]')
    
    # Sample outer radii at key Z levels
    print(f'  {"z":>7s} {"%":>5s} {"outer_r":>8s}  {"inner_r":>8s}  {"slope":>8s}  type')
    prev_z = None
    prev_outer_r = None
    const_r = None  # estimated constant cylinder radius
    
    # Find the constant radius region (middle section)
    mid_radii = []
    for zl in sorted_z:
        if z_min + 0.1*height < zl < z_max - 0.1*height:
            pts = z_layers[zl]
            radii = sorted([math.sqrt((p[0] - cx)**2 + (p[1] - cy)**2) for p in pts])
            n = len(radii)
            outer_r = sum(radii[n - n//4:]) / (n//4)
            inner_r = sum(radii[:n//4]) / max(1, n//4)
            if len(radii) >= 16:
                mid_radii.append(outer_r)
    
    if mid_radii:
        const_r = sorted(mid_radii)[-1]  # largest outer radius in middle region
    
    for zl in sorted_z:
        pts = z_layers[zl]
        radii = sorted([math.sqrt((p[0] - cx)**2 + (p[1] - cy)**2) for p in pts])
        n = len(radii)
        outer_r = sum(radii[n - n//4:]) / max(1, n//4)
        inner_r = sum(radii[:n//4]) / max(1, n//4)
        pct = (zl - z_min) / max(height, 0.01) * 100
        
        slope = 0
        if prev_z is not None:
            dz = zl - prev_z
            if dz > 0.001:
                slope = (outer_r - prev_outer_r) / dz
        
        # Classify region
        region = 'cyl'  # default: cylinder body
        if const_r and outer_r < const_r * 0.97:
            if prev_z and prev_outer_r and prev_outer_r > const_r * 0.97:
                # Check if slope becomes constant (chamfer) or changing (fillet)
                # Will be computed below
                region = 'top '
            else:
                region = 'top '
        elif zl <= z_min + 0.05 * height:
            region = 'bot '
        
        print(f'  {zl:7.1f} {pct:4.0f}% {outer_r:8.3f}  {inner_r:8.3f}  {slope:8.3f}  {region}')
        
        prev_z = zl
        prev_outer_r = outer_r
    
    bm.free()

print('\nDone!')