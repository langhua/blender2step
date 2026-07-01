import re
path = r'f:\git\blender2step\step_exporter\export\staged_export.py'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

# Remove all lines containing groove_angle
lines = content.split('\n')
new_lines = []
for line in lines:
    if "groove_angle" not in line:
        new_lines.append(line)

with open(path, 'w', encoding='utf-8') as f:
    f.write('\n'.join(new_lines))
print('Done')
