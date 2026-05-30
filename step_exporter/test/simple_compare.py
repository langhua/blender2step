"""Compare surface error between Blender test28.step and our STEP file."""
import sys
import os
import re
import math

def parse_step_points(step_file):
    """Parse STEP file and extract all vertex coordinates."""
    with open(step_file, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()
    
    # Extract CARTESIAN_POINT coordinates
    # Format: #ID = CARTESIAN_POINT('', (X, Y, Z));
    point_pattern = r'CARTESIAN_POINT\s*\(\s*\'[^\']*\'\s*,\s*\(\s*([-+]?\d*\.?\d+(?:[eE][-+]?\d+)?)\s*,\s*([-+]?\d*\.?\d+(?:[eE][-+]?\d+)?)\s*,\s*([-+]?\d*\.?\d+(?:[eE][-+]?\d+)?)\s*\)\s*\)'
    
    points = []
    for match in re.finditer(point_pattern, content):
        x = float(match.group(1))
        y = float(match.group(2))
        z = float(match.group(3))
        points.append((x, y, z))
    
    return points

def analyze_surface_error():
    """Analyze surface error between Blender and our STEP files."""
    print("=" * 60)
    print("Surface Error Analysis: Blender vs Our STEP")
    print("=" * 60)
    
    blender_file = os.path.join(os.path.dirname(__file__), 'test28.step')
    our_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'test39.step')
    
    # Parse both files
    print(f"\nParsing Blender test28.step...")
    blender_points = parse_step_points(blender_file)
    print(f"  Points: {len(blender_points)}")
    
    print(f"\nParsing our test39.step...")
    our_points = parse_step_points(our_file)
    print(f"  Points: {len(our_points)}")
    
    if not blender_points or not our_points:
        print("ERROR: Could not parse points")
        return
    
    # Analyze Z ranges
    blender_z = [p[2] for p in blender_points]
    our_z = [p[2] for p in our_points]
    
    blender_min_z = min(blender_z)
    blender_max_z = max(blender_z)
    blender_height = blender_max_z - blender_min_z
    
    our_min_z = min(our_z)
    our_max_z = max(our_z)
    our_height = our_max_z - our_min_z
    
    print(f"\nZ-coordinate ranges:")
    print(f"  Blender: {blender_min_z:.2f} to {blender_max_z:.2f} mm (height: {blender_height:.2f} mm)")
    print(f"  Our:     {our_min_z:.2f} to {our_max_z:.2f} mm (height: {our_height:.2f} mm)")
    
    # Check if Blender file needs coordinate transformation
    # Blender uses different coordinate system, need to normalize
    if blender_height > 100:  # Blender file has large coordinates
        print("\nBlender file has large coordinates, normalizing...")
        
        # Find the bounding box center and scale
        blender_x = [p[0] for p in blender_points]
        blender_y = [p[1] for p in blender_points]
        
        blender_min_x = min(blender_x)
        blender_max_x = max(blender_x)
        blender_min_y = min(blender_y)
        blender_max_y = max(blender_y)
        
        blender_width = blender_max_x - blender_min_x
        blender_depth = blender_max_y - blender_min_y
        
        print(f"  Blender bounding box: {blender_width:.2f} x {blender_depth:.2f} x {blender_height:.2f}")
        
        # Calculate scale factor (assuming Blender uses mm but with offset)
        # Our expected dimensions: 100 x 70 x 10
        scale_x = 100.0 / blender_width if blender_width > 0 else 1
        scale_y = 70.0 / blender_depth if blender_depth > 0 else 1
        scale_z = 10.0 / blender_height if blender_height > 0 else 1
        
        # Use average scale
        avg_scale = (scale_x + scale_y + scale_z) / 3
        
        print(f"  Scale factors: X={scale_x:.4f}, Y={scale_y:.4f}, Z={scale_z:.4f}")
        print(f"  Average scale: {avg_scale:.4f}")
        
        # Normalize Blender points
        blender_center_x = (blender_min_x + blender_max_x) / 2
        blender_center_y = (blender_min_y + blender_max_y) / 2
        blender_center_z = (blender_min_z + blender_max_z) / 2
        
        normalized_blender = []
        for p in blender_points:
            nx = (p[0] - blender_center_x) * avg_scale
            ny = (p[1] - blender_center_y) * avg_scale
            nz = (p[2] - blender_center_z) * avg_scale
            normalized_blender.append((nx, ny, nz))
        
        blender_points = normalized_blender
        
        # Recalculate ranges
        blender_z = [p[2] for p in blender_points]
        blender_min_z = min(blender_z)
        blender_max_z = max(blender_z)
        blender_height = blender_max_z - blender_min_z
        
        print(f"\nNormalized Blender ranges:")
        print(f"  Z: {blender_min_z:.2f} to {blender_max_z:.2f} mm (height: {blender_height:.2f} mm)")
    
    # Filter side wall points (exclude top/bottom within 0.5mm)
    blender_side = [p for p in blender_points 
                    if p[2] > blender_min_z + 0.5 and p[2] < blender_max_z - 0.5]
    our_side = [p for p in our_points 
                if p[2] > our_min_z + 0.5 and p[2] < our_max_z - 0.5]
    
    print(f"\nSide wall points:")
    print(f"  Blender: {len(blender_side)}")
    print(f"  Our:     {len(our_side)}")
    
    # Group by Z level
    def group_by_z(points, precision=0.1):
        levels = {}
        for p in points:
            z_key = round(p[2] / precision) * precision
            if z_key not in levels:
                levels[z_key] = []
            levels[z_key].append(p)
        return levels
    
    blender_levels = group_by_z(blender_side)
    our_levels = group_by_z(our_side)
    
    print(f"\nZ levels:")
    print(f"  Blender: {len(blender_levels)}")
    print(f"  Our:     {len(our_levels)}")
    
    # Calculate expected positions using cosine curve
    print(f"\nExpected (cosine curve): width=100, depth=70, height=10, recess=10")
    print(f"  Bottom: 100x70, Top: 80x50")
    
    # Sample Z levels and compare
    sample_z = sorted(blender_levels.keys())
    if len(sample_z) > 10:
        step = len(sample_z) // 10
        sample_z = sample_z[::step][:10]
    
    print(f"\n{'Z(mm)':<8} {'Blend_Xmax':<12} {'Our_Xmax':<12} {'Expected':<12} {'Error':<12}")
    print("-" * 56)
    
    errors = []
    for z in sample_z:
        t = (z - blender_min_z) / blender_height if blender_height > 0 else 0
        expected_inset = 10.0 * (1 - math.cos(math.pi / 2 * t))
        expected_x = 50.0 - expected_inset
        
        blend_pts = blender_levels.get(z, [])
        our_pts = our_levels.get(z, [])
        
        blend_xmax = max((p[0] for p in blend_pts), default=0)
        our_xmax = max((p[0] for p in our_pts), default=0)
        
        error = abs(our_xmax - expected_x)
        errors.append(error)
        
        print(f"{z:<8.1f} {blend_xmax:<12.2f} {our_xmax:<12.2f} {expected_x:<12.2f} {error:<12.4f}")
    
    if errors:
        avg_err = sum(errors) / len(errors)
        max_err = max(errors)
        print(f"\n{'='*56}")
        print(f"Error Summary:")
        print(f"  Average: {avg_err:.4f} mm")
        print(f"  Maximum: {max_err:.4f} mm")
        
        if max_err < 0.01:
            print(f"  Rating: EXCELLENT (< 0.01 mm)")
        elif max_err < 0.1:
            print(f"  Rating: GOOD (< 0.1 mm)")
        elif max_err < 1.0:
            print(f"  Rating: ACCEPTABLE (< 1.0 mm)")
        else:
            print(f"  Rating: POOR (> 1.0 mm)")

if __name__ == '__main__':
    analyze_surface_error()
