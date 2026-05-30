import re

with open('f:\\git\\blender2step\\step_exporter\\test39.step', 'r', encoding='utf-8', errors='ignore') as f:
    content = f.read()

# Extract vertices
vertex_pattern = r'#(\d+)\s*=\s*VERTEX_POINT\s*\(\s*\'[^\']*\'\s*,\s*#(\d+)\s*\)'
vertices = {}
for m in re.finditer(vertex_pattern, content):
    vertices[int(m.group(1))] = int(m.group(2))

print(f'Vertex #38 -> Point #{vertices.get(38, "N/A")}')
print(f'Vertex #40 -> Point #{vertices.get(40, "N/A")}')
print(f'Total vertices: {len(vertices)}')

# Extract points
point_pattern = r'#(\d+)\s*=\s*CARTESIAN_POINT\s*\(\s*\'[^\']*\'\s*,\s*\(\s*([-+]?\d*\.?\d+(?:[eE][-+]?\d+)?)\s*,\s*([-+]?\d*\.?\d+(?:[eE][-+]?\d+)?)\s*,\s*([-+]?\d*\.?\d+(?:[eE][-+]?\d+)?)\s*\)'
points = {}
for m in re.finditer(point_pattern, content):
    point_id = int(m.group(1))
    points[point_id] = (float(m.group(2)), float(m.group(3)), float(m.group(4)))

print(f'\nTotal points: {len(points)}')
print(f'Point #39 in points: {39 in points}')
if 39 in points:
    print(f'Point #39: {points[39]}')
