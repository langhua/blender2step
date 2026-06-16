import sys, os
os.chdir(r'f:\git\blender2step\step_exporter\lib')
sys.path.insert(0, '.')
try:
    import _step_exporter as c
    funcs = [x for x in dir(c) if 'cone' in x.lower()]
    with open(r'f:\git\blender2step\check_export.txt', 'w') as f:
        f.write('CONE FUNCTIONS:\n')
        for name in funcs:
            f.write(f'  {name}\n')
        f.write(f'\nHas export_cone_blind_hole_step: {hasattr(c, "export_cone_blind_hole_step")}\n')
    print('Success!')
except Exception as e:
    with open(r'f:\git\blender2step\check_export.txt', 'w') as f:
        f.write(f'ERROR: {e}\n')
    print(f'Error: {e}')
