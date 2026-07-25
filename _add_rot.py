#!/usr/bin/env python3
"""Add rotation support to all C++ export functions in module.cpp."""
import re

CPP = r"f:\git\blender2step\src\export\module.cpp"
with open(CPP, 'r', encoding='utf-8') as f:
    lines = f.readlines()

i = 0
modified = 0
while i < len(lines):
    line = lines[i]
    
    if 'double pos_x = 0.0, pos_y = 0.0, pos_z = 0.0;' in line:
        next_line = lines[i+1] if i+1 < len(lines) else ''
        if 'rot_x = 0.0' in next_line:
            i += 1
            continue
        
        # Add rot vars
        lines.insert(i+1, '    double rot_x = 0.0, rot_y = 0.0, rot_z = 0.0;\n')
        i += 1
        
        # Find PyArg format line
        fmt_li = None
        for j in range(i, min(i+15, len(lines))):
            if 'PyArg_ParseTuple(args,' in lines[j]:
                fmt_li = j
                break
        if fmt_li is None: i += 1; continue
        
        # Add |ddd to format
        m = re.search(r'"s[^"]*"', lines[fmt_li])
        if m and '|ddd"' not in m.group():
            lines[fmt_li] = lines[fmt_li].replace(m.group(), m.group()[:-1] + '|ddd"')
        
        # Find closing )) and insert rot args
        close_li = None
        depth = 0
        for j in range(fmt_li, min(fmt_li+60, len(lines))):
            for ch in lines[j]:
                if ch == '(': depth += 1
                if ch == ')':
                    depth -= 1
                    if depth == 0: close_li = j
            if close_li is not None: break
        if close_li is None: i += 1; continue
        
        # Insert rot args before last ))
        cl = lines[close_li]
        last = cl.rfind('))')
        if last >= 0:
            lines[close_li] = cl[:last] + ', &rot_x, &rot_y, &rot_z))' + cl[last+2:]
        
        # Add rotation call after translation block
        for j in range(fmt_li, min(fmt_li+200, len(lines))):
            if 'BRepBuilderAPI_Transform(shape, trsf).Shape();' in lines[j]:
                k = j
                while k < len(lines) and '}' not in lines[k]:
                    k += 1
                if k >= len(lines): break
                
                # Determine height var
                hv = 'height'
                for h in range(j, max(0, j-100), -1):
                    if 'outer_height' in lines[h]: hv = 'outer_height'; break
                indent = lines[k][:len(lines[k]) - len(lines[k].lstrip())]
                lines.insert(k+1, f'{indent}shape = apply_rotation_after_translation(shape, pos_x, pos_y, pos_z, {hv}, rot_x, rot_y, rot_z);\n')
                break
        modified += 1
    i += 1

with open(CPP, 'w', encoding='utf-8') as f:
    f.writelines(lines)

print(f"Modified {modified} functions.")
