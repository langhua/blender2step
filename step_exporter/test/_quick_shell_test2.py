"""Quick test v2: detect both bottom shells with debug."""
import bpy
import sys
import os
import importlib.util

sys.path.insert(0, os.path.dirname(__file__))

# Clean and create WITHOUT C++ export
for obj in list(bpy.data.objects):
    bpy.data.objects.remove(obj, do_unlink=True)

# Use create_hollow_shell_blender directly to avoid C++ export side effects
import create_bottom_shell
importlib.reload(create_bottom_shell)

create_bottom_shell.create_hollow_shell_blender(
    name="BottomShell_NoHoles",
    width=100, depth=70, outer_height=10,
    bottom_thickness=2, wall_thickness=2,
    corner_radius=20, location=(-60, 0, 0), segments=32
)

create_bottom_shell.create_hollow_shell_blender(
    name="BottomShell_WithHoles",
    width=100, depth=70, outer_height=10,
    bottom_thickness=2, wall_thickness=2,
    corner_radius=20, location=(60, 0, 0), segments=32,
    holes=(3, 25, 20)
)

print(f"\nScene objects: {[o.name for o in bpy.context.scene.objects]}")
print(f"Object count: {len(bpy.context.scene.objects)}")

# Load dev version
_spec = importlib.util.spec_from_file_location("step_exporter.__init__",
    os.path.join(os.path.dirname(os.path.dirname(__file__)), '__init__.py'))
init_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(init_mod)

ctx = bpy.context

for obj in ctx.scene.objects:
    if obj.type != 'MESH':
        continue
    if not obj.name.startswith('BottomShell'):
        continue
    
    print(f"\n>>> Analyzing {obj.name}...")
    result = init_mod._analyze_bottom_shell_from_mesh(obj, ctx, 1000)
    if result:
        print(f">>> DETECTED: {obj.name} -> type={result.get('obj_type')}, holes={result.get('has_holes')}")
        for k, v in sorted(result.items()):
            if isinstance(v, (int, float)):
                print(f"      {k}: {v:.3f}")
    else:
        print(f">>> NOT DETECTED: {obj.name}")
    
    print(f">>> Done analyzing {obj.name}")

print("\nAll objects processed. Done.")