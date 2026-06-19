"""Verify cylinder gallery: compare each row's objects against Plain reference."""
import re
from collections import defaultdict

log_path = r'f:\git\blender2step\step_exporter\test28.step.log'
with open(log_path, 'r', encoding='utf-8') as f:
    content = f.read()

patterns = [
    (r'-> cylinder! r=([\d.]+) h=([\d.]+)', 'cylinder'),
    (r'-> cylinder_chamfer! r=([\d.]+) h=([\d.]+)', 'cyl_chamfer'),
    (r'-> cylinder_fillet! r=([\d.]+) h=([\d.]+)', 'cyl_fillet'),
    (r'-> cylinder_chamfer_fillet! r=([\d.]+) h=([\d.]+)', 'cyl_chamfer_fillet'),
    (r'-> cylinder_chamfer_both! r=([\d.]+) h=([\d.]+)', 'cyl_chamfer_both'),
    (r'-> cylinder_fillet_both! r=([\d.]+) h=([\d.]+)', 'cyl_fillet_both'),
    (r'-> cylinder_blind_hole! r=([\d.]+) h=([\d.]+)', 'cyl_blind_hole'),
    (r'-> hollow_cylinder[^!]*! r=([\d.]+) h=([\d.]+)', 'hollow_cyl'),
    (r'-> hollow_cylinder_tapered! r=[\d.]+\? h=([\d.]+)', 'hollow_cyl_tapered'),
    (r'-> cone! r=([\d.]+) h=([\d.]+)', 'cone'),
]

objects = []
for m in re.finditer(r'Checking: (C\d+_\w+)', content):
    name = m.group(1)
    pos = m.end()
    snippet = content[pos:pos+5000]
    for pat, otype in patterns:
        cm = re.search(pat, snippet)
        if cm:
            if 'tapered' in otype:
                r = 400.0
                h = float(cm.group(1))
            else:
                r = float(cm.group(1))
                h = float(cm.group(2))
            objects.append((name, otype, r, h))
            break

rows = defaultdict(list)
for name, otype, r, h in objects:
    prefix = name[:2]
    rows[prefix].append((name, otype, r, h))

print(f'{"Row":>3s} {"Object":<20s} {"Type":<22s} {"r(mm)":>8s} {"h(mm)":>8s}  Match?')
print('-' * 78)
issues = []
for row_key in sorted(rows.keys()):
    row = rows[row_key]
    plain = next((x for x in row if x[0].endswith('Plain')), None)
    if not plain:
        continue
    ref_r, ref_h = plain[2], plain[3]
    for name, otype, r, h in row:
        r_ok = abs(r - ref_r) / max(ref_r, 1) < 0.02
        h_ok = abs(h - ref_h) / max(ref_h, 1) < 0.02
        r_flag = '' if r_ok else ' BAD-R'
        h_flag = '' if h_ok else ' BAD-H'
        flag = r_flag + h_flag
        if flag:
            issues.append((name, otype, r, h, ref_r, ref_h, flag))
        print(f'{row_key:>3s} {name:<20s} {otype:<22s} {r:8.1f} {h:8.1f}{flag}')

if issues:
    print(f'\n=== {len(issues)} DIMENSION MISMATCHES ===')
    for name, otype, r, h, ref_r, ref_h, flag in issues:
        print(f'  {name} ({otype}): r={r:.1f} ref={ref_r:.0f} h={h:.1f} ref={ref_h:.0f}{flag}')
else:
    print('\n=== ALL DIMENSIONS MATCH ===')
