"""Clean up orphan code in cylinder_parametric.cpp"""
path = r'f:\git\blender2step\src\cylinder\cylinder_parametric.cpp'
with open(path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Find the first broken function declaration (line with orphan code inside params)
broken_start = -1
for i, line in enumerate(lines):
    if '// Combined: cone stepped hole + external trapezoidal groove' in line and i > 1200:
        # Check if the NEXT line has the broken params (indented orphan code)
        if i+4 < len(lines) and '// Apply inner top hole fillet' in lines[i+4]:
            broken_start = i
            break

# Find the SECOND (correct) occurrence
correct_start = -1
count = 0
for i, line in enumerate(lines):
    if '// Combined: cone stepped hole + external trapezoidal groove' in line:
        count += 1
        if count == 2:
            correct_start = i
            break

if broken_start >= 0 and correct_start > broken_start:
    print(f"Removing lines {broken_start}-{correct_start-1} ({correct_start-broken_start} lines)")
    # Keep lines 0 to broken_start-1, then lines from correct_start to end
    new_lines = lines[:broken_start] + lines[correct_start:]
    with open(path, 'w', encoding='utf-8') as f:
        f.writelines(new_lines)
    print(f"Done. Removed {correct_start-broken_start} lines of orphan code.")
else:
    print(f"Could not find orphan section. broken_start={broken_start}, correct_start={correct_start}")
