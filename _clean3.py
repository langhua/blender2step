"""Remove only the orphan code between create_cone_stepped_hole_parametric and the next function."""
path = r'f:\git\blender2step\src\cylinder\cylinder_parametric.cpp'
lines = open(path, encoding='utf-8').readlines()
# Find the new function end: last } before "单端盲孔圆柱体"
next_func = None
for i,line in enumerate(lines):
    if '// ====================== 单端盲孔圆柱体' in line:
        next_func = i
        break
# The new function's closing } is at next_func-1...
# Find the FIRST } after the catch block that's part of our new code  
# Our new function has: } catch (...) { ... } } (outer })
# The orphan starts after that outer }
for i in range(next_func-1, 0, -1):
    stripped = lines[i].strip()
    if stripped == '}':
        # Check if the line above is a catch or similar
        prev = lines[i-1].strip() if i>0 else ''
        if 'catch' in prev or 'return' in prev or '}' in prev or 'result' in prev:
            continue
        # This might be the orphan's first }
        pass
    
# Simpler: find the first line after our replacement that's indented orphan code
orphan_start = None
for i, line in enumerate(lines):
    if 'BRepPrimAPI_MakeCone cone_cut_maker(cone_axis, inner_bottom_radius, cutter_top_r, cone_h);' in line:
        orphan_start = i
        break

if orphan_start and next_func:
    orphan_count = next_func - orphan_start
    print(f"Orphan starts at {orphan_start}, next_func at {next_func}, removing {orphan_count} lines")
    new_lines = lines[:orphan_start] + lines[next_func:]
    open(path,'w',encoding='utf-8').writelines(new_lines)
    print(f"Done. {len(new_lines)} lines")
else:
    print(f"orphan_start={orphan_start}, next_func={next_func}")
