"""
端到端测试：检测圆柱体并参数化导出
"""
import bpy
import sys
import os
import time

script_dir = os.path.dirname(os.path.abspath(__file__))
step_exporter_dir = os.path.dirname(script_dir)
lib_dir = os.path.join(step_exporter_dir, 'lib')

os.environ['PATH'] = lib_dir + os.pathsep + os.environ.get('PATH', '')
if hasattr(os, 'add_dll_directory'):
    os.add_dll_directory(lib_dir)

# Import step_exporter functions
import step_exporter
import step_exporter.__init__ as init_mod
import importlib
importlib.reload(init_mod)

analyze_fn = init_mod._analyze_cylinder_from_mesh
log_fn = init_mod.log_to_file

# Step 1: 创建圆柱体
print("Step 1: Creating cylinders...")
create_script = os.path.join(script_dir, 'create_mesh_cylinder.py')
with open(create_script, 'r', encoding='utf-8') as f:
    code = f.read()
script_globals = {'__name__': '__main__', '__file__': create_script}
exec(compile(code, create_script, 'exec'), script_globals)
script_globals['create_mechanical_demo_scene']()

# Step 2: 分析所有物体
print("\nStep 2: Analyzing objects...")
context = bpy.context
scale = 1000.0

cylinders = []
for obj in bpy.context.scene.objects:
    if obj.type == 'MESH':
        print(f"  Analyzing: {obj.name}")
        result = analyze_fn(obj, context, scale)
        if result:
            cylinders.append(result)
            print(f"    -> {result['obj_type']}: {result}")
        else:
            print(f"    -> NOT a cylinder")

print(f"\nDetected {len(cylinders)} cylinder/cone objects")

# Step 3: 模拟导出
if cylinders:
    print("\nStep 3: Exporting cylinders parametrically...")
    output_path = os.path.join(step_exporter_dir, 'test', 'cylinders_parametric.step')
    log_path = output_path + ".log"
    
    init_mod._export_log_file = open(log_path, 'w', encoding='utf-8')
    init_mod.log_to_file(f"[STEP Exporter] Log file opened")
    init_mod.log_to_file(f"[STEP Exporter] Found {len(cylinders)} cylinder(s), using parametric export")
    
    init_mod._bottom_shell_export_data = {
        'filepath': output_path,
        'shells': [],
        'cylinders': cylinders,
        'step_schema': 'AP214IS',
        'step_unit': 'MILLIMETER',
        'enable_logging': True,
        'context': context,
    }
    
    print("Calling timer function...")
    result = init_mod._export_bottom_shell_timer()
    print(f"Timer result: {result}")
    
    init_mod._export_log_file.close()

    # Step 4: 检查结果
    print("\nStep 4: Checking output...")
    if os.path.exists(output_path):
        import re
        size = os.path.getsize(output_path)
        with open(output_path, 'r') as f:
            content = f.read()
        faces = len(re.findall(r'ADVANCED_FACE\(', content))
        solids = len(re.findall(r'MANIFOLD_SOLID_BREP', content))
        cyl = len(re.findall(r'CYLINDRICAL_SURFACE', content))
        cone = len(re.findall(r'CONICAL_SURFACE', content))
        torus = len(re.findall(r'TOROIDAL_SURFACE', content))
        plane = len(re.findall(r'PLANE', content))
        print(f"  cylinders_parametric.step: {size} bytes, {solids} solids, {faces} faces")
        print(f"  Surfaces: CYLINDRICAL={cyl}, CONICAL={cone}, TOROIDAL={torus}, PLANE={plane}")
        
        if os.path.exists(log_path):
            print(f"\n  Log file contents:")
            with open(log_path, 'r') as f:
                print(f.read())
    else:
        print("  ERROR: Output file not created!")
else:
    print("\n  No cylinders detected!")