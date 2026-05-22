"""Quick Z-level check"""
import bpy, bmesh, math
from collections import defaultdict

obj = bpy.context.scene.objects.get('Cylinder_Fillet_Top')
if obj:
    bm = bmesh.new()
    depsgraph = bpy.context.evaluated_depsgraph_get()
    eval_obj = obj.evaluated_get(depsgraph)
    bm.from_mesh(eval_obj.data)
    
    z_layers = defaultdict(list)
    for v in bm.verts:
        z_key = round(v.co.z / 0.05) * 0.05
        z_layers[z_key].append(v.co.z)
    
    sorted_z = sorted(z_layers.keys())
    rich_z = [zl for zl in sorted_z if len(z_layers[zl]) >= 4]
    
    print(f'All Z levels: {len(sorted_z)}, rich: {len(rich_z)}')
    print(f'Range: [{sorted_z[0]:.4f}, {sorted_z[-1]:.4f}]')
    
    mid_start = sorted_z[0] + 0.2 * (sorted_z[-1] - sorted_z[0])
    mid_end = sorted_z[-1] - 0.2 * (sorted_z[-1] - sorted_z[0])
    mid = [zl for zl in rich_z if mid_start <= zl <= mid_end]
    print(f'Mid [{mid_start:.1f}..{mid_end:.1f}]: {len(mid)} levels')
    
    if mid:
        print(f'Mid samples: {mid[:5]} ... {mid[-3:]}')
    else:
        print(f'All rich levels: {rich_z[:5]} ... {rich_z[-5:]}')
    
    bm.free()
else:
    print('Object not found')