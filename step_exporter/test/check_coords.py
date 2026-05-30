import re

def parse_step_file(step_file):
    with open(step_file, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()
    
    point_pattern = r'#(\d+)\s*=\s*CARTESIAN_POINT\s*\([^,]+,\s*\(\s*([^,\r\n]+)\s*,\s*([^,\r\n]+)\s*,\s*([^\)\r\n]+)\s*\)'
    points = {}
    for match in re.finditer(point_pattern, content):
        try:
            points[int(match.group(1))] = (float(match.group(2)), float(match.group(3)), float(match.group(4)))
        except ValueError:
            pass
    
    vertex_pattern = r'#(\d+)\s*=\s*VERTEX_POINT\s*\([^,]+,\s*#(\d+)\s*\)'
    vertices = {}
    for match in re.finditer(vertex_pattern, content):
        vertices[int(match.group(1))] = int(match.group(2))
    
    edge_pattern = r'#(\d+)\s*=\s*EDGE_CURVE\s*\([^,]+,\s*#(\d+)\s*,\s*#(\d+)\s*,'
    edges = {}
    for match in re.finditer(edge_pattern, content):
        edges[int(match.group(1))] = (int(match.group(2)), int(match.group(3)))
    
    shell_pattern = r'#(\d+)\s*=\s*CLOSED_SHELL\s*\([^;]+\)\);'
    shells = {}
    for match in re.finditer(shell_pattern, content, re.DOTALL):
        shell_id = int(match.group(1))
        face_refs = [int(x) for x in re.findall(r'#(\d+)', match.group(0))]
        face_refs = [x for x in face_refs if x != shell_id]
        shells[shell_id] = face_refs
    
    return content, points, vertices, edges, shells

def extract_shell_points(content, face_ids, points, vertices, edges):
    xyz_points = []
    for face_id in face_ids:
        face_pattern = rf'#{face_id}\s*=\s*ADVANCED_FACE\s*\([^,]*,\s*\(([^)]+)\)'
        face_match = re.search(face_pattern, content)
        if face_match:
            bound_refs = [int(x) for x in re.findall(r'#(\d+)', face_match.group(1))]
            for bound_ref in bound_refs:
                loop_pattern = rf'#{bound_ref}\s*=\s*FACE_BOUND\s*\([^,]*,\s*#(\d+)'
                loop_match = re.search(loop_pattern, content)
                if loop_match:
                    loop_id = int(loop_match.group(1))
                    oriented_pattern = rf'#{loop_id}\s*=\s*EDGE_LOOP\s*\([^,]*,\s*\(([^)]+)\)'
                    oriented_match = re.search(oriented_pattern, content)
                    if oriented_match:
                        edge_refs = [int(x) for x in re.findall(r'#(\d+)', oriented_match.group(1))]
                        for edge_ref in edge_refs:
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

# Parse both files
b_content, b_points, b_vertices, b_edges, b_shells = parse_step_file('f:\\git\\blender2step\\step_exporter\\test\\test28.step')
o_content, o_points, o_vertices, o_edges, o_shells = parse_step_file('f:\\git\\blender2step\\step_exporter\\test39.step')

print("Blender test28.step:")
print(f"  Total points: {len(b_points)}")
print(f"  Total vertices: {len(b_vertices)}")
print(f"  Shells: {list(b_shells.keys())}")

print("\nOur test39.step:")
print(f"  Total points: {len(o_points)}")
print(f"  Total vertices: {len(o_vertices)}")
print(f"  Shells: {list(o_shells.keys())}")

# Extract shell #8084 from Blender
if 8084 in b_shells:
    blender_pts = extract_shell_points(b_content, b_shells[8084], b_points, b_vertices, b_edges)
    print(f"\nBlender shell #8084: {len(blender_pts)} points")
    if blender_pts:
        x_vals = [p[0] for p in blender_pts]
        y_vals = [p[1] for p in blender_pts]
        z_vals = [p[2] for p in blender_pts]
        print(f"  X: {min(x_vals):.2f} to {max(x_vals):.2f}")
        print(f"  Y: {min(y_vals):.2f} to {max(y_vals):.2f}")
        print(f"  Z: {min(z_vals):.2f} to {max(z_vals):.2f}")

# Extract shell #32 from our file
if 32 in o_shells:
    our_pts = extract_shell_points(o_content, o_shells[32], o_points, o_vertices, o_edges)
    print(f"\nOur shell #32: {len(our_pts)} points")
    if our_pts:
        x_vals = [p[0] for p in our_pts]
        y_vals = [p[1] for p in our_pts]
        z_vals = [p[2] for p in our_pts]
        print(f"  X: {min(x_vals):.2f} to {max(x_vals):.2f}")
        print(f"  Y: {min(y_vals):.2f} to {max(y_vals):.2f}")
        print(f"  Z: {min(z_vals):.2f} to {max(z_vals):.2f}")
