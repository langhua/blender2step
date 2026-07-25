import re

f = r"f:\git\blender2step\step_exporter\analysis\cylinder.py"
with open(f, 'r', encoding='utf-8') as fp:
    text = fp.read()

lines = text.split('\n')
out = []
i = 0
while i < len(lines):
    line = lines[i]
    out.append(line)
    
    # Check if this is a pos_z line in a return dict
    is_pos_z = ("'pos_z': pos_z" in line)
    if is_pos_z:
        next_line = lines[i+1] if i+1 < len(lines) else ''
        if 'rot_x' not in next_line:
            indent = line[:len(line) - len(line.lstrip())]
            out.append(f"{indent}'rot_x': rot_x, 'rot_y': rot_y, 'rot_z': rot_z,")
    i += 1

with open(f, 'w', encoding='utf-8') as fp:
    fp.write('\n'.join(out))

print("Done")
