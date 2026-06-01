import re

with open("f:/git/blender2step/step_exporter/test28.step", "r") as f:
    content = f.read()

points = re.findall(r"CARTESIAN_POINT\s*\([^)]*\)", content)
zs = []
for p in points:
    m = re.search(r"'[^']*',\s*\(([^,]+),([^,]+),([^)]+)\)", p)
    if m:
        zs.append(float(m.group(3).strip()))

if zs:
    print(f"Total cartesian points: {len(points)}")
    print(f"Z range: [{min(zs):.4f}, {max(zs):.4f}]")
    unique_z = sorted(set(round(z, 4) for z in zs))
    print(f"Unique Z values: {unique_z}")