"""Quick test: detect all cylinders."""
import bpy
import sys
import os
import importlib.util

sys.path.insert(0, os.path.dirname(__file__))

# Clean
for obj in list(bpy.data.objects):
    bpy.data.objects.remove(obj, do_unlink=True)

# Run create_mesh_cylinder.py as script
create_script = os.path.join(os.path.dirname(__file__), 'create_mesh_cylinder.py')
with open(create_script) as f:
    code = f.read()

# Execute the creation script (it uses __main__ check, so we need to force it)
exec_globals = {'__name__': '__main__', '__builtins__': __builtins__}
exec(compile(code, create_script, 'exec'), exec_globals)

targets = ['Cylinder_Chamfer_45deg', 'Cylinder_Fillet_Top', 'Cylinder_Fillet_Small',
           'Cylinder_Tapered_Fillet_Chamfer', 'Cylinder_Tapered_Hollow_Chamfer',
           'Cylinder_Hollow_R25_r10_H60']

print(f"\nScene objects: {[o.name for o in bpy.context.scene.objects]}")

# Load dev version
_spec = importlib.util.spec_from_file_location("step_exporter.__init__",
    os.path.join(os.path.dirname(os.path.dirname(__file__)), '__init__.py'))
init_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(init_mod)

ctx = bpy.context
all_ok = True

for obj in ctx.scene.objects:
    if obj.type != 'MESH':
        continue
    if obj.name not in targets:
        continue
    
    result = init_mod._analyze_cylinder_from_mesh(obj, ctx, 1000)
    if result:
        print(f'\n  {obj.name}:')
        print(f'    type={result.get("obj_type")}')
        print(f'    top_feature={result.get("top_feature")}, top_size={result.get("top_feature_size", 0):.3f}')
        print(f'    bot_feature={result.get("bottom_feature")}, bot_size={result.get("bottom_feature_size", 0):.3f}')
        for k in ['radius', 'height', 'outer_radius', 'inner_radius', 'bottom_radius', 'top_radius']:
            if k in result:
                print(f'    {k}={result[k]:.2f}')
    else:
        print(f'\n  {obj.name}: -> None [FAIL]')
        all_ok = False

if all_ok:
    print("\n[OK] All cylinders detected!")
else:
    print("\n[FAIL] Some cylinders not detected")