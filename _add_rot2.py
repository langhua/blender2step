#!/usr/bin/env python3
"""Add rotation support to all C++ export functions in module.cpp."""
import re

CPP = r"f:\git\blender2step\src\export\module.cpp"
with open(CPP, 'r', encoding='utf-8') as f:
    text = f.read()

# Step 1: Add rot vars after pos vars (if not present)
text = re.sub(
    r'(double pos_x = 0\.0, pos_y = 0\.0, pos_z = 0\.0;)\n(?!\s*double rot_x = 0)',
    r'\1\n    double rot_x = 0.0, rot_y = 0.0, rot_z = 0.0;',
    text
)

# Step 2: Add |ddd to PyArg format strings
text = re.sub(
    r'(PyArg_ParseTuple\(args,\s*)("s[^"]*")(\s*,)',
    lambda m: m.group(1) + (m.group(2)[:-1] + '|ddd"') + m.group(3) if not m.group(2).endswith('|ddd"') else m.group(0),
    text
)

# Step 3: Insert rot args into PyArg_ParseTuple calls for functions with rot vars
# Strategy: find &enable_logging)) endings and insert before ))
text = re.sub(
    r'(&enable_logging\)\))',
    lambda m: '&enable_logging, &rot_x, &rot_y, &rot_z))' if '&rot_x' not in m.group(0) else m.group(0),
    text
)

# Step 4: Add rotation call after translation blocks
text = re.sub(
    r'(shape = BRepBuilderAPI_Transform\(shape, trsf\)\.Shape\(\);\s*\})',
    r'\1\n        shape = apply_rotation_after_translation(shape, pos_x, pos_y, pos_z, height, rot_x, rot_y, rot_z);',
    text
)

with open(CPP, 'w', encoding='utf-8') as f:
    f.write(text)

print("Done")
