"""Clean orphan code after create_cone_stepped_hole_parametric."""
path = r'f:\git\blender2step\src\cylinder\cylinder_parametric.cpp'
lines = open(path, encoding='utf-8').readlines()

# Find the two landmarks
func_end_brace = None  # last } of our function
next_func_start = None
for i, line in enumerate(lines):
    if '// ====================== 单端盲孔圆柱体' in line:
        next_func_start = i
        break

# The first line after the real function end is orphan code. It starts at the first }
# after "return result;" that's part of the function.
# Find the "return result;" that's indented (inside the function)
for i, line in enumerate(lines):
    if line.strip() == 'return result;':
        # Find next }
        for j in range(i+1, len(lines)):
            if lines[j].strip() == '}':
                func_end_brace = j
                break
        break

if func_end_brace is not None and next_func_start is not None:
    orphan_count = next_func_start - func_end_brace - 1
    if orphan_count > 0:
        new_lines = lines[:func_end_brace+1] + lines[next_func_start:]
        open(path, 'w', encoding='utf-8').writelines(new_lines)
        print(f"Removed {orphan_count} orphan lines. New: {len(new_lines)} lines")
    else:
        print("No orphan code found")
else:
    print(f"func_end={func_end_brace}, next_func={next_func_start}")
    # Show context
    for i in range(max(0,next_func_start-3), min(len(lines),next_func_start+3)):
        print(f"  {i}: {lines[i].rstrip()}")
