"""
模拟 GUI 菜单导出流程，测试底壳检测和定时器导出
"""
import bpy
import sys
import os

script_dir = os.path.dirname(os.path.abspath(__file__))
step_exporter_dir = os.path.dirname(script_dir)
lib_dir = os.path.join(step_exporter_dir, 'lib')

os.environ['PATH'] = lib_dir + os.pathsep + os.environ.get('PATH', '')
if hasattr(os, 'add_dll_directory'):
    os.add_dll_directory(lib_dir)

import importlib
import step_exporter.__init__ as init_mod
importlib.reload(init_mod)

analyze_fn = init_mod._analyze_bottom_shell_from_mesh

# Step 1: 创建底壳
print("\n=== Step 1: Creating shells ===")
create_script = os.path.join(script_dir, 'create_bottom_shell.py')
with open(create_script, 'r', encoding='utf-8') as f:
    code = f.read()
script_globals = {'__name__': '__main__', '__file__': create_script}
exec(compile(code, create_script, 'exec'), script_globals)
script_globals['create_filleted_bottom_shells_with_holes_scene']()

# Step 2: 模拟 export execute 方法中的检测流程
print("\n=== Step 2: Simulating GUI export detection ===")
context = bpy.context
scale = 1000.0

# 这和 execute 方法中的代码一样
_export_objects = [obj for obj in context.scene.objects if obj.type == 'MESH']
print(f"Scene objects (MESH): {len(_export_objects)}")
for obj in _export_objects:
    print(f"  - {obj.name}")

bottom_shells = []
for obj in _export_objects:
    print(f"\n  Checking: {obj.name}")
    shell_params = analyze_fn(obj, context, scale)
    if shell_params:
        bottom_shells.append(shell_params)
        hh = shell_params.get('has_holes', False)
        print(f"    -> Bottom shell! has_holes={hh}")
        for k, v in shell_params.items():
            print(f"       {k}={v}")
    else:
        print(f"    -> NOT a bottom shell")

print(f"\nTotal: {len(_export_objects)} objects, {len(bottom_shells)} bottom shells")

# Step 3: 模拟定时器注册和调用
if bottom_shells:
    print("\n=== Step 3: Simulating timer registration ===")
    output_path = os.path.join(step_exporter_dir, 'test28.step')
    log_path = output_path + ".log"
    
    # 打开日志文件
    init_mod._export_log_file = open(log_path, 'w', encoding='utf-8')
    init_mod.log_to_file(f"[STEP Exporter] Log file opened")
    init_mod.log_to_file(f"[STEP Exporter] Found {len(bottom_shells)} bottom shell(s), using parametric export")
    
    init_mod._bottom_shell_export_data = {
        'filepath': output_path,
        'shells': bottom_shells,
        'step_schema': 'AP214IS',
        'step_unit': 'MILLIMETER',
        'enable_logging': True,
        'context': context,
    }
    
    print("Timer data set. Calling timer function...")
    result = init_mod._export_bottom_shell_timer()
    print(f"Timer result: {result}")
    
    init_mod._export_log_file.close()

# Step 4: 检查结果
print("\n=== Step 4: Checking output ===")
if os.path.exists(output_path):
    import re
    size = os.path.getsize(output_path)
    with open(output_path, 'r') as f:
        content = f.read()
    faces = len(re.findall(r'ADVANCED_FACE\(', content))
    solids = len(re.findall(r'MANIFOLD_SOLID_BREP', content))
    cyl = len(re.findall(r'CYLINDRICAL_SURFACE', content))
    print(f"  test28.step: {size} bytes, {solids} solids, {faces} faces, {cyl} cylindrical surfaces")
    
    # 读取日志
    if os.path.exists(log_path):
        print(f"\n  Log file contents:")
        with open(log_path, 'r') as f:
            print(f.read())
else:
    print("  test28.step NOT FOUND!")
    
    # 读取日志
    if os.path.exists(log_path):
        print(f"\n  Log file contents:")
        with open(log_path, 'r') as f:
            print(f.read())

print("\nDone!")