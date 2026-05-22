"""Debug chamfer/fillet detection v3"""
import bpy, sys, importlib, bmesh, math, os
from collections import defaultdict

sys.path.insert(0, r'f:\git\blender2step')
os.environ['STEP_EXPORTER_DEBUG'] = '1'

import step_exporter.__init__ as init_mod
importlib.reload(init_mod)

ctx = bpy.context
targets = ['Cylinder_Chamfer_45deg', 'Cylinder_Fillet_Top', 'Cylinder_Fillet_Small',
           'Cylinder_Tapered_Fillet_Chamfer', 'Cylinder_Tapered_Hollow_Chamfer',
           'Cylinder_Hollow_R25_r10_H60']

print('\n=== Debug Results ===')
for obj in ctx.scene.objects:
    if obj.name not in targets:
        continue
    if obj.type != 'MESH':
        continue
    
    result = init_mod._analyze_cylinder_from_mesh(obj, ctx, 1000)
    if result:
        print(f'{obj.name}: -> {result["obj_type"]}, top={result.get("top_feature")}, '
              f'bot={result.get("bottom_feature")}, '
              f'top_size={result.get("top_feature_size", 0):.3f}, '
              f'bot_size={result.get("bottom_feature_size", 0):.3f}')
        extra = []
        if 'radius' in result: extra.append(f'r={result["radius"]:.2f}')
        if 'outer_radius' in result: extra.append(f'outer_r={result["outer_radius"]:.2f}')
        if 'inner_radius' in result: extra.append(f'inner_r={result["inner_radius"]:.2f}')
        if 'height' in result: extra.append(f'h={result["height"]:.1f}')
        if extra: print(f'  params: {", ".join(extra)}')
    else:
        print(f'{obj.name}: -> None')

print('\nDone!')