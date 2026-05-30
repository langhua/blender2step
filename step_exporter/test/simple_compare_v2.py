"""Simple comparison of top shell between Blender test28.step and our test39.step."""
import re
import math

def parse_step_file(step_file):
    """Parse STEP file and extract geometry."""
    with open(step_file, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()
    
    # Extract CARTESIAN_POINT coordinates
    point_pattern = r'#(\d+)\s*=\s*CARTESIAN_POINT\s*\([^,]+,\s*\(\s*([^,\r\n]+)\s*,\s*([^,\r\n]+)\s*,\s*([^\)\r\n]+)\s*\)'
    points = {}
    for match in re.finditer(point_pattern, content):
        id_num = int(match.group(1))
        try:
            points[id_num] = (float(match.group(2)), float(match.group(3)), float(match.group(4)))
        except ValueError:
            pass  # Skip malformed points
    
    # Find VERTEX_POINT -> CARTESIAN_POINT mapping
    vertex_pattern = r'#(\d+)\s*=\s*VERTEX_POINT\s*\(\s*\'[^\']*\'\s*,\s*#(\d+)\s*\)'
    vertices = {}
    for match in re.finditer(vertex_pattern, content):
        vertices[int(match.group(1))] = int(match.group(2))
    
    # Find EDGE_CURVE -> VERTEX_POINT mapping
    edge_pattern = r'#(\d+)\s*=\s*EDGE_CURVE\s*\([^,]+,\s*#(\d+)\s*,\s*#(\d+)\s*,'
    edges = {}
    for match in re.finditer(edge_pattern, content):
        edges[int(match.group(1))] = (int(match.group(2)), int(match.group(3)))
    
    # Find CLOSED_SHELL entities (may span multiple lines)
    shell_pattern = r'#(\d+)\s*=\s*CLOSED_SHELL\s*\([^;]+\)\);'
    shells = {}
    for match in re.finditer(shell_pattern, content, re.DOTALL):
        shell_id = int(match.group(1))
        face_refs = [int(x) for x in re.findall(r'#(\d+)', match.group(0))]
        # Remove the shell ID itself from the list
        face_refs = [x for x in face_refs if x != shell_id]
        shells[shell_id] = face_refs
    
    return content, points, vertices, edges, shells

def extract_shell_points(content, face_ids, points, vertices, edges):
    """Extract all vertex points from a shell."""
    xyz_points = []
    for face_id in face_ids:
        # ADVANCED_FACE('',(#34),#47,.F.)
        face_pattern = rf'#{face_id}\s*=\s*ADVANCED_FACE\s*\([^,]*,\s*\(([^)]+)\)'
        face_match = re.search(face_pattern, content)
        if face_match:
            bound_refs = [int(x) for x in re.findall(r'#(\d+)', face_match.group(1))]
            for bound_ref in bound_refs:
                # FACE_BOUND('',#35,.F.)
                loop_pattern = rf'#{bound_ref}\s*=\s*FACE_BOUND\s*\([^,]*,\s*#(\d+)'
                loop_match = re.search(loop_pattern, content)
                if loop_match:
                    loop_id = int(loop_match.group(1))
                    # EDGE_LOOP('',(#36,#77,#116,#142))
                    oriented_pattern = rf'#{loop_id}\s*=\s*EDGE_LOOP\s*\([^,]*,\s*\(([^)]+)\)'
                    oriented_match = re.search(oriented_pattern, content)
                    if oriented_match:
                        edge_refs = [int(x) for x in re.findall(r'#(\d+)', oriented_match.group(1))]
                        for edge_ref in edge_refs:
                            # ORIENTED_EDGE('',*,*,#37,.T.)
                            oriented_edge_pattern = rf'#{edge_ref}\s*=\s*ORIENTED_EDGE\s*\([^)]*#(\d+)'
                            oriented_edge_match = re.search(oriented_edge_pattern, content)
                            if oriented_edge_match:
                                edge_curve_id = int(oriented_edge_match.group(1))
                                if edge_curve_id in edges:
                                    v1_id, v2_id = edges[edge_curve_id]
                                    for v_id in [v1_id, v2_id]:
                                        if v_id in vertices and vertices[v_id] in points:
                                            xyz_points.append(points[vertices[v_id]])
    return xyz_points

def main():
    print("=" * 60)
    print("Top Shell Comparison: Blender test28.step vs test39.step")
    print("=" * 60)
    
    # Parse Blender file
    b_content, b_points, b_vertices, b_edges, b_shells = parse_step_file('f:\\git\\blender2step\\step_exporter\\test\\test28.step')
    print(f"\nBlender test28.step:")
    print(f"  Shells: {list(b_shells.keys())}")
    
    # Parse our file
    o_content, o_points, o_vertices, o_edges, o_shells = parse_step_file('f:\\git\\blender2step\\step_exporter\\test39.step')
    print(f"\nOur test39.step:")
    print(f"  Shells: {list(o_shells.keys())}")
    
    # Extract top shell from Blender (shell #8084)
    if 8084 in b_shells:
        blender_pts = extract_shell_points(b_content, b_shells[8084], b_points, b_vertices, b_edges)
        print(f"\nBlender top shell (#8084): {len(blender_pts)} points")
    else:
        print("ERROR: Shell #8084 not found")
        return
    
    # Extract our shell (first shell)
    if o_shells:
        our_shell_id = list(o_shells.keys())[0]
        our_pts = extract_shell_points(o_content, o_shells[our_shell_id], o_points, o_vertices, o_edges)
        print(f"Our top shell (#{our_shell_id}): {len(our_pts)} points")
    else:
        print("ERROR: No shells found")
        return
    
    if not blender_pts or not our_pts:
        print("ERROR: Could not extract points")
        return
    
    # Normalize Blender coordinates to match our coordinate system
    # Blender: X centered ~60, Y centered ~3, Z from -5 to 5
    # Our: X centered 0, Y centered 0, Z from 5 to 15
    
    b_center_x = sum(p[0] for p in blender_pts) / len(blender_pts)
    b_center_y = sum(p[1] for p in blender_pts) / len(blender_pts)
    b_center_z = sum(p[2] for p in blender_pts) / len(blender_pts)
    
    o_center_x = sum(p[0] for p in our_pts) / len(our_pts)
    o_center_y = sum(p[1] for p in our_pts) / len(our_pts)
    o_center_z = sum(p[2] for p in our_pts) / len(our_pts)
    
    # Normalize Blender points to our coordinate system
    normalized_blender_pts = []
    for p in blender_pts:
        nx = p[0] - b_center_x + o_center_x
        ny = p[1] - b_center_y + o_center_y
        nz = p[2] - b_center_z + o_center_z
        normalized_blender_pts.append((nx, ny, nz))
    
    blender_pts = normalized_blender_pts
    
    # Analyze Z ranges
    b_z = [p[2] for p in blender_pts]
    o_z = [p[2] for p in our_pts]
    
    print(f"\nZ-coordinate ranges:")
    print(f"  Blender: {min(b_z):.2f} to {max(b_z):.2f} mm (height: {max(b_z)-min(b_z):.2f} mm)")
    print(f"  Our:     {min(o_z):.2f} to {max(o_z):.2f} mm (height: {max(o_z)-min(o_z):.2f} mm)")
    
    # Analyze X ranges at different Z levels
    def analyze_by_z(points, num_levels=10):
        z_vals = [p[2] for p in points]
        min_z, max_z = min(z_vals), max(z_vals)
        z_range = max_z - min_z
        
        levels = {}
        for p in points:
            t = (p[2] - min_z) / z_range if z_range > 0 else 0
            level = int(t * (num_levels - 1))
            if level not in levels:
                levels[level] = []
            levels[level].append(p)
        
        return levels, min_z, max_z
    
    b_levels, b_min_z, b_max_z = analyze_by_z(blender_pts)
    o_levels, o_min_z, o_max_z = analyze_by_z(our_pts)
    
    print(f"\n{'Level':<6} {'Z':<8} {'Blend_Xmax':<12} {'Blend_Xmin':<12} {'Our_Xmax':<12} {'Our_Xmin':<12}")
    print("-" * 68)
    
    for level in sorted(b_levels.keys()):
        t = level / 9.0
        z = b_min_z + t * (b_max_z - b_min_z)
        
        b_pts = b_levels.get(level, [])
        o_pts = o_levels.get(level, [])
        
        b_xmax = max((p[0] for p in b_pts), default=0)
        b_xmin = min((p[0] for p in b_pts), default=0)
        o_xmax = max((p[0] for p in o_pts), default=0)
        o_xmin = min((p[0] for p in o_pts), default=0)
        
        print(f"{level:<6} {z:<8.2f} {b_xmax:<12.2f} {b_xmin:<12.2f} {o_xmax:<12.2f} {o_xmin:<12.2f}")
    
    # Calculate cosine curve expected values
    print(f"\n{'='*68}")
    print(f"Expected cosine curve (width=100, depth=70, height=6, recess=10):")
    print(f"  Bottom: 100x70, Top: 80x50")
    print(f"  X range at bottom: -50 to 50")
    print(f"  X range at top: -40 to 40")
    
    print(f"\n{'Level':<6} {'t':<6} {'Exp_Xmax':<12} {'Blend_Xmax':<12} {'Our_Xmax':<12} {'Blend_Err':<12} {'Our_Err':<12}")
    print("-" * 78)
    
    blend_errors = []
    our_errors = []
    
    for level in sorted(b_levels.keys()):
        t = level / 9.0
        
        # Expected inset using cosine curve
        expected_inset = 10.0 * (1 - math.cos(math.pi / 2 * t))
        expected_xmax = 50.0 - expected_inset
        
        b_pts = b_levels.get(level, [])
        o_pts = o_levels.get(level, [])
        
        b_xmax = max((p[0] for p in b_pts), default=0)
        o_xmax = max((p[0] for p in o_pts), default=0)
        
        # Need to normalize Blender X to match our coordinate system
        # Blender shell #8084 has X: 10.56 to 109.44 (centered around 60)
        # Our shell has X: -50 to 50 (centered around 0)
        # Scale: Blender width ~99, Our width ~100
        b_center_x = sum(p[0] for p in blender_pts) / len(blender_pts)
        o_center_x = sum(p[0] for p in our_pts) / len(our_pts)
        b_width = max(p[0] for p in blender_pts) - min(p[0] for p in blender_pts)
        o_width = max(p[0] for p in our_pts) - min(p[0] for p in our_pts)
        
        # Normalize Blender X
        scale = o_width / b_width if b_width > 0 else 1
        normalized_b_xmax = (b_xmax - b_center_x) * scale + o_center_x
        normalized_b_xmin = (min(p[0] for p in b_pts) - b_center_x) * scale + o_center_x
        
        blend_err = abs(normalized_b_xmax - expected_xmax)
        our_err = abs(o_xmax - expected_xmax)
        
        blend_errors.append(blend_err)
        our_errors.append(our_err)
        
        print(f"{level:<6} {t:<6.2f} {expected_xmax:<12.2f} {normalized_b_xmax:<12.2f} {o_xmax:<12.2f} {blend_err:<12.4f} {our_err:<12.4f}")
    
    if blend_errors and our_errors:
        print(f"\n{'='*78}")
        print(f"Error Summary (vs expected cosine curve):")
        print(f"  Blender - Average: {sum(blend_errors)/len(blend_errors):.4f} mm, Max: {max(blend_errors):.4f} mm")
        print(f"  Our     - Average: {sum(our_errors)/len(our_errors):.4f} mm, Max: {max(our_errors):.4f} mm")

if __name__ == '__main__':
    main()
