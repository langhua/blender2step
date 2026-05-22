"""End-to-end test: detect and export all cylinders and bottom shells."""
import bpy
import sys
import os
import importlib.util

script_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, script_dir)

# ==== Step 0: Setup ====
lib_dir = os.path.abspath(os.path.join(script_dir, '..', 'lib'))
sys.path.insert(0, lib_dir)
os.environ['PATH'] = lib_dir + os.pathsep + os.environ.get('PATH', '')
if hasattr(os, 'add_dll_directory'):
    os.add_dll_directory(lib_dir)

# ==== Step 1: Create cylinders ====
print("\n" + "="*60)
print("[1/3] Creating cylinder test objects...")
print("="*60)

for obj in list(bpy.data.objects):
    bpy.data.objects.remove(obj, do_unlink=True)

create_cyl = os.path.join(script_dir, 'create_mesh_cylinder.py')
with open(create_cyl) as f:
    code = f.read()
exec(compile(code, create_cyl, 'exec'), {'__name__': '__main__', '__builtins__': __builtins__})

print(f"Cylinders: {[o.name for o in bpy.context.scene.objects]}")

# ==== Step 2: Create bottom shells ====
print("\n" + "="*60)
print("[2/3] Creating bottom shell test objects...")
print("="*60)

import create_bottom_shell
bm_before = set(o.name for o in bpy.context.scene.objects)

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

all_objs = [o.name for o in bpy.context.scene.objects]
print(f"All objects: {all_objs}")

# ==== Step 3: Detect and export ====
print("\n" + "="*60)
print("[3/3] Detecting and exporting...")
print("="*60)

# Load dev version
_spec = importlib.util.spec_from_file_location("step_exporter.__init__",
    os.path.join(os.path.dirname(script_dir), '__init__.py'))
init_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(init_mod)

ctx = bpy.context
scale = 1000.0

cyl_targets = ['Cylinder_Chamfer_45deg', 'Cylinder_Fillet_Top', 'Cylinder_Fillet_Small',
               'Cylinder_Tapered_Fillet_Chamfer', 'Cylinder_Tapered_Hollow_Chamfer',
               'Cylinder_Tapered_Hollow', 'Cylinder_Hollow_R25_r10_H60']
shell_targets = ['BottomShell_NoHoles', 'BottomShell_WithHoles']

# Import C++ extension
import _step_exporter as cpp

output_dir = os.path.join(script_dir, 'e2e_output')
os.makedirs(output_dir, exist_ok=True)

cyl_results = []
shell_results = []

for obj in ctx.scene.objects:
    if obj.type != 'MESH':
        continue
    
    if obj.name in cyl_targets:
        result = init_mod._analyze_cylinder_from_mesh(obj, ctx, scale)
        if result:
            cyl_results.append((obj, result))
            print(f"\n{obj.name}: type={result['obj_type']}")
            for k, v in sorted(result.items()):
                if isinstance(v, (int, float)):
                    print(f"  {k}: {v:.3f}")
                elif isinstance(v, str):
                    print(f"  {k}: {v}")
        else:
            print(f"\n{obj.name}: DETECTION FAILED")
    
    elif obj.name in shell_targets:
        result = init_mod._analyze_bottom_shell_from_mesh(obj, ctx, scale)
        if result:
            shell_results.append((obj, result))
            print(f"\n{obj.name}: shell, has_holes={result.get('has_holes', False)}")
            for k, v in sorted(result.items()):
                if isinstance(v, (int, float)):
                    print(f"  {k}: {v:.3f}")
                elif isinstance(v, bool):
                    print(f"  {k}: {v}")
        else:
            print(f"\n{obj.name}: DETECTION FAILED")

# ==== Export ====
print("\n" + "="*60)
print("Exporting...")
print("="*60)

# Export cylinders
for obj, params in cyl_results:
    p = params
    px, py, pz = p.get('pos_x', 0), p.get('pos_y', 0), p.get('pos_z', 0)
    obj_type = p['obj_type']
    
    out_path = os.path.join(output_dir, f'{obj.name}.step')
    
    try:
        if obj_type == 'cylinder_chamfer':
            ok = cpp.export_cylinder_chamfer_step(out_path, p['radius'], p['height'],
                p.get('top_feature_size', 0), px, py, pz, "AP214IS", "MILLIMETER", 1)
        elif obj_type == 'cylinder_fillet':
            ok = cpp.export_cylinder_fillet_step(out_path, p['radius'], p['height'],
                p.get('top_feature_size', 0), px, py, pz, "AP214IS", "MILLIMETER", 1)
        elif obj_type == 'cone_chamfer_fillet':
            ok = cpp.export_cone_chamfer_fillet_step(out_path,
                p.get('bottom_radius', 0), p.get('top_radius', 0), p['height'],
                p.get('bottom_feature_size', 0), p.get('top_feature_size', 0),
                px, py, pz, "AP214IS", "MILLIMETER", 1)
        elif obj_type == 'hollow_cylinder':
            ok = cpp.export_hollow_cylinder_step(out_path,
                p['outer_radius'], p['inner_radius'], p['height'],
                px, py, pz, "AP214IS", "MILLIMETER", 1)
        elif obj_type == 'hollow_cone_fillet':
            ok = cpp.export_hollow_cone_fillet_step(out_path,
                p.get('outer_bottom_radius', 0), p.get('outer_top_radius', 0),
                p.get('inner_bottom_radius', 0), p.get('inner_top_radius', 0),
                p['height'], p.get('top_feature_size', 0),
                px, py, pz, "AP214IS", "MILLIMETER", 1)
        else:
            print(f"  {obj.name}: UNKNOWN TYPE {obj_type}")
            ok = False
        
        if ok:
            sz = os.path.getsize(out_path)
            print(f"  {obj.name}: OK ({sz} bytes)")
        else:
            print(f"  {obj.name}: EXPORT FAILED")
    except Exception as e:
        print(f"  {obj.name}: ERROR: {e}")

# Export shells
for obj, params in shell_results:
    p = params
    px, py, pz = p.get('pos_x', 0), p.get('pos_y', 0), p.get('pos_z', 0)
    has_holes = p.get('has_holes', False)
    
    out_path = os.path.join(output_dir, f'{obj.name}.step')
    
    try:
        if has_holes:
            ok = cpp.export_bottom_shell_filleted_with_holes_step(
                out_path,
                p['width'], p['depth'], p['outer_height'],
                p['bottom_thickness'], p['wall_thickness'],
                p['corner_radius'], p.get('outer_fillet_radius', 0),
                params.get('inner_fillet_radius', 0), params.get('step_height', 1.0),
                params.get('hole_radius', 1.5), params.get('hole_offset_x', 25), params.get('hole_offset_y', 20),
                px, py, pz, "AP214IS", "MILLIMETER", 1)
        else:
            ok = cpp.export_rounded_box_step(
                out_path,
                p['width'], p['depth'], p['outer_height'],
                p['bottom_thickness'], p['wall_thickness'],
                p['corner_radius'],
                "AP214IS", "MILLIMETER", 1)
        
        if ok:
            sz = os.path.getsize(out_path)
            print(f"  {obj.name}: OK ({sz} bytes)")
        else:
            print(f"  {obj.name}: EXPORT FAILED")
    except Exception as e:
        import traceback
        print(f"  {obj.name}: ERROR: {e}")
        traceback.print_exc()

print(f"\nExported files in: {output_dir}")
for f in sorted(os.listdir(output_dir)):
    if f.endswith('.step'):
        sz = os.path.getsize(os.path.join(output_dir, f))
        print(f"  {f}: {sz} bytes")

print("\nDone.")