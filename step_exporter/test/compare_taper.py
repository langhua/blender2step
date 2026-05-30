"""Compare taper between test39.step (old) and test40.step (new)."""
import re

def analyze_step_file(filepath, label):
    print(f"\n{'='*60}")
    print(f"Analyzing {label}: {filepath}")
    print(f"{'='*60}")
    
    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
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

    # Find surfaces with varying X across Z levels (taper indicator)
    tapered_surfaces = []
    vertical_surfaces = []
    
    for surf_id, surf_info in bsplines.items():
        cp_refs = surf_info['control_points']
        cp_coords = [points.get(ref, (0,0,0)) for ref in cp_refs]
        
        z_vals = [p[2] for p in cp_coords]
        unique_z = sorted(set(round(z, 2) for z in z_vals))
        
        if len(unique_z) > 1:
            # Check if X varies with Z
            x_at_bottom = [p[0] for p in cp_coords if round(p[2], 2) == unique_z[0]]
            x_at_top = [p[0] for p in cp_coords if round(p[2], 2) == unique_z[-1]]
            
            if x_at_bottom and x_at_top:
                bottom_x = min(x_at_bottom)
                top_x = min(x_at_top)
                
                if abs(bottom_x - top_x) > 0.1:  # More than 0.1mm difference
                    tapered_surfaces.append({
                        'id': surf_id,
                        'bottom_x': bottom_x,
                        'top_x': top_x,
                        'bottom_z': unique_z[0],
                        'top_z': unique_z[-1],
                        'taper': abs(bottom_x - top_x)
                    })
                else:
                    vertical_surfaces.append(surf_id)

    print(f"\nTapered surfaces: {len(tapered_surfaces)}")
    print(f"Vertical surfaces: {len(vertical_surfaces)}")
    
    if tapered_surfaces:
        print(f"\nTaper details:")
        for surf in tapered_surfaces[:5]:  # Show first 5
            print(f"  Surface #{surf['id']}:")
            print(f"    Z: {surf['bottom_z']:.2f} -> {surf['top_z']:.2f}")
            print(f"    X: {surf['bottom_x']:.2f} -> {surf['top_x']:.2f}")
            print(f"    Taper: {surf['taper']:.2f} mm")

    return len(tapered_surfaces), len(vertical_surfaces)

# Analyze both files
tapered_39, vertical_39 = analyze_step_file(
    'f:\\git\\blender2step\\step_exporter\\test39.step',
    'test39.step (old - before fix)'
)

tapered_40, vertical_40 = analyze_step_file(
    'f:\\git\\blender2step\\step_exporter\\test40.step',
    'test40.step (new - after fix)'
)

print(f"\n{'='*60}")
print(f"SUMMARY")
print(f"{'='*60}")
print(f"test39.step: {tapered_39} tapered, {vertical_39} vertical surfaces")
print(f"test40.step: {tapered_40} tapered, {vertical_40} vertical surfaces")

if tapered_40 > tapered_39:
    print(f"\nSUCCESS: test40.step has {tapered_40 - tapered_39} more tapered surfaces!")
else:
    print(f"\nWARNING: test40.step does not have more tapered surfaces")
