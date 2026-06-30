"""Targeted fix: replace lines 733 and 1118 in sample_ops.py"""
path = r"F:\git\blender2step\step_exporter\ui\sample_ops.py"
with open(path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

old = "                    if abs(lbl.location.y - obj.location.y) < 0.01 and abs(lbl.location.z - obj.location.z) < 0.01:\n"
new = "                    if abs(lbl.location.y - obj.location.y) < 0.01 and abs(lbl.location.z - (obj.location.z + m.H * 0.1)) < 0.01:\n"

fixed = 0
for i, line in enumerate(lines):
    if line == old:
        lines[i] = new
        fixed += 1
        print(f"Fixed line {i+1}")

with open(path, 'w', encoding='utf-8') as f:
    f.writelines(lines)

print(f"Done: {fixed} lines fixed")
