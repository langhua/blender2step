"""Simple script to extract points from STEP files."""
import re

def extract_points_from_step(step_file):
    """Extract all vertex points from a STEP file."""
    with open(step_file, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()
    
    # Extract all CARTESIAN_POINT coordinates
    point_pattern = r'#(\d+)\s*=\s*CARTESIAN_POINT\s*\(\s*\'[^\']*\'\s*,\s*\(\s*([-+]?\d*\.?\d+(?:[eE][-+]?\d+)?)\s*,\s*([-+]?\d*\.?\d+(?:[eE][-+]?\d+)?)\s*,\s*([-+]?\d*\.?\d+(?:[eE][-+]?\d+)?)\s*\)\s*\)'
    points = {}
    for match in re.finditer(point_pattern, content):
        id_num = int(match.group(1))
        x = float(match.group(2))
        y = float(match.group(3))
        z = float(match.group(4))
        points[id_num] = (x, y, z)
    
    # Find VERTEX_POINT -> CARTESIAN_POINT mapping
    vertex_pattern = r'#(\d+)\s*=\s*VERTEX_POINT\s*\(\s*\'[^\']*\'\s*,\s*#(\d+)\s*\)'
    vertices = {}
    for match in re.finditer(vertex_pattern, content):
        vertex_id = int(match.group(1))
        point_id = int(match.group(2))
        vertices[vertex_id] = point_id
    
    # Find EDGE_CURVE -> VERTEX_POINT mapping
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
    
    print(f"\nFile: {step_file}")
    print(f"  Total CARTESIAN_POINTs: {len(points)}")
    print(f"  Total VERTEX_POINTs: {len(vertices)}")
    print(f"  Total EDGE_CURVEs: {len(edges)}")
    print(f"  CLOSED_SHELLs: {list(shells.keys())}")
    
    # Extract points from each shell
    for shell_id, face_ids in shells.items():
        shell_points = []
        for face_id in face_ids:
            # ADVANCED_FACE('',(#34),#47,.F.)
            face_pattern = rf'#{face_id}=\s*ADVANCED_FACE\s*\([^,]+,\s*\(([^)]+)\)'
            face_match = re.search(face_pattern, content)
            if face_match:
                bound_refs = [int(x) for x in re.findall(r'#(\d+)', face_match.group(1))]
                for bound_ref in bound_refs:
                    # FACE_BOUND('',#35,.F.)
                    loop_pattern = rf'#{bound_ref}=\s*FACE_BOUND\s*\([^,]+,\s*#(\d+)'
                    loop_match = re.search(loop_pattern, content)
                    if loop_match:
                        loop_id = int(loop_match.group(1))
                        # EDGE_LOOP('',(#36,#77,#116,#142))
                        oriented_pattern = rf'#{loop_id}=\s*EDGE_LOOP\s*\([^,]+,\s*\(([^)]+)\)'
                        oriented_match = re.search(oriented_pattern, content)
                        if oriented_match:
                            edge_refs = [int(x) for x in re.findall(r'#(\d+)', oriented_match.group(1))]
                            for edge_ref in edge_refs:
                                # ORIENTED_EDGE('',*,*,#37,.T.)
                                oriented_edge_pattern = rf'#{edge_ref}=\s*ORIENTED_EDGE\s*\([^,]+,\s*\*,\s*\*,\s*#(\d+)'
                                oriented_edge_match = re.search(oriented_edge_pattern, content)
                                if oriented_edge_match:
                                    edge_curve_id = int(oriented_edge_match.group(1))
                                    if edge_curve_id in edges:
                                        v1_id, v2_id = edges[edge_curve_id]
                                        for v_id in [v1_id, v2_id]:
                                            if v_id in vertices and vertices[v_id] in points:
                                                shell_points.append(points[vertices[v_id]])
        
        if shell_points:
            z_vals = [p[2] for p in shell_points]
            x_vals = [p[0] for p in shell_points]
            y_vals = [p[1] for p in shell_points]
            print(f"\n  Shell #{shell_id}:")
            print(f"    Faces: {len(face_ids)}")
            print(f"    Points: {len(shell_points)}")
            print(f"    X: {min(x_vals):.2f} to {max(x_vals):.2f}")
            print(f"    Y: {min(y_vals):.2f} to {max(y_vals):.2f}")
            print(f"    Z: {min(z_vals):.2f} to {max(z_vals):.2f}")
            print(f"    Sample points:")
            for p in shell_points[:3]:
                print(f"      ({p[0]:.2f}, {p[1]:.2f}, {p[2]:.2f})")

if __name__ == '__main__':
    extract_points_from_step('f:\\git\\blender2step\\step_exporter\\test\\test28.step')
    extract_points_from_step('f:\\git\\blender2step\\step_exporter\\test39.step')
