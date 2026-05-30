"""Compare surface error between Blender test28.step and our test39.step."""
import sys
import os
import re
import math

def extract_face_data(step_file):
    """Extract face data from STEP file."""
    with open(step_file, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()
    
    # Find all ADVANCED_FACE entries
    face_pattern = r'#(\d+)\s*=\s*ADVANCED_FACE\([^)]*\),\s*\(([^)]*)\)'
    faces = re.findall(face_pattern, content)
    
    # Find all CARTESIAN_POINT entries
    point_pattern = r'#(\d+)\s*=\s*CARTESIAN_POINT\([^)]*\),\s*\(\s*([-+]?\d*\.?\d+)\s*,\s*([-+]?\d*\.?\d+)\s*,\s*([-+]?\d*\.?\d+)\s*\)'
    points = {}
    for match in re.finditer(point_pattern, content):
        point_id = match.group(1)
        x, y, z = float(match.group(2)), float(match.group(3)), float(match.group(4))
        points[point_id] = (x, y, z)
    
    return faces, points

def analyze_surface_error(blender_file, our_file):
    """Analyze surface error between two STEP files."""
    print("Comparing surface error between Blender and our STEP files...")
    print()
    
    # Extract data from both files
    print("Extracting data from Blender test28.step...")
    blender_faces, blender_points = extract_face_data(blender_file)
    print(f"  Faces: {len(blender_faces)}, Points: {len(blender_points)}")
    
    print("Extracting data from our test39.step...")
    our_faces, our_points = extract_face_data(our_file)
    print(f"  Faces: {len(our_faces)}, Points: {len(our_points)}")
    
    # Analyze Z-coordinate distribution
    print("\nAnalyzing Z-coordinate distribution...")
    
    blender_z = [p[2] for p in blender_points.values()]
    our_z = [p[2] for p in our_points.values()]
    
    if blender_z and our_z:
        print(f"Blender Z range: {min(blender_z):.2f} to {max(blender_z):.2f} mm")
        print(f"Our Z range: {min(our_z):.2f} to {max(our_z):.2f} mm")
        
        # Count unique Z levels
        blender_z_levels = sorted(set([round(z, 1) for z in blender_z]))
        our_z_levels = sorted(set([round(z, 1) for z in our_z]))
        
        print(f"Blender Z levels: {len(blender_z_levels)}")
        print(f"Our Z levels: {len(our_z_levels)}")
        
        # Analyze side wall points (exclude top and bottom)
        height = max(blender_z) - min(blender_z)
        mid_z = (max(blender_z) + min(blender_z)) / 2
        
        blender_side_points = [p for p in blender_points.values() 
                              if abs(p[2] - mid_z) < height/2 - 0.5]
        our_side_points = [p for p in our_points.values() 
                          if abs(p[2] - mid_z) < height/2 - 0.5]
        
        print(f"\nSide wall points:")
        print(f"  Blender: {len(blender_side_points)}")
        print(f"  Our: {len(our_side_points)}")
        
        # Calculate expected positions using cosine curve
        print("\nCalculating expected positions (cosine curve)...")
        print("Parameters: width=100, depth=70, height=10, top_recess=10")
        
        # For each Z level, calculate expected X/Y positions
        errors = []
        for z in sorted(set([p[2] for p in our_side_points])):
            t = (z - min(blender_z)) / height
            expected_inset = 10.0 * (1 - math.cos(math.pi / 2 * t))
            
            # Get actual points at this Z level
            points_at_z = [p for p in our_side_points if abs(p[2] - z) < 0.1]
            
            if points_at_z:
                # Calculate average X position for right side (X > 0)
                right_points = [p for p in points_at_z if p[0] > 0]
                if right_points:
                    avg_x = sum(p[0] for p in right_points) / len(right_points)
                    expected_x = 50.0 - expected_inset  # width/2 - inset
                    error = abs(avg_x - expected_x)
                    errors.append(error)
        
        if errors:
            avg_error = sum(errors) / len(errors)
            max_error = max(errors)
            print(f"\nSurface Error Analysis:")
            print(f"  Points analyzed: {len(errors)}")
            print(f"  Average error: {avg_error:.4f} mm")
            print(f"  Maximum error: {max_error:.4f} mm")
            
            if max_error < 0.01:
                print("  Result: EXCELLENT match (< 0.01 mm)")
            elif max_error < 0.1:
                print("  Result: GOOD match (< 0.1 mm)")
            elif max_error < 1.0:
                print("  Result: ACCEPTABLE match (< 1.0 mm)")
            else:
                print("  Result: POOR match (> 1.0 mm)")

if __name__ == '__main__':
    blender_step = os.path.join(os.path.dirname(__file__), 'test28.step')
    our_step = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'test39.step')
    
    if os.path.exists(blender_step) and os.path.exists(our_step):
        analyze_surface_error(blender_step, our_step)
    else:
        print("STEP files not found!")
        print(f"Blender: {blender_step} (exists: {os.path.exists(blender_step)})")
        print(f"Our: {our_step} (exists: {os.path.exists(our_step)})")
