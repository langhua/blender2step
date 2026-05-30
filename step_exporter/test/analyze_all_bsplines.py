import re

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

print(f"Total B_SPLINE_SURFACEs: {len(bsplines)}")

# Analyze all BSpline surfaces - group by X range
surface_analysis = []
for surface_id, bspline in bsplines.items():
    cp_coords = []
    for cp_id in bspline['control_points']:
        if cp_id in points:
            cp_coords.append(points[cp_id])
    
    if cp_coords:
        x_vals = [p[0] for p in cp_coords]
        y_vals = [p[1] for p in cp_coords]
        z_vals = [p[2] for p in cp_coords]
        
        surface_analysis.append({
            'id': surface_id,
            'x_min': min(x_vals),
            'x_max': max(x_vals),
            'y_min': min(y_vals),
            'y_max': max(y_vals),
            'z_min': min(z_vals),
            'z_max': max(z_vals),
            'num_cps': len(cp_coords)
        })

# Group by Z range (should be 5 to 15 for side walls)
side_surfaces = [s for s in surface_analysis if s['z_min'] == 5.0 and s['z_max'] == 15.0]
print(f"\nSide wall surfaces (Z=5 to 15): {len(side_surfaces)}")

# Analyze X ranges at bottom and top
for i, surf in enumerate(side_surfaces[:4]):
    print(f"\nSurface #{surf['id']} (sample {i+1}):")
    print(f"  X: {surf['x_min']:.2f} to {surf['x_max']:.2f}")
    print(f"  Y: {surf['y_min']:.2f} to {surf['y_max']:.2f}")
    print(f"  Z: {surf['z_min']:.2f} to {surf['z_max']:.2f}")

# Check if there are surfaces with different X at bottom vs top
print(f"\n\nChecking for tapered surfaces...")
for surf in side_surfaces:
    # Get control points and check X variation by Z
    bspline = bsplines[surf['id']]
    cp_coords = []
    for cp_id in bspline['control_points']:
        if cp_id in points:
            cp_coords.append(points[cp_id])
    
    if cp_coords:
        # Group by Z
        z_groups = {}
        for p in cp_coords:
            z_rounded = round(p[2], 1)
            if z_rounded not in z_groups:
                z_groups[z_rounded] = []
            z_groups[z_rounded].append(p)
        
        # Check X range at different Z levels
        x_at_bottom = None
        x_at_top = None
        for z in sorted(z_groups.keys()):
            pts = z_groups[z]
            x_vals_z = [p[0] for p in pts]
            if z == 5.0:
                x_at_bottom = (min(x_vals_z), max(x_vals_z))
            elif z == 15.0:
                x_at_top = (min(x_vals_z), max(x_vals_z))
        
        if x_at_bottom and x_at_top:
            bottom_width = x_at_bottom[1] - x_at_bottom[0]
            top_width = x_at_top[1] - x_at_top[0]
            if abs(bottom_width - top_width) > 0.1:
                print(f"  Surface #{surf['id']}: Bottom X={x_at_bottom}, Top X={x_at_top}")
