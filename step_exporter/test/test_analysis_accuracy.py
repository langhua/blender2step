"""
完整operator导出路径测试 - 检测参数分析是否准确
"""
import bpy
import sys
import os

script_dir = os.path.dirname(os.path.abspath(__file__))
step_exporter_dir = os.path.dirname(script_dir)
lib_dir = os.path.join(step_exporter_dir, 'lib')

if step_exporter_dir not in sys.path:
    sys.path.insert(0, step_exporter_dir)
if lib_dir not in os.environ.get('PATH', ''):
    os.environ['PATH'] = lib_dir + os.pathsep + os.environ.get('PATH', '')
if hasattr(os, 'add_dll_directory') and os.path.exists(lib_dir):
    os.add_dll_directory(lib_dir)

import step_exporter

# Register
step_exporter.register()

# Clear scene
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete()

# Create bottom shell
print("=" * 60)
print("Creating bottom shell...")
print("=" * 60)

create_script = os.path.join(script_dir, 'create_bottom_shell.py')
with open(create_script, 'r', encoding='utf-8') as f:
    code = f.read()

script_globals = {'__name__': '__main__', '__file__': create_script}
exec(compile(code, create_script, 'exec'), script_globals)
script_globals['create_filleted_bottom_shells_scene']()

for o in bpy.data.objects:
    print(f"  {o.name} ({o.type}, {len(o.data.vertices)} verts)")

# ===== Test the analysis =====
print("=" * 60)
print("Running _analyze_bottom_shell_from_mesh...")
print("=" * 60)

from step_exporter import _analyze_bottom_shell_from_mesh

for obj in bpy.data.objects:
    if obj.type == 'MESH':
        result = _analyze_bottom_shell_from_mesh(obj, bpy.context, 1000.0)
        if result:
            print(f"\n  Object: {obj.name}")
            print(f"  Detected parameters:")
            print(f"    width: {result.get('width')}")
            print(f"    depth: {result.get('depth')}")
            print(f"    outer_height: {result.get('outer_height')}")
            print(f"    bottom_thickness: {result.get('bottom_thickness')}")
            print(f"    wall_thickness: {result.get('wall_thickness')}")
            print(f"    corner_radius: {result.get('corner_radius')}")
            print(f"    outer_fillet_radius: {result.get('outer_fillet_radius')}")
            print(f"    inner_fillet_radius: {result.get('inner_fillet_radius')}")
            print(f"    step_height: {result.get('step_height')}")
            print(f"    has_holes: {result.get('has_holes')}")
            print(f"    pos_x: {result.get('pos_x')}")
            print(f"    pos_y: {result.get('pos_y')}")
            print(f"    pos_z: {result.get('pos_z')}")
            
            # Expected parameters (from create_bottom_shell.py):
            print(f"\n  Expected parameters:")
            print(f"    width: 100.0")
            print(f"    depth: 70.0")
            print(f"    outer_height: 10.0")
            print(f"    bottom_thickness: 2.0")
            print(f"    wall_thickness: 2.0")
            print(f"    corner_radius: 20.0")
            print(f"    outer_fillet_radius: 3.0")
            print(f"    inner_fillet_radius: 1.5")
            print(f"    step_height: 1.0")
            print(f"    has_holes: False")
            
            # Now test C++ export with detected parameters
            print(f"\n  Testing C++ export with DETECTED parameters...")
            import _step_exporter as cpp
            temp_file = os.path.join(script_dir, 'test_detected_params.step')
            
            try:
                success = cpp.export_bottom_shell_filleted_step(
                    temp_file,
                    result['width'],
                    result['depth'],
                    result['outer_height'],
                    result['bottom_thickness'],
                    result['wall_thickness'],
                    result['corner_radius'],
                    result['outer_fillet_radius'],
                    result['inner_fillet_radius'],
                    result.get('step_height', 1.0),
                    result.get('pos_x', 0.0),
                    result.get('pos_y', 0.0),
                    result.get('pos_z', 0.0),
                    'AP214DIS', 'MILLIMETER', 1
                )
                if success:
                    size = os.path.getsize(temp_file)
                    with open(temp_file) as f:
                        solids = f.read().count('MANIFOLD_SOLID_BREP')
                    print(f"  C++ export OK: {size} bytes, {solids} solids")
                else:
                    print(f"  C++ export FAILED with detected params!")
            except Exception as e:
                print(f"  C++ export ERROR: {e}")
                import traceback
                traceback.print_exc()
        else:
            print(f"  {obj.name}: NOT detected as bottom shell")

# Now test with CORRECT parameters for comparison
print("\n" + "=" * 60)
print("Testing C++ export with CORRECT parameters...")
print("=" * 60)

import _step_exporter as cpp
temp_file2 = os.path.join(script_dir, 'test_correct_params.step')

try:
    success = cpp.export_bottom_shell_filleted_step(
        temp_file2,
        100.0, 70.0, 10.0,  # width, depth, outer_height  
        2.0, 2.0, 20.0,      # bottom_t, wall_t, corner_r
        3.0, 1.5, 1.0,       # outer_fillet, inner_fillet, step_height
        0.0, 0.0, 0.0,       # pos
        'AP214DIS', 'MILLIMETER', 1
    )
    if success:
        size = os.path.getsize(temp_file2)
        with open(temp_file2) as f:
            solids = f.read().count('MANIFOLD_SOLID_BREP')
        print(f"C++ export OK: {size} bytes, {solids} solids")
    else:
        print("C++ export FAILED with correct params!")
except Exception as e:
    print(f"C++ export ERROR: {e}")
    import traceback
    traceback.print_exc()