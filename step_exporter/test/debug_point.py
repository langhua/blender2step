import re

with open('f:\\git\\blender2step\\step_exporter\\test39.step', 'r', encoding='utf-8', errors='ignore') as f:
    content = f.read()

# Test the exact pattern on line 64
test_line = "#39 = CARTESIAN_POINT('',(-30.,-35.,15.));"
print(f"Test line: {test_line}")

# Pattern from simple_compare_v2.py
point_pattern = r'#(\d+)\s*=\s*CARTESIAN_POINT\s*\(\s*\'[^\']*\'\s*,\s*\(\s*([-+]?\d*\.?\d+(?:[eE][-+]?\d+)?)\s*,\s*([-+]?\d*\.?\d+(?:[eE][-+]?\d+)?)\s*,\s*([-+]?\d*\.?\d+(?:[eE][-+]?\d+)?)\s*\)'

match = re.search(point_pattern, test_line)
print(f"Match on test line: {match}")

if match:
    print(f"  ID: {match.group(1)}")
    print(f"  X: {match.group(2)}")
    print(f"  Y: {match.group(3)}")
    print(f"  Z: {match.group(4)}")

# Try a simpler pattern
simple_pattern = r'#(\d+)\s*=\s*CARTESIAN_POINT\s*\([^,]+,\s*\(\s*([^,]+)\s*,\s*([^,]+)\s*,\s*([^)]+)\s*\)'
match2 = re.search(simple_pattern, test_line)
print(f"\nSimple pattern match: {match2}")
if match2:
    print(f"  ID: {match2.group(1)}")
    print(f"  X: {match2.group(2)}")
    print(f"  Y: {match2.group(3)}")
    print(f"  Z: {match2.group(4)}")

# Count total points with simple pattern
all_matches = re.findall(simple_pattern, content)
print(f"\nTotal points with simple pattern: {len(all_matches)}")
