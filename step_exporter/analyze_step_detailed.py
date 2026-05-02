import re
import sys

if len(sys.argv) < 2:
    print("Usage: python analyze_step_detailed.py <step_file>")
    sys.exit(1)

step_file = sys.argv[1]

with open(step_file, 'r', encoding='utf-8') as f:
    content = f.read()

# 查找所有CARTESIAN_POINT并建立ID到坐标的映射
point_map = {}
for match in re.finditer(r"#(\d+)\s*=\s*CARTESIAN_POINT\s*\(\s*''\s*,\s*\(([^)]+)\)", content):
    point_id = int(match.group(1))
    coords = [float(x.strip()) for x in match.group(2).split(',')]
    point_map[point_id] = coords

print(f'Found {len(point_map)} CARTESIAN_POINT entries')

# 查找所有MANIFOLD_SOLID_BREP
for i, match in enumerate(re.finditer(r'#(\d+)\s*=\s*MANIFOLD_SOLID_BREP\s*\(\s*''\s*,\s*#(\d+)\s*\)', content)):
    solid_id = int(match.group(1))
    shell_id = int(match.group(2))
    
    # 查找对应的CLOSED_SHELL
    shell_match = re.search(r'#' + str(shell_id) + r'\s*=\s*CLOSED_SHELL\s*\(\s*\(([^)]+)\)', content)
    if shell_match:
        face_ids = [int(x.strip().lstrip('#')) for x in shell_match.group(1).split(',') if x.strip()]
        
        # 收集所有顶点
        all_vertices = []
        for face_id in face_ids[:3]:  # 只检查前3个面
            # 查找FACE_OUTER_BOUND
            face_match = re.search(r'#' + str(face_id) + r'\s*=\s*FACE_BOUND\s*\(\s*''\s*,\s*#(\d+)\s*,\s*\w+\s*\)', content)
            if face_match:
                bound_id = int(face_match.group(1))
                # 查找EDGE_LOOP
                loop_match = re.search(r'#' + str(bound_id) + r'\s*=\s*EDGE_LOOP\s*\(\s*\(([^)]+)\)', content)
                if loop_match:
                    edge_ids = [int(x.strip().lstrip('#')) for x in loop_match.group(1).split(',') if x.strip()]
                    
                    for edge_id in edge_ids[:2]:  # 只检查前2条边
                        # 查找EDGE_CURVE
                        edge_match = re.search(r'#' + str(edge_id) + r'\s*=\s*EDGE_CURVE\s*\(\s*''\s*,\s*#(\d+)\s*,\s*#(\d+)\s*,\s*#(\d+)\s*,\s*\w+\s*\)', content)
                        if edge_match:
                            start_id = int(edge_match.group(1))
                            end_id = int(edge_match.group(2))
                            
                            if start_id in point_map:
                                all_vertices.append(point_map[start_id])
                            if end_id in point_map:
                                all_vertices.append(point_map[end_id])
        
        if all_vertices:
            xs = [v[0] for v in all_vertices]
            ys = [v[1] for v in all_vertices]
            zs = [v[2] for v in all_vertices]
            
            center_x = (min(xs) + max(xs)) / 2
            center_y = (min(ys) + max(ys)) / 2
            center_z = (min(zs) + max(zs)) / 2
            
            print(f'Object {i+1}: Center=({center_x:.1f}, {center_y:.1f}, {center_z:.1f})')
            print(f'  Bounds X[{min(xs):.1f},{max(xs):.1f}] Y[{min(ys):.1f},{max(ys):.1f}] Z[{min(zs):.1f},{max(zs):.1f}]')
            print(f'  Size: {max(xs)-min(xs):.1f} x {max(ys)-min(ys):.1f} x {max(zs)-min(zs):.1f}')
            print()
