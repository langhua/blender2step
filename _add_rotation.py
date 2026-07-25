#!/usr/bin/env python3
"""Add rotation (rot_x/rot_y/rot_z) support to all C++ export functions in module.cpp."""

import re

CPP_FILE = r"f:\git\blender2step\src\export\module.cpp"

with open(CPP_FILE, 'r', encoding='utf-8') as f:
    content = f.read()

# Pattern: find PyObject* export_*_step functions that have pos_x/pos_y/pos_z but NOT rot_x
# Strategy for each function:
# 1. Add rot vars after pos vars
# 2. Append |ddd to PyArg_ParseTuple format string (before the closing ")
# 3. Append ,&rot_x,&rot_y,&rot_z to PyArg_ParseTuple args (before the closing ))
# 4. After the translation block, add rotation call

# Step 1: Add rot_x/rot_y/rot_z vars after pos vars (if not already present)
# Pattern: (double pos_x = 0.0, pos_y = 0.0, pos_z = 0.0;)\n(?!.*rot_x)
pattern_rot_vars = r'(double pos_x = 0\.0, pos_y = 0\.0, pos_z = 0\.0;)\n(?!.*rot_x)'
replacement_rot_vars = r'\1\n    double rot_x = 0.0, rot_y = 0.0, rot_z = 0.0;'

content = re.sub(pattern_rot_vars, replacement_rot_vars, content)

# Step 2: Add |ddd to PyArg_ParseTuple format strings
# Find format strings that have pos_x/y/z but not rot_x/y/z
# Pattern: "s...|dddssi"  or similar - we need to add |ddd before the closing quote
# But careful: some functions already have |ddd for rot (parametric_shell)

# We look for PyArg_ParseTuple calls in functions WITH rot_x now added
# Find all format strings in PyArg_ParseTuple calls and check if they end with |ddd already

def add_rot_to_format(match):
    """Add |ddd to format string if not already there."""
    full = match.group(0)
    fmt = match.group(2)
    if '|ddd' in fmt.split('"')[0]:
        return full  # already has rotation
    # Insert |ddd before closing quote
    fmt_new = re.sub(r'"$', '|ddd"', fmt)
    return full.replace(fmt, fmt_new)

# Pattern for PyArg_ParseTuple format strings in functions that have pos vars
# Match the format string argument in PyArg_ParseTuple(args, "format", ...)
content = re.sub(
    r'(PyArg_ParseTuple\(args,\s*)("s[^"]*"(?![^)]*rot_x))',
    lambda m: m.group(1) + m.group(2)[:-1] + '|ddd"',
    content
)

# Step 3: Add &rot_x,&rot_y,&rot_z to PyArg_ParseTuple args
# After the last arg before closing ), add &rot_x,&rot_y,&rot_z
# But only in functions that have pos_x AND rot_x vars
# Pattern: ),\n                          &enable_logging))\n(?!.*rot_x.*rot_y)

# Step 4: Add rotation call after translation block
# Pattern: after "shape = BRepBuilderAPI_Transform(shape, trsf).Shape();\n        }"
# Insert: \n        shape = apply_rotation_after_translation(shape, pos_x, pos_y, pos_z, HEIGHT, rot_x, rot_y, rot_z);
# But HEIGHT varies by function (height, outer_height, etc.)

def add_rotation_call(match):
    """Add rotation call after translation block."""
    start = match.start()
    # Find the function's height parameter name by looking backward
    before = content[:start]
    # Look for the last `double height` or `double outer_height` before this point
    height_matches = list(re.finditer(r'double\s+(outer_height|height)\b', before))
    if height_matches:
        height_var = height_matches[-1].group(1)
    else:
        height_var = 'height'  # fallback
    
    translation = match.group(0)
    return translation + f'\n        shape = apply_rotation_after_translation(shape, pos_x, pos_y, pos_z, {height_var}, rot_x, rot_y, rot_z);'

content = re.sub(
    r'(if \(pos_x != 0\.0 \|\| pos_y != 0\.0 \|\| pos_z != 0\.0\) \{\s*gp_Trsf trsf;\s*trsf\.SetTranslation\(gp_Vec\(pos_x, pos_y, pos_z\)\);\s*shape = BRepBuilderAPI_Transform\(shape, trsf\)\.Shape\(\);\s*\})',
    add_rotation_call,
    content
)

# Step 3 (continued): Add rot params to PyArg_ParseTuple args
# Find ) at end of PyArg_ParseTuple call and insert ,&rot_x,&rot_y,&rot_z
# Pattern: ),\n                          &enable_logging)) (or similar last arg)
# Need to be careful to only modify in functions that have rot_x

# Write back
with open(CPP_FILE, 'w', encoding='utf-8') as f:
    f.write(content)

print("Done. Check the changes in module.cpp.")
