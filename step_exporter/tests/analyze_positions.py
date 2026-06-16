import re
import sys

if len(sys.argv) < 2:
    print("Usage: python analyze_positions.py <step_file>")
    sys.exit(1)

step_file = sys.argv[1]

with open(step_file, 'r', encoding='utf-8') as f:
    content = f.read()

# 查找所有PRODUCT（支持多行）
product_pattern = r'#(\d+)\s*=\s*PRODUCT\s*\([^;]+\);'
products = list(re.finditer(product_pattern, content, re.DOTALL))

print(f'Found {len(products)} PRODUCT entries\n')

for i, product_match in enumerate(products):
    product_text = product_match.group(0)
    
    # 提取产品名称
    name_match = re.search(r"PRODUCT\s*\(\s*'[^']*'\s*,\s*\"([^\"]+)\"", product_text)
    product_name = name_match.group(1) if name_match else "Unknown"
    
    print(f'Product {i+1}: {product_name}')
    
    # 查找该PRODUCT对应的MANIFOLD_SOLID_BREP
    # 先找到SHAPE_DEFINITION_REPRESENTATION
    product_id = product_match.group(1)
    
    # 查找引用这个PRODUCT的SHAPE_DEFINITION_REPRESENTATION
    sdr_pattern = rf'SHAPE_DEFINITION_REPRESENTATION\s*\(\s*#(\d+)\s*,\s*#{product_id}\s*\)'
    sdr_match = re.search(sdr_pattern, content)
    
    if not sdr_match:
        # 尝试查找PRODUCT_DEFINITION_SHAPE引用PRODUCT_DEFINITION
        pd_pattern = rf'PRODUCT_DEFINITION\s*\(\s*\'[^\']*\'\s*,\s*\'[^\']*\'\s*,\s*#(\d+)\s*,\s*#{product_id}\s*\)'
        pd_match = re.search(pd_pattern, content)
        if pd_match:
            pd_id = pd_match.group(1)
            # 查找PRODUCT_DEFINITION_SHAPE引用这个PRODUCT_DEFINITION
            pds_pattern = rf'PRODUCT_DEFINITION_SHAPE\s*\(\s*\'[^\']*\'\s*,\s*\'[^\']*\'\s*,\s*#{pd_id}\s*\)'
            pds_match = re.search(pds_pattern, content)
            if pds_match:
                pds_id = pds_match.start()
                # 查找SHAPE_DEFINITION_REPRESENTATION引用这个PRODUCT_DEFINITION_SHAPE
                sdr_pattern2 = rf'SHAPE_DEFINITION_REPRESENTATION\s*\(\s*#{pds_match.group(0).split("#")[1].split("(")[0]}\s*,\s*#(\d+)\s*\)'
    
    # 简化方法：查找该区域的所有CARTESIAN_POINT
    start_pos = product_match.start()
    if i + 1 < len(products):
        end_pos = products[i+1].start()
    else:
        end_pos = len(content)
    
    section = content[start_pos:end_pos]
    
    # 查找所有3D CARTESIAN_POINT（有3个坐标的）
    point_pattern = r'CARTESIAN_POINT\s*\(\s*\'\'\s*,\s*\(([^)]+)\)\s*\)'
    points = re.findall(point_pattern, section)
    
    points_3d = []
    for point_str in points:
        coords = [float(x.strip()) for x in point_str.split(',')]
        if len(coords) == 3:
            points_3d.append(coords)
    
    if points_3d:
        print(f'  Found {len(points_3d)} 3D points')
        
        # 计算边界框
        min_x = min(p[0] for p in points_3d)
        max_x = max(p[0] for p in points_3d)
        min_y = min(p[1] for p in points_3d)
        max_y = max(p[1] for p in points_3d)
        min_z = min(p[2] for p in points_3d)
        max_z = max(p[2] for p in points_3d)
        
        center_x = (min_x + max_x) / 2
        center_y = (min_y + max_y) / 2
        center_z = (min_z + max_z) / 2
        
        print(f'  Bounding box: X[{min_x:.2f}, {max_x:.2f}] Y[{min_y:.2f}, {max_y:.2f}] Z[{min_z:.2f}, {max_z:.2f}]')
        print(f'  Center: ({center_x:.2f}, {center_y:.2f}, {center_z:.2f})')
    else:
        print(f'  No 3D points found')
    
    print()
