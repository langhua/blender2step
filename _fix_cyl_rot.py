import re

f = r"f:\git\blender2step\step_exporter\analysis\cylinder.py"
with open(f, 'r', encoding='utf-8') as fp:
    text = fp.read()

# Add rot_x, rot_y, rot_z after every pos_z in return dicts
# Pattern: 'pos_z': pos_z * S,  → add rot after
# Pattern: 'pos_z': pos_z,      → add rot after (inline, append to same line if reasonable)
# Pattern: 'pos_x': pos_x, 'pos_y': pos_y, 'pos_z': pos_z, → change inline

# Strategy: for each line with 'pos_z':, if next line doesn't already have rot, insert rot line
lines = text.split('\n')
out = []
i = 0
while i < len(lines):
    line = lines[i]
    out.append(line)
    
    if "'pos_z': pos_z * S," in line or "'pos_z': pos_z," in line:
        # Check if next line already has rot_x
        next_line = lines[i+1] if i+1 < len(lines) else ''
        if 'rot_x' not in next_line and 'rot_x' not in line:
            indent = line[:len(line) - len(line.lstrip())]
            # If it's an inline pattern like 'pos_x': pos_x, 'pos_y': pos_y, 'pos_z': pos_z,
            # then rot is not on the same line; add on next line
            if 'pos_z,' in line and 'rot_x' not in line:
                out.append(f"{indent}'rot_x': rot_x, 'rot_y': rot_y, 'rot_z': rot_z,")
    i += 1

with open(f, 'w', encoding='utf-8') as fp:
    fp.write('\n'.join(out))

print("Done")
