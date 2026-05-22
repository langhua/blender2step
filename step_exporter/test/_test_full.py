"""Full test: create mesh cylinders and bottom shells, then detect and export"""
import bpy, sys, importlib, bmesh, math, os
from collections import defaultdict

sys.path.insert(0, r'f:\git\blender2step')
os.environ['STEP_EXPORTER_DEBUG'] = '1'

ctx = bpy.context

# Helper: clear scene
def clear_scene():
    for obj in list(bpy.data.objects):
        bpy.data.objects.remove(obj, do_unlink=True)

# Step 1: Create cylinders
print("\n" + "="*60)
print("[1/4] Creating cylinder test objects...")
print("="*60)
clear_scene()

# Run create_mesh_cylinder main block via subprocess to avoid __name__ conflicts
# Instead, extract and run the cylinder creation logic directly
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'test'))
import create_mesh_cylinder
# Force run the main block
create_mesh_cylinder_scene = getattr(create_mesh_cylinder, 'create_mesh_cylinder_scene', None)
if create_mesh_cylinder_scene is None:
    # The script executes at import level? Let's check
    print("  Objects in scene:", [o.name for o in ctx.scene.objects])
else:
    create_mesh_cylinder_scene()

print("  Created:", [o.name for o in ctx.scene.objects])

# Step 2: Load the module and test cylinder detection
print("\n" + "="*60)
print("[2/4] Testing cylinder detection...")
print("="*60)
import importlib.util
_spec = importlib.util.spec_from_file_location("step_exporter.__init__",
    os.path.join(os.path.dirname(os.path.dirname(__file__)), '__init__.py'))
init_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(init_mod)

targets = ['Cylinder_Chamfer_45deg', 'Cylinder_Fillet_Top', 'Cylinder_Fillet_Small',
           'Cylinder_Tapered_Fillet_Chamfer', 'Cylinder_Tapered_Hollow_Chamfer',
           'Cylinder_Hollow_R25_r10_H60']

all_cylinder_ok = True
for obj in list(ctx.scene.objects):
    if obj.name not in targets:
        continue
    if obj.type != 'MESH':
        continue
    
    result = init_mod._analyze_cylinder_from_mesh(obj, ctx, 1000)
    if result:
        print(f'  {obj.name}: -> {result["obj_type"]}, top={result.get("top_feature")}, '
              f'bot={result.get("bottom_feature")}, '
              f'top_size={result.get("top_feature_size", 0):.3f}, '
              f'bot_size={result.get("bottom_feature_size", 0):.3f}')
        extra = []
        if 'radius' in result: extra.append(f'r={result["radius"]:.2f}')
        if 'outer_radius' in result: extra.append(f'outer_r={result["outer_radius"]:.2f}')
        if 'inner_radius' in result: extra.append(f'inner_r={result["inner_radius"]:.2f}')
        if 'height' in result: extra.append(f'h={result["height"]:.1f}')
        if extra: print(f'    params: {", ".join(extra)}')
    else:
        print(f'  {obj.name}: -> None [FAIL]')
        all_cylinder_ok = False

if all_cylinder_ok:
    print("  [OK] All cylinders detected!")
else:
    print("  [FAIL] Some cylinders not detected")

# Step 3: Clean and create bottom shells
print("\n" + "="*60)
print("[3/4] Creating bottom shell test objects...")
print("="*60)

clear_scene()

# Import create_bottom_shell and call both shells scene
importlib.reload(sys.modules['create_mesh_cylinder'])
import create_bottom_shell
# The main block runs create_bottom_shell_scene() which creates a simple rounded box
# We want create_both_bottom_shells_scene() for two shells
importlib.reload(create_bottom_shell)

# Override __name__ to prevent main block from running
# Actually, let's just call the function directly
create_bottom_shell.create_both_bottom_shells_scene()

print("  Created:", [o.name for o in ctx.scene.objects])

# Step 4: Test bottom shell detection
print("\n" + "="*60)
print("[4/4] Testing bottom shell detection...")
print("="*60)

# Reload from dev file
_spec = importlib.util.spec_from_file_location("step_exporter.__init__",
    os.path.join(os.path.dirname(os.path.dirname(__file__)), '__init__.py'))
init_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(init_mod)

shell_targets = ['BottomShell_NoHoles', 'BottomShell_WithHoles']
all_shell_ok = True
for obj in ctx.scene.objects:
    if obj.name not in shell_targets:
        continue
    if obj.type != 'MESH':
        continue
    
    result = init_mod._analyze_bottom_shell_from_mesh(obj, ctx, 1000)
    if result:
        print(f'  {obj.name}: -> {result.get("obj_type", "?")}')
        for k, v in sorted(result.items()):
            if isinstance(v, (int, float)):
                print(f'    {k}: {v:.3f}')
            elif isinstance(v, bool):
                print(f'    {k}: {v}')
    else:
        print(f'  {obj.name}: -> None [FAIL]')
        all_shell_ok = False

if all_shell_ok:
    print("  [OK] All bottom shells detected!")
else:
    print("  [FAIL] Some bottom shells not detected")

print("\n" + "="*60)
print("TEST COMPLETE!")
print("="*60)