import re

with open('test28.step', 'r', encoding='utf-8') as f:
    content = f.read()

# 查找所有CARTESIAN_POINT并建立ID到坐标的映射
point_map = {}
for match in re.finditer(r"#(\d+)\s*=\s*CARTESIAN_POINT\s*\(\s*''\s*,\s*\(([^)]+)\)\)", content):
    point_id = int(match.group(1))
    coords = [float(x.strip()) for x in match.group(2).split(',')]
    point_map[point_id] = coords

print(f'Found {len(point_map)} CARTESIAN_POINT entries')

# 查找所有VERTEX_POINT并建立ID到坐标的映射
vertex_map = {}
for match in re.finditer(r"#(\d+)\s*=\s*VERTEX_POINT\s*\(\s*''\s*,\s*#(\d+)\s*\)", content):
    vertex_id = int(match.group(1))
    point_id = int(match.group(2))
    if point_id in point_map:
        vertex_map[vertex_id] = point_map[point_id]

print(f'Found {len(vertex_map)} VERTEX_POINT entries')

# 查找所有MANIFOLD_SOLID_BREP
solids = []
for match in re.finditer(r"#(\d+)\s*=\s*MANIFOLD_SOLID_BREP\s*\(\s*''\s*,\s*#(\d+)\s*\)", content):
    solid_id = int(match.group(1))
    shell_id = int(match.group(2))
    solids.append((solid_id, shell_id))

print(f'\nFound {len(solids)} MANIFOLD_SOLID_BREP entries')

# 对每个solid，查找其所有顶点
for idx, (solid_id, shell_id) in enumerate(solids):
    # 查找CLOSED_SHELL定义
    shell_pattern = rf"#{shell_id}\s*=\s*CLOSED_SHELL\s*\(\s*''\s*,\s*\(([^)]+)\)\)"
    shell_match = re.search(shell_pattern, content)
    
    if not shell_match:
        continue
    
    # 提取所有面ID
    face_ids = [int(x) for x in re.findall(r'#(\d+)', shell_match.group(1))]
    
    # 查找这些面中的所有顶点
    all_coords = []
    for face_id in face_ids:
        # 查找FACE_BOUND -> EDGE_LOOP -> EDGE_CURVE -> VERTEX_POINT
        # 简化：直接查找所有引用这个面的EDGE_CURVE
        edge_pattern = rf"EDGE_CURVE\s*\(\s*''\s*,\s*#(\d+)\s*,\s*#(\d+)"
        
        # 在这个面附近查找边
        face_pos = content.find(f'#{face_id}')
        if face_pos == -1:
            continue
        
        # 查找接下来的2000字符中的EDGE_CURVE
        face_section = content[face_pos:face_pos+2000]
        
        for edge_match in re.finditer(edge_pattern, face_section):
            v1_id = int(edge_match.group(1))
            v2_id = int(edge_match.group(2))
            
            if v1_id in vertex_map:
                all_coords.append(vertex_map[v1_id])
            if v2_id in vertex_map:
                all_coords.append(vertex_map[v2_id])
    
    if all_coords:
        xs = [c[0] for c in all_coords]
        ys = [c[1] for c in all_coords]
        zs = [c[2] for c in all_coords]
        
        center_x = (min(xs) + max(xs)) / 2
        center_y = (min(ys) + max(ys)) / 2
        center_z = (min(zs) + max(zs)) / 2
        
        print(f'Object {idx+1}: Center=({center_x:.1f}, {center_y:.1f}, {center_z:.1f}), '
              f'Bounds X[{min(xs):.1f},{max(xs):.1f}] Y[{min(ys):.1f},{max(ys):.1f}] Z[{min(zs):.1f},{max(zs):.1f}]')
    else:
        print(f'Object {idx+1}: No vertices found')
