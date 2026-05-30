import re
import math

with open('f:\\git\\blender2step\\step_exporter\\test39.step', 'r', encoding='utf-8', errors='ignore') as f:
    content = f.read()

# Extract all CARTESIAN_POINTs
point_pattern = r'#(\d+)\s*=\s*CARTESIAN_POINT\s*\([^,]+,\s*\(\s*([^,\r\n]+)\s*,\s*([^,\r\n]+)\s*,\s*([^\)\r\n]+)\s*\)'
points = {}
for match in re.finditer(point_pattern, content):
    try:
        points[int(match.group(1))] = (float(match.group(2)), float(match.group(3)), float(match.group(4)))
    except ValueError:
        pass

print(f"Total CARTESIAN_POINTs: {len(points)}")

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

print(f"\nTotal B_SPLINE_SURFACEs: {len(bsplines)}")

# Analyze first BSpline surface
if bsplines:
    first_id = list(bsplines.keys())[0]
    bspline = bsplines[first_id]
    print(f"\nFirst BSpline surface #{first_id}:")
    print(f"  U degree: {bspline['u_degree']}")
    print(f"  V degree: {bspline['v_degree']}")
    print(f"  Control points: {len(bspline['control_points'])}")
    
    # Get actual control point coordinates
    cp_coords = []
    for cp_id in bspline['control_points']:
        if cp_id in points:
            cp_coords.append(points[cp_id])
    
    print(f"  Resolved control points: {len(cp_coords)}")
    
    if cp_coords:
        x_vals = [p[0] for p in cp_coords]
        y_vals = [p[1] for p in cp_coords]
        z_vals = [p[2] for p in cp_coords]
        print(f"  X: {min(x_vals):.2f} to {max(x_vals):.2f}")
        print(f"  Y: {min(y_vals):.2f} to {max(y_vals):.2f}")
        print(f"  Z: {min(z_vals):.2f} to {max(z_vals):.2f}")
        
        # Analyze Z distribution
        print(f"\n  Control points by Z level:")
        z_levels = {}
        for p in cp_coords:
            z_rounded = round(p[2], 1)
            if z_rounded not in z_levels:
                z_levels[z_rounded] = []
            z_levels[z_rounded].append(p)
        
        for z in sorted(z_levels.keys()):
            pts = z_levels[z]
            x_vals_z = [p[0] for p in pts]
            print(f"    Z={z:.1f}: {len(pts)} points, X: {min(x_vals_z):.2f} to {max(x_vals_z):.2f}")
