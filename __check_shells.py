import re
c = open(r'F:\git\blender2step\step_exporter\test28.step', 'r', encoding='utf-8').read()

# Find CLOSED_SHELL entities
shells = re.findall(r'#(\d+)=\s*CLOSED_SHELL\s*\(.*?\)\s*;', c, re.DOTALL)
print(f"Found {len(shells)} CLOSED_SHELL entities")

for i, sh in enumerate(shells):
    # count face refs
    faces = re.findall(r'#(\d+)', sh)
    print(f"Shell {i+1}: {len(faces)} face refs")
    # print first 200 chars
    print(f"  Preview: {sh[:200]}")

# Find CARTESIAN_POINT with extreme Y values
points = re.findall(r"#(\d+)=\s*CARTESIAN_POINT\s*\([^)]*'\)\s*\(\s*([^,]+),\s*([^,]+),\s*([^)]+)\)", c)
print(f"\nTotal CARTESIAN_POINT: {len(points)}")

# Find extreme coords
ys = []
for p_id, x, y, z in points:
    try:
        ys.append((float(y.strip()), int(p_id.strip())))
    except:
        pass
ys.sort()
print(f"Y range: [{ys[0][0]:.1f}, {ys[-1][0]:.1f}]")
print(f"Min Y: #{ys[0][1]} at {ys[0][0]:.1f}")
print(f"Max Y: #{ys[-1][1]} at {ys[-1][0]:.1f}")

# Find the extreme point lines
for line_num, line in enumerate(c.split('\n'), 1):
    if f'#{ys[0][1]}' in line:
        print(f"Min Y line {line_num}: {line.strip()}")
        break
for line_num, line in enumerate(c.split('\n'), 1):
    if f'#{ys[-1][1]}' in line:
        print(f"Max Y line {line_num}: {line.strip()}")
        break
