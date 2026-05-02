import re
import sys

if len(sys.argv) < 2:
    print("Usage: python check_coords.py <step_file>")
    sys.exit(1)

step_file = sys.argv[1]

with open(step_file, 'r', encoding='utf-8') as f:
    content = f.read()

# 查找所有CARTESIAN_POINT
point_map = {}
for match in re.finditer(r"#(\d+)\s*=\s*CARTESIAN_POINT\s*\(\s*''\s*,\s*\(([^)]+)\)", content):
    point_id = int(match.group(1))
    coords = [float(x.strip()) for x in match.group(2).split(',')]
    point_map[point_id] = coords

print(f'Found {len(point_map)} CARTESIAN_POINT entries')

# 检查是否有坐标值超过1000（表示没有被正确缩放）
large_coords = []
for pid, coords in point_map.items():
    if any(abs(c) > 1000 for c in coords):
        large_coords.append((pid, coords))

if large_coords:
    print(f'\nFound {len(large_coords)} points with coordinates > 1000 (likely not scaled properly):')
    for pid, coords in large_coords[:10]:
        print(f'  Point #{pid}: ({coords[0]:.1f}, {coords[1]:.1f}, {coords[2]:.1f})')
else:
    print('\nAll coordinates are within reasonable range (< 1000)')

# 打印前20个点的坐标
print('\nFirst 20 CARTESIAN_POINT coordinates:')
for i, (pid, coords) in enumerate(sorted(point_map.items())[:20]):
    if len(coords) >= 3:
        print(f'  Point #{pid}: ({coords[0]:.2f}, {coords[1]:.2f}, {coords[2]:.2f})')
    else:
        print(f'  Point #{pid}: ({", ".join(f"{c:.2f}" for c in coords)})')
