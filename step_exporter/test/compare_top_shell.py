"""Compare surface error between Blender test28.step (top shell only) and our STEP file."""
import sys
import os
import re
import math

def parse_step_file(step_file):
    """Parse STEP file and extract all geometry data."""
    with open(step_file, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()
    
    # Extract CARTESIAN_POINT coordinates
    point_pattern = r'#(\d+)\s*=\s*CARTESIAN_POINT\s*\(\s*\'[^\']*\'\s*,\s*\(\s*([-+]?\d*\.?\d+(?:[eE][-+]?\d+)?)\s*,\s*([-+]?\d*\.?\d+(?:[eE][-+]?\d+)?)\s*,\s*([-+]?\d*\.?\d+(?:[eE][-+]?\d+)?)\s*\)\s*\)'
    points = {}
    for match in re.finditer(point_pattern, content):
        id_num = int(match.group(1))
        x = float(match.group(2))
        y = float(match.group(3))
        z = float(match.group(4))
        points[id_num] = (x, y, z)
    
    # Extract VERTEX_POINT -> CARTESIAN_POINT mapping
    vertex_pattern = r'#(\d+)\s*=\s*VERTEX_POINT\s*\(\s*\'[^\']*\'\s*,\s*#(\d+)\s*\)'
    vertices = {}
    for match in re.finditer(vertex_pattern, content):
        vertex_id = int(match.group(1))
        point_id = int(match.group(2))
        vertices[vertex_id] = point_id
    
    # Extract EDGE_CURVE -> VERTEX_POINT mapping
    edge_pattern = r'#(\d+)\s*=\s*EDGE_CURVE\s*\([^,]+,\s*#(\d+)\s*,\s*#(\d+)\s*,'
    edges = {}
    for match in re.finditer(edge_pattern, content):
        edge_id = int(match.group(1))
        v1_id = int(match.group(2))
        v2_id = int(match.group(3))
        edges[edge_id] = (v1_id, v2_id)
    
    # Find CLOSED_SHELL entities
    shell_pattern = r'#(\d+)\s*=\s*CLOSED_SHELL\s*\(\s*\'[^\']*\'\s*,\s*\(([^)]+)\)\)'
    shells = {}
    for match in re.finditer(shell_pattern, content):
        shell_id = int(match.group(1))
        face_refs = [int(x) for x in re.findall(r'#(\d+)', match.group(2))]
        shells[shell_id] = face_refs
    
    return content, points, vertices, edges, shells

def extract_shell_points(content, shell_id, face_ids, points, vertices, edges):
    """Extract all vertex points from a specific shell."""
    xyz_points = []
    
    for face_id in face_ids:
        # Find ADVANCED_FACE and get its FACE_BOUND references
        face_pattern = rf'#{face_id}=\s*ADVANCED_FACE\s*\([^,]+,\s*\(([^)]+)\)'
        face_match = re.search(face_pattern, content)
        if face_match:
            bound_refs = [int(x) for x in re.findall(r'#(\d+)', face_match.group(1))]
            for bound_ref in bound_refs:
                # Find EDGE_LOOP reference in FACE_BOUND
                loop_pattern = rf'#{bound_ref}=\s*FACE_BOUND\s*\([^,]+,\s*#(\d+)'
                loop_match = re.search(loop_pattern, content)
                if loop_match:
                    loop_id = int(loop_match.group(1))
                    # Find ORIENTED_EDGE references in EDGE_LOOP
                    oriented_pattern = rf'#{loop_id}=\s*EDGE_LOOP\s*\([^,]+,\s*\(([^)]+)\)'
                    oriented_match = re.search(oriented_pattern, content)
                    if oriented_match:
                        edge_refs = [int(x) for x in re.findall(r'#(\d+)', oriented_match.group(1))]
                        for edge_ref in edge_refs:
                            # Check if this is ORIENTED_EDGE -> EDGE_CURVE
                            # ORIENTED_EDGE('',*,*,#37,.T.)
                            oriented_edge_pattern = rf'#{edge_ref}=\s*ORIENTED_EDGE\s*\([^,]+,[^,]+,[^,]+,\s*#(\d+)'
                            oriented_edge_match = re.search(oriented_edge_pattern, content)
                            if oriented_edge_match:
                                edge_curve_id = int(oriented_edge_match.group(1))
                                if edge_curve_id in edges:
                                    v1_id, v2_id = edges[edge_curve_id]
                                    for v_id in [v1_id, v2_id]:
                                        if v_id in vertices and vertices[v_id] in points:
                                            xyz_points.append(points[vertices[v_id]])
    
    return xyz_points

def analyze_surface_error():
    """Analyze surface error between Blender and our STEP files."""
    print("=" * 60)
    print("Surface Error Analysis: Blender vs Our STEP")
    print("=" * 60)
    
    blender_file = os.path.join(os.path.dirname(__file__), 'test28.step')
    our_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'test39.step')
    
    # Parse Blender file
    print(f"\nParsing Blender test28.step...")
    b_content, b_points, b_vertices, b_edges, b_shells = parse_step_file(blender_file)
    print(f"  Total points: {len(b_points)}")
    print(f"  Shells found: {list(b_shells.keys())}")
    
    # Parse our file
    print(f"\nParsing our test39.step...")
    o_content, o_points, o_vertices, o_edges, o_shells = parse_step_file(our_file)
    print(f"  Total points: {len(o_points)}")
    print(f"  Shells found: {list(o_shells.keys())}")
    
    # Extract top shell from Blender (shell #8084)
    if 8084 in b_shells:
        print(f"\nExtracting Blender top shell (#8084)...")
        blender_points = extract_shell_points(b_content, 8084, b_shells[8084], b_points, b_vertices, b_edges)
        print(f"  Top shell points: {len(blender_points)}")
    else:
        print("ERROR: Shell #8084 not found in Blender file")
        return
    
    # Extract our shell (first shell)
    if o_shells:
        our_shell_id = list(o_shells.keys())[0]
        print(f"\nExtracting our top shell (#{our_shell_id})...")
        our_points = extract_shell_points(o_content, our_shell_id, o_shells[our_shell_id], o_points, o_vertices, o_edges)
        print(f"  Our shell points: {len(our_points)}")
    else:
        print("ERROR: No shells found in our file")
        return
    
    if not blender_points or not our_points:
        print("ERROR: Could not extract points")
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
    
    # Normalize Blender to match our coordinate system
    # The heights should match, but coordinates may be offset
    if abs(blender_height - our_height) > 0.1:
        print(f"\nNormalizing Blender coordinates...")
        
        # Calculate scale factor based on height
        scale = our_height / blender_height if blender_height > 0 else 1
        
        # Center and scale
        blender_center_z = (blender_min_z + blender_max_z) / 2
        our_center_z = (our_min_z + our_max_z) / 2
        
        blender_center_x = sum(p[0] for p in blender_points) / len(blender_points)
        blender_center_y = sum(p[1] for p in blender_points) / len(blender_points)
        
        our_center_x = sum(p[0] for p in our_points) / len(our_points)
        our_center_y = sum(p[1] for p in our_points) / len(our_points)
        
        normalized_blender = []
        for x, y, z in blender_points:
            nx = (x - blender_center_x) * scale + our_center_x
            ny = (y - blender_center_y) * scale + our_center_y
            nz = (z - blender_center_z) * scale + our_center_z
            normalized_blender.append((nx, ny, nz))
        
        blender_points = normalized_blender
        
        # Recalculate ranges
        blender_z = [p[2] for p in blender_points]
        blender_min_z = min(blender_z)
        blender_max_z = max(blender_z)
        blender_height = blender_max_z - blender_min_z
        
        print(f"  Scale factor: {scale:.4f}")
        print(f"  Normalized Blender Z: {blender_min_z:.2f} to {blender_max_z:.2f} mm")
    
    # Filter side wall points (exclude top/bottom within 10% of height)
    margin = blender_height * 0.1
    blender_side = [p for p in blender_points 
                    if p[2] > blender_min_z + margin and p[2] < blender_max_z - margin]
    our_side = [p for p in our_points 
                if p[2] > our_min_z + margin and p[2] < our_max_z - margin]
    
    print(f"\nSide wall points:")
    print(f"  Blender: {len(blender_side)}")
    print(f"  Our:     {len(our_side)}")
    
    # Group by Z level
    def group_by_z(points, num_levels=20):
        if not points:
            return {}
        z_values = [p[2] for p in points]
        min_z = min(z_values)
        max_z = max(z_values)
        z_range = max_z - min_z
        
        levels = {}
        for p in points:
            # Normalize z to 0-1 range
            t = (p[2] - min_z) / z_range if z_range > 0 else 0
            # Map to level index
            level_idx = int(t * (num_levels - 1))
            if level_idx not in levels:
                levels[level_idx] = []
            levels[level_idx].append(p)
        
        return levels
    
    blender_levels = group_by_z(blender_side)
    our_levels = group_by_z(our_side)
    
    print(f"\nZ levels:")
    print(f"  Blender: {len(blender_levels)}")
    print(f"  Our:     {len(our_levels)}")
    
    # Calculate expected positions using cosine curve
    print(f"\nExpected (cosine curve): width=100, depth=70, height=6, recess=10")
    print(f"  Bottom: 100x70, Top: 80x50")
    
    # Sample Z levels and compare
    sample_levels = sorted(blender_levels.keys())
    if len(sample_levels) > 10:
        step = len(sample_levels) // 10
        sample_levels = sample_levels[::step][:10]
    
    print(f"\n{'Level':<6} {'Z(mm)':<8} {'Blend_Xmax':<12} {'Our_Xmax':<12} {'Expected':<12} {'Error':<12}")
    print("-" * 68)
    
    errors = []
    for level in sample_levels:
        # Calculate t value (0 at bottom, 1 at top)
        t = level / 19.0 if len(blender_levels) > 1 else 0
        
        # Calculate expected Z
        z = blender_min_z + t * blender_height
        
        # Expected inset using cosine curve
        expected_inset = 10.0 * (1 - math.cos(math.pi / 2 * t))
        expected_x = 50.0 - expected_inset
        
        blend_pts = blender_levels.get(level, [])
        our_pts = our_levels.get(level, [])
        
        blend_xmax = max((p[0] for p in blend_pts), default=0)
        our_xmax = max((p[0] for p in our_pts), default=0)
        
        error = abs(our_xmax - expected_x)
        errors.append(error)
        
        print(f"{level:<6} {z:<8.2f} {blend_xmax:<12.2f} {our_xmax:<12.2f} {expected_x:<12.2f} {error:<12.4f}")
    
    if errors:
        avg_err = sum(errors) / len(errors)
        max_err = max(errors)
        print(f"\n{'='*68}")
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
