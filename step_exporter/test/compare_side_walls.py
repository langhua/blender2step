"""Compare side wall face distribution between STEP files."""
import sys
import os
import re

def analyze_side_walls(step_file, label):
    """Analyze side wall face distribution."""
    print(f"\n{'='*60}")
    print(f"Analyzing side walls: {label}")
    print(f"{'='*60}")
    
    if not os.path.exists(step_file):
        print(f"File not found!")
        return
    
    with open(step_file, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()
    
    # Find all ADVANCED_FACE entries
    face_pattern = r'#(\d+)\s*=\s*ADVANCED_FACE\([^)]*\),\s*\(([^)]*)\)'
    faces = re.findall(face_pattern, content)
    
    print(f"Total ADVANCED_FACE entries: {len(faces)}")
    
    # Find PLANE entries to identify top/bottom faces
    plane_pattern = r'#(\d+)\s*=\s*PLANE\('
    planes = re.findall(plane_pattern, content)
    print(f"PLANE surfaces: {len(planes)}")
    
    # Find CYLINDRICAL_SURFACE entries (fillets)
    cyl_pattern = r'#(\d+)\s*=\s*CYLINDRICAL_SURFACE\('
    cylinders = re.findall(cyl_pattern, content)
    print(f"CYLINDRICAL_SURFACE (fillets): {len(cylinders)}")
    
    # Side wall faces = total - planes - cylinders
    side_wall_count = len(faces) - len(planes) - len(cylinders)
    print(f"Side wall faces (estimated): {side_wall_count}")
    
    # Analyze face sizes by looking at vertex coordinates
    # Find all CARTESIAN_POINT entries
    point_pattern = r'#(\d+)\s*=\s*CARTESIAN_POINT\([^)]*\),\s*\(\s*([-+]?\d*\.?\d+)\s*,\s*([-+]?\d*\.?\d+)\s*,\s*([-+]?\d*\.?\d+)\s*\)'
    points = re.findall(point_pattern, content)
    
    if points:
        # Get Z coordinates to analyze height distribution
        z_coords = [float(p[3]) for p in points]
        if z_coords:
            min_z = min(z_coords)
            max_z = max(z_coords)
            print(f"\nZ-coordinate range: {min_z:.2f} to {max_z:.2f} mm")
            print(f"Height: {max_z - min_z:.2f} mm")
            
            # Count points at different Z levels
            z_levels = {}
            for z in z_coords:
                z_rounded = round(z, 1)
                z_levels[z_rounded] = z_levels.get(z_rounded, 0) + 1
            
            print(f"\nZ-level distribution (points per level):")
            for z in sorted(z_levels.keys()):
                print(f"  Z={z:.1f}: {z_levels[z]} points")

if __name__ == '__main__':
    blender_step = os.path.join(os.path.dirname(__file__), 'test28.step')
    our_step = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'test39.step')
    
    analyze_side_walls(blender_step, "Blender test28.step")
    analyze_side_walls(our_step, "Our test39.step")
