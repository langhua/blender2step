import re
import math

STEP_PATH = r"f:/git/blender2step/step_exporter/test_diag.step"
# target centers from window_data
targets = [(9.8,9.5,3.6), (-31.4,12.4,3.6), (0.6,-18.4,3.6)]

pat = re.compile(r"(#\d+)\s*=\s*CARTESIAN_POINT\s*\('',\s*\(\s*([^)]+?)\s*\)\s*\)\s*;", re.DOTALL)

points = []
with open(STEP_PATH, 'r', encoding='utf-8', errors='ignore') as f:
    txt = f.read()
    for m in pat.finditer(txt):
        ent = m.group(1)
        nums = [s.strip() for s in m.group(2).replace('\n',' ').split(',')]
        if len(nums) < 3:
            continue
        try:
            coords = tuple(float(n) for n in nums[:3])
        except:
            continue
        points.append((ent, coords))

if not points:
    print('No CARTESIAN_POINT entries parsed.')
    raise SystemExit(0)

for ti, t in enumerate(targets):
    dists = []
    for ent, coords in points:
        dx = coords[0]-t[0]; dy = coords[1]-t[1]; dz = coords[2]-t[2]
        dist = math.sqrt(dx*dx+dy*dy+dz*dz)
        dists.append((dist, ent, coords))
    dists.sort()
    print(f"\nTarget {ti} {t}: closest 5 CARTESIAN_POINTs:")
    for dist, ent, coords in dists[:5]:
        print(f"  {ent}: {coords}  dist={dist:.4f}mm")

# Also check mirrored Y and swapped XY
for ti, t in enumerate(targets):
    variants = {
        'mirrorY': (t[0], -t[1], t[2]),
        'swapXY': (t[1], t[0], t[2]),
        'negX': (-t[0], t[1], t[2]),
        'negZ': (t[0], t[1], -t[2]),
    }
    print(f"\nTarget {ti} variants:")
    for name, vt in variants.items():
        dists = []
        for ent, coords in points:
            dx = coords[0]-vt[0]; dy = coords[1]-vt[1]; dz = coords[2]-vt[2]
            dist = math.sqrt(dx*dx+dy*dy+dz*dz)
            dists.append((dist, ent, coords))
        dists.sort()
        dist, ent, coords = dists[0]
        print(f"  {name}: closest {ent} {coords} dist={dist:.4f}mm")
