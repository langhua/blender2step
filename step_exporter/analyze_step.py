import re
import sys

if len(sys.argv) < 2:
    print("Usage: python analyze_step.py <step_file>")
    sys.exit(1)

step_file = sys.argv[1]

with open(step_file, 'r', encoding='utf-8') as f:
    content = f.read()

# 查找所有ADVANCED_BREP_SHAPE_REPRESENTATION
adv_brep_matches = re.findall(r'#(\d+)\s*=\s*ADVANCED_BREP_SHAPE_REPRESENTATION', content)
print(f'Found {len(adv_brep_matches)} ADVANCED_BREP_SHAPE_REPRESENTATION entries')

# 查找所有MANIFOLD_SOLID_BREP
manifold_matches = re.findall(r'#(\d+)\s*=\s*MANIFOLD_SOLID_BREP', content)
print(f'Found {len(manifold_matches)} MANIFOLD_SOLID_BREP entries')

# 查找所有BREP_WITH_VOIDS
brep_voids_matches = re.findall(r'#(\d+)\s*=\s*BREP_WITH_VOIDS', content)
print(f'Found {len(brep_voids_matches)} BREP_WITH_VOIDS entries')

# 查找所有SHAPE_REPRESENTATION
shape_repr_matches = re.findall(r'#(\d+)\s*=\s*SHAPE_REPRESENTATION', content)
print(f'Found {len(shape_repr_matches)} SHAPE_REPRESENTATION entries')

# 查找所有PRODUCT
product_matches = list(re.finditer(r'#(\d+)\s*=\s*PRODUCT\s*\(\s*\'\'\s*,\s*"([^"]+)"', content))
print(f'Found {len(product_matches)} PRODUCT entries')

# 打印所有产品名称
for match in product_matches:
    print(f'  Product ID={match.group(1)}: {match.group(2)}')

# 查找所有CONTEXT_DEPENDENT_SHAPE_REPRESENTATION
context_dep_matches = re.findall(r'#(\d+)\s*=\s*CONTEXT_DEPENDENT_SHAPE_REPRESENTATION', content)
print(f'Found {len(context_dep_matches)} CONTEXT_DEPENDENT_SHAPE_REPRESENTATION entries')

# 查找所有PRODUCT_DEFINITION_SHAPE_REPRESENTATION
prod_def_shape_matches = re.findall(r'#(\d+)\s*=\s*PRODUCT_DEFINITION_SHAPE_REPRESENTATION', content)
print(f'Found {len(prod_def_shape_matches)} PRODUCT_DEFINITION_SHAPE_REPRESENTATION entries')
