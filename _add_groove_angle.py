import re
path = r'f:\git\blender2step\step_exporter\export\staged_export.py'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

# Add groove_angle after each cparams.get('groove_extrusion_length', 0))
pattern = r"(cparams\.get\('groove_extrusion_length', 0\)\))"
replacement = r"\1,\n            cparams.get('groove_angle', 45.0))"
content = re.sub(pattern, replacement, content)

# Also handle: cparams['groove_extrusion_length'],
pattern2 = r"(cparams\['groove_extrusion_length'\],)"
replacement2 = r"\1\n            cparams.get('groove_angle', 45.0),"
content = re.sub(pattern2, replacement2, content)

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)
print('Done')
