import re
import math

STEP_PATH = r"f:/git/blender2step/step_exporter/test30.step"
# target centers from window_data
targets = [(9.8,9.5,3.6), (-31.4,12.4,3.6), (0.6,-18.4,3.6)]

pat = re.compile(r"CARTESIAN_POINT\('',\(([^)]+)\)\);")

found = []
with open(STEP_PATH, 'r', encoding='utf-8', errors='ignore') as f:
    for i, line in enumerate(f, start=1):
        m = pat.search(line)
        if m:
            nums = [s.strip() for s in m.group(1).split(',')]
            if len(nums) < 3:
                continue
            try:
                coords = tuple(float(n) for n in nums[:3])
            except:
                continue
            for ti, t in enumerate(targets):
                dx = coords[0]-t[0]; dy = coords[1]-t[1]; dz = coords[2]-t[2]
                dist = math.sqrt(dx*dx+dy*dy+dz*dz)
                if dist < 1.0:  # within 1 mm
                    found.append((ti, dist, coords, i, line.strip()))

if not found:
    print('No CARTESIAN_POINT within 1mm of targets found.')
else:
    for ti, dist, coords, lineno, line in found:
        print(f"Target {ti} ~{dist:.4f}mm at line {lineno}: {coords}")
        print(line)

# Also search for approximate mirrored Y (negate Y)
print('\nChecking mirrored-Y matches (y -> -y):')
with open(STEP_PATH, 'r', encoding='utf-8', errors='ignore') as f:
    for i, line in enumerate(f, start=1):
        m = pat.search(line)
        if m:
            nums = [s.strip() for s in m.group(1).split(',')]
            if len(nums) < 3:
                continue
            try:
                coords = tuple(float(n) for n in nums[:3])
            except:
                continue
            for ti, t in enumerate(targets):
                mirror = (t[0], -t[1], t[2])
                dx = coords[0]-mirror[0]; dy = coords[1]-mirror[1]; dz = coords[2]-mirror[2]
                dist = math.sqrt(dx*dx+dy*dy+dz*dz)
                if dist < 1.0:
                    print(f"Mirror Target {ti} ~{dist:.4f}mm at line {i}: {coords}")
                    print(line.strip())
