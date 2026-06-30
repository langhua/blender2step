path = r'f:\git\blender2step\src\cylinder\cylinder_parametric.cpp'
lines = open(path, encoding='utf-8').readlines()
idx = [i for i, l in enumerate(lines) if '// Combined: cone stepped hole' in l]
print(f'Found at lines: {idx}')
if len(idx) >= 2:
    new_lines = lines[:idx[0]] + lines[idx[1]:]
    open(path, 'w', encoding='utf-8').writelines(new_lines)
    print(f'Removed {idx[1]-idx[0]} lines')
else:
    print('No duplicates found')
