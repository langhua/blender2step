import re, math
from collections import defaultdict

with open(r'F:\git\blender2step\step_exporter\test28.step', 'r', encoding='utf-8', errors='ignore') as f:
    content = f.read()

pattern = r"#(\d+)\s*=\s*CARTESIAN_POINT\s*\(\s*'[^']*'\s*,\s*\(\s*([^,\r\n]+)\s*,\s*([^,\r\n]+)\s*,\s*([^\)\r\n]+)\s*\)"
all_points = {}
for m in re.finditer(pattern, content):
    try:
        pid = int(m.group(1))
        x = float(m.group(2).strip())
        y = float(m.group(3).strip())
        z = float(m.group(4).strip())
        all_points[pid] = (x, y, z)
    except:
        pass

print(f'Points: {len(all_points)}')

z_layers = defaultdict(list)
for pid, (x, y, z) in all_points.items():
    z_key = round(z / 0.01) * 0.01
    z_layers[z_key].append((x, y, z))

sorted_z = sorted(z_layers.keys())
min_z = sorted_z[0]
max_z = sorted_z[-1]
print(f'Z range: {min_z:.3f} to {max_z:.3f}, layers: {len(sorted_z)}')

all_x = [x for x, y, z in all_points.values()]
all_y = [y for x, y, z in all_points.values()]
cx = (max(all_x) + min(all_x)) / 2.0
cy = (max(all_y) + min(all_y)) / 2.0
print(f'Center: ({cx:.2f}, {cy:.2f})')
print(f'BBox: X[{min(all_x):.1f}, {max(all_x):.1f}] Y[{min(all_y):.1f}, {max(all_y):.1f}]')

print(f'\nBottom region (z <= {min_z + 3.0:.1f}):')
for z in [z for z in sorted_z if z <= min_z + 3.0][:10]:
    verts = z_layers[z]
    dists = [math.sqrt((x-cx)**2 + (y-cy)**2) for x, y, _ in verts]
    dists.sort()
    n = len(dists)
    if n == 0:
        continue
    print(f'  z={z:+.3f} n={n:4d} min={min(dists):.1f} max={max(dists):.1f}')
    if n >= 4:
        print(f'    P10={dists[n//10]:.1f} P25={dists[n//4]:.1f} P50={dists[n//2]:.1f} P75={dists[n*3//4]:.1f} P90={dists[n*9//10]:.1f}')

# Angular sector analysis at z=min_z
print(f'\nAngular sector analysis at z={min_z:.3f}:')
z0_verts = z_layers[min_z]
num_sectors = 64
sector_dists = [[] for _ in range(num_sectors)]
step = 2.0 * math.pi / num_sectors
for x, y, _ in z0_verts:
    dx = x - cx
    dy = y - cy
    dist = math.sqrt(dx*dx + dy*dy)
    angle = math.atan2(dy, dx)
    if angle < 0:
        angle += 2.0 * math.pi
    idx = int(angle / step) % num_sectors
    sector_dists[idx].append(dist)

populated = sum(1 for s in sector_dists if len(s) >= 3)
print(f'  Populated sectors (>=3 verts): {populated}/{num_sectors}')

for fracs in [(0.40, 0.90), (0.35, 0.85), (0.30, 0.85), (0.30, 0.80), (0.25, 0.80)]:
    gaps = []
    for sd in sector_dists:
        if len(sd) < 3:
            continue
        sd.sort()
        ns = len(sd)
        i_idx = max(0, int(ns * fracs[0]))
        o_idx = min(ns - 1, int(ns * fracs[1]))
        if i_idx >= o_idx:
            continue
        iv = sd[i_idx]
        ov = sd[o_idx]
        if ov > iv + 0.1:
            gaps.append(ov - iv)
    if gaps:
        gaps.sort()
        tn = max(1, len(gaps) // 4)
        t = gaps[tn:-tn] if len(gaps) > tn*2 else gaps
        avg = sum(t) / len(t)
        print(f'  P{int(fracs[0]*100)}-P{int(fracs[1]*100)}: {len(gaps)} sectors, avg_gap={avg:.2f}mm (trimmed)')