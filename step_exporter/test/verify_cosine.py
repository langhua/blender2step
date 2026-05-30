"""Verify cosine curve taper in test40.step."""
import re
import math

with open('f:\\git\\blender2step\\step_exporter\\test40.step', 'r', encoding='utf-8', errors='ignore') as f:
    content = f.read()

# Extract control point coordinates
point_pattern = r'#(\d+)\s*=\s*CARTESIAN_POINT\s*\([^,]+,\s*\(\s*([^,\r\n]+)\s*,\s*([^,\r\n]+)\s*,\s*([^\)\r\n]+)\s*\)'
points = {}
for match in re.finditer(point_pattern, content):
    point_id = int(match.group(1))
    try:
        x = float(match.group(2).strip())
        y = float(match.group(3).strip())
        z = float(match.group(4).strip())
        points[point_id] = (x, y, z)
    except ValueError:
        pass

# Find B_SPLINE_SURFACE entities
bspline_pattern = r'#(\d+)\s*=\s*\(?\s*BOUNDED_SURFACE\(\)\s*B_SPLINE_SURFACE\s*\(\s*(\d+)\s*,\s*(\d+)\s*,\s*\(([^)]+)\)'
bsplines = {}
for match in re.finditer(bspline_pattern, content, re.DOTALL):
    surface_id = int(match.group(1))
    u_degree = int(match.group(2))
    v_degree = int(match.group(3))
    control_points_refs = [int(x) for x in re.findall(r'#(\d+)', match.group(4))]
    bsplines[surface_id] = {
        'u_degree': u_degree,
        'v_degree': v_degree,
        'control_points': control_points_refs
    }

# Analyze Surface #236 (right side wall with taper)
target_surf = 236
if target_surf in bsplines:
    surf_info = bsplines[target_surf]
    cp_refs = surf_info['control_points']
    cp_coords = [points.get(ref, (0,0,0)) for ref in cp_refs]
    
    # Group by Z level
    z_groups = {}
    for p in cp_coords:
        z_rounded = round(p[2], 2)
        if z_rounded not in z_groups:
            z_groups[z_rounded] = []
        z_groups[z_rounded].append(p)
    
    sorted_z = sorted(z_groups.keys())
    
    print(f"Surface #{target_surf} - Cosine Curve Taper Verification")
    print(f"="*70)
    print(f"{'Z Level':<10} {'X (min)':<10} {'X (max)':<10} {'Expected X':<12} {'Error':<10}")
    print(f"-"*70)
    
    # Parameters after flip and translation:
    # Original: bottom_z=-5 (width=100, X=±50), top_z=5 (width=80, X=±40)
    # After 180° flip around X: bottom_z=5 (width=100), top_z=-5 (width=80)
    # After translation +10: bottom_z=15 (width=100, X=±50), top_z=5 (width=80, X=±40)
    # So in STEP file: Z=5 is top (narrow), Z=15 is bottom (wide)
    bottom_z = 15.0  # After flip+translate, this is the wide end
    top_z = 5.0      # After flip+translate, this is the narrow end
    bottom_x = 50.0  # Wide end X
    top_x = 40.0     # Narrow end X
    total_recess = bottom_x - top_x  # 10mm
    
    for z in sorted_z:
        pts_at_z = z_groups[z]
        x_vals = [p[0] for p in pts_at_z]
        min_x = min(x_vals)
        max_x = max(x_vals)
        
        # Calculate expected X using cosine curve
        # t=0 at bottom (wide end, z=15), t=1 at top (narrow end, z=5)
        t = (bottom_z - z) / (bottom_z - top_z)  # Reversed: t=0 at z=15, t=1 at z=5
        cosine_t = 1.0 - math.cos(math.pi / 2.0 * t)
        expected_x = bottom_x - total_recess * cosine_t
        
        error = min_x - expected_x
        
        print(f"{z:<10.2f} {min_x:<10.2f} {max_x:<10.2f} {expected_x:<12.2f} {error:<10.4f}")
    
    print(f"\nCosine curve formula: inset = {total_recess} * (1 - cos(π/2 * t))")
    print(f"t=0 at bottom (z={bottom_z}, wide), t=1 at top (z={top_z}, narrow)")
    print(f"\nNote: After 180° flip + translation, original bottom (wide) is now at z=15")
    
else:
    print(f"Surface #{target_surf} not found")
