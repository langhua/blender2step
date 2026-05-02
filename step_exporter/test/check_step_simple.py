import re

step_file = r"F:\git\blender2step\step_exporter\test28.step"

with open(step_file, 'r') as f:
    content = f.read()

# 查找所有PRODUCT定义（每个物体）
products = re.findall(r'#(\d+)=PRODUCT\([^)]+\)', content)
print(f'Found {len(products)} products in STEP file')
print('=' * 80)

# 查找PRODUCT定义中的名称
for i, match in enumerate(products, 1):
    # 提取产品名称
    name_match = re.search(r"'([^']+)'", match)
    name = name_match.group(1) if name_match else 'Unknown'
    print(f'Product {i}: {name}')

# 查找ADVANCED_BREP_SHAPE_REPRESENTATION
shape_reps = re.findall(r'ADVANCED_BREP_SHAPE_REPRESENTATION', content)
print(f'\nFound {len(shape_reps)} shape representations')

# 查找MANIFOLD_SOLID_BREP（实体）
solids = re.findall(r'MANIFOLD_SOLID_BREP', content)
print(f'Found {len(solids)} manifold solids')

# 查找文件中的尺寸信息（通过搜索较大的数值）
large_values = re.findall(r'#\d+=CARTESIAN_POINT\([^)]+\)', content)
print(f'\nFound {len(large_values)} cartesian points')

# 分析前10个点的坐标
for i, point in enumerate(large_values[:10]):
    coords = re.findall(r'[-]?\d+\.?\d+', point)
    if coords:
        print(f'Point {i+1}: ({", ".join(coords)})')
