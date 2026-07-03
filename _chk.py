import re

content = open(r'F:\git\blender2step\step_exporter\test28.step').read()

types = ['MANIFOLD_SOLID_BREP','CLOSED_SHELL','ADVANCED_FACE',
         'SHAPE_DEFINITION_REPRESENTATION','ADVANCED_BREP_SHAPE_REPRESENTATION',
         'PRODUCT_DEFINITION_SHAPE','GEOMETRICALLY_BOUNDED_WIREFRAME']

for t in types:
    print(f'{t}: {len(re.findall(t, content))}')

shells = re.findall(r'#\d+\s*=\s*CLOSED_SHELL\s*\([^,]*,\s*\(([^)]*)\)', content)
for i, s in enumerate(shells):
    faces = [x.strip() for x in s.split(',') if x.strip().startswith('#')]
    print(f'CLOSED_SHELL #{i+1}: {len(faces)} faces')

entity_count = len(re.findall(r"^#\d+\s*=", content, re.MULTILINE))
print(f'Size: {len(content):,} bytes')
print(f'Entities: {entity_count}')
