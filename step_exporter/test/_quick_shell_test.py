"""Quick test: detect both bottom shells."""
import bpy
import sys
import os
import importlib.util

sys.path.insert(0, os.path.dirname(__file__))
import create_bottom_shell

# Clean and create
for obj in list(bpy.data.objects):
    bpy.data.objects.remove(obj, do_unlink=True)

create_bottom_shell.create_both_bottom_shells_scene()

# Load dev version of __init__.py
_spec = importlib.util.spec_from_file_location("step_exporter.__init__",
    os.path.join(os.path.dirname(os.path.dirname(__file__)), '__init__.py'))
init_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(init_mod)

ctx = bpy.context

print(f"Scene objects: {[o.name for o in ctx.scene.objects]}")

for obj in ctx.scene.objects:
    if obj.type != 'MESH':
        continue
    if not obj.name.startswith('BottomShell'):
        continue
    
    print(f"\n--- {obj.name} ---")
    result = init_mod._analyze_bottom_shell_from_mesh(obj, ctx, 1000)
    if result:
        print(f"  DETECTED: type={result.get('obj_type')}, has_holes={result.get('has_holes')}")
        for k, v in sorted(result.items()):
            if isinstance(v, (int, float)):
                print(f"    {k}: {v:.3f}")
    else:
        print(f"  NOT DETECTED")

print("\nDone.")