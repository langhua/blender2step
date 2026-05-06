"""
测试 Cylinder_Tapered_Hollow_Chamfer 的 STEP 导出
"""
import bpy
import sys
import os

sys.path.insert(0, r"F:\git\blender2step\step_exporter")

bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)

exec(open(r"F:\git\blender2step\step_exporter\test\create_mesh_cylinder.py").read())

output_path = r"F:\git\blender2step\step_exporter\test_fillet_export.step"

bpy.ops.object.select_all(action='DESELECT')

target = bpy.data.objects.get("Cylinder_Tapered_Hollow_Chamfer")
if target:
    target.select_set(True)
    bpy.context.view_layer.objects.active = target
    print(f"Found target object: {target.name}")

    if "step_top_fillet_radius" in target:
        print(f"  step_top_fillet_radius = {target['step_top_fillet_radius']}")

bpy.ops.object.select_all(action='SELECT')

from step_exporter import step_exporter
import json

params = {
    'filepath': output_path,
    'context': bpy.context,
    'unit': 'mm',
    'scale': 1.0,
    'fix_geometry': True,
    'create_solid': True,
    'advanced_brep': True,
    'step_schema': 'AP214IS',
    'enable_logging': True,
    'sew_tolerance': 0.001,
    'apply_modifiers': True,
}

objects = [obj for obj in bpy.context.scene.objects if obj.type == 'MESH' and obj.name == 'Cylinder_Tapered_Hollow_Chamfer']
print(f"Objects to export: {[o.name for o in objects]}")

scene_data = []
scale = 1000.0
for obj in objects:
    from step_exporter import _get_mesh_data_enhanced
    data = _get_mesh_data_enhanced(obj, bpy.context, scale, True)
    if data:
        scene_data.append(data)
        print(f"  Data keys: {list(data.keys())}")
        if 'top_fillet_radius' in data:
            print(f"  top_fillet_radius in data: {data['top_fillet_radius']}")

print(f"Scene data: {len(scene_data)} objects")

success = step_exporter.init_incremental_export(
    output_path,
    len(scene_data),
    1.0,
    1, 1, 1,
    'AP214IS', 'MILLIMETER',
    1, 0.001,
    lambda msg: print(f"[C++] {msg}")
)

if success:
    for data in scene_data:
        ok = step_exporter.add_object_to_export(data, None)
        print(f"  add_object_to_export: {ok}")
    step_exporter.finalize_incremental_export()
    print(f"Exported to: {output_path}")
else:
    print("Failed to initialize export")
