import re

with open("f:/git/blender2step/step_exporter/test28.step", "r") as f:
    content = f.read()

# Extract all CARTESIAN_POINT entries
points = re.findall(r"#(\d+)\s*=\s*CARTESIAN_POINT\s*\('.*?',\s*\(([^)]+)\)", content)
zs = []
for pid, coords in points:
    parts = coords.split(",")
    if len(parts) >= 3:
        z = float(parts[2].strip())
        zs.append((pid, float(parts[0].strip()), float(parts[1].strip()), z))

zvals = [v[3] for v in zs]
zmin = min(zvals) if zvals else 0
zmax = max(zvals) if zvals else 0
print(f"Total points: {len(zs)}")
print(f"Z range: [{zmin}, {zmax}]")

# Check points at extremes
z_bottom = [v for v in zs if abs(v[3] - zmin) < 0.01]
z_top = [v for v in zs if abs(v[3] - zmax) < 0.01]
print(f"Points at z={zmin:.4f}: {len(z_bottom)}")
for p in z_bottom[:5]:
    print(f"  #{p[0]}: ({p[1]}, {p[2]}, {p[3]})")
print(f"Points at z={zmax:.4f}: {len(z_top)}")
for p in z_top[:5]:
    print(f"  #{p[0]}: ({p[1]}, {p[2]}, {p[3]})")

# Check for step ring (z should be near 16 if step ring is present)
z_ring = [v for v in zs if 15.5 < v[3] < 16.5]
print(f"\nPoints near z=16 (step ring): {len(z_ring)}")
for p in z_ring[:5]:
    print(f"  #{p[0]}: ({p[1]}, {p[2]}, {p[3]})")

# All unique Z values
unique_z = sorted(set(round(v[3], 4) for v in zs))
print(f"\nUnique Z values: {unique_z}")