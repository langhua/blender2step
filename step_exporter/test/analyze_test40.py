"""Analyze BSpline surfaces in test40.step to verify taper."""
import re

with open('f:\\git\\blender2step\\step_exporter\\test40.step', 'r', encoding='utf-8', errors='ignore') as f:
    content = f.read()

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

print(f"Found {len(bsplines)} BSpline surfaces")
print(f"Found {len(points)} control points")

# Analyze first few BSpline surfaces
for i, (surf_id, surf_info) in enumerate(list(bsplines.items())[:5]):
    cp_refs = surf_info['control_points']
    cp_coords = [points.get(ref, (0,0,0)) for ref in cp_refs]
    
    x_vals = [p[0] for p in cp_coords]
    y_vals = [p[1] for p in cp_coords]
    z_vals = [p[2] for p in cp_coords]
    
    print(f"\nSurface #{surf_id}:")
    print(f"  U degree: {surf_info['u_degree']}, V degree: {surf_info['v_degree']}")
    print(f"  Control points: {len(cp_coords)}")
    print(f"  X range: {min(x_vals):.2f} to {max(x_vals):.2f}")
    print(f"  Y range: {min(y_vals):.2f} to {max(y_vals):.2f}")
    print(f"  Z range: {min(z_vals):.2f} to {max(z_vals):.2f}")
    
    # Check if X varies with Z (taper indicator)
    unique_z = sorted(set(round(z, 2) for z in z_vals))
    if len(unique_z) > 1:
        print(f"  Z levels: {unique_z}")
        for z_level in unique_z[:3]:
            pts_at_z = [p for p in cp_coords if round(p[2], 2) == z_level]
            if pts_at_z:
                x_at_z = [p[0] for p in pts_at_z]
                print(f"    Z={z_level}: X range = {min(x_at_z):.2f} to {max(x_at_z):.2f}")
