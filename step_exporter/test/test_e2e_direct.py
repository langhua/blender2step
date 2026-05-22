"""
端到端测试：直接调用 _export_bottom_shell_timer 模拟导出
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

analyze_fn = init_mod._analyze_bottom_shell_from_mesh
log_fn = init_mod.log_to_file

# Step 1: 创建底壳
print("Step 1: Creating shells...")
create_script = os.path.join(script_dir, 'create_bottom_shell.py')
with open(create_script, 'r', encoding='utf-8') as f:
    code = f.read()
script_globals = {'__name__': '__main__', '__file__': create_script}
exec(compile(code, create_script, 'exec'), script_globals)
script_globals['create_filleted_bottom_shells_with_holes_scene']()

# Step 2: 设置日志文件
log_path = os.path.join(step_exporter_dir, 'test28.step.log')
log_f = open(log_path, 'w', encoding='utf-8')
init_mod._export_log_file = log_f

output_path = os.path.join(step_exporter_dir, 'test28.step')
context = bpy.context
scale = 1000.0

# Step 3: 检测底壳
print("\nStep 3: Detecting bottom shells...")
bottom_shells = []
for obj in bpy.context.scene.objects:
    if obj.type == 'MESH':
        params = analyze_fn(obj, context, scale)
        if params:
            hh = params.get('has_holes', False)
            print(f"  {obj.name}: has_holes={hh}")
            bottom_shells.append(params)

print(f"\n  Total: {len(bottom_shells)} bottom shell(s)")

# Step 4: 设置全局数据并调用导出定时器
if bottom_shells:
    print("\nStep 4: Setting up export data and calling timer...")
    init_mod._bottom_shell_export_data = {
        'filepath': output_path,
        'shells': bottom_shells,
        'step_schema': 'AP214IS',
        'step_unit': 'MILLIMETER',
        'enable_logging': True,
        'context': context,
    }
    
    # 直接调用定时器函数
    result = init_mod._export_bottom_shell_timer()
    print(f"  Timer result: {result}")
    log_f.close()

# Step 5: 检查结果
print("\nStep 5: Checking output...")
if os.path.exists(output_path):
    import re
    size = os.path.getsize(output_path)
    with open(output_path, 'r') as f:
        content = f.read()
    faces = len(re.findall(r'ADVANCED_FACE\(', content))
    solids = len(re.findall(r'MANIFOLD_SOLID_BREP', content))
    holes = len(re.findall(r'CYLINDRICAL_SURFACE', content))
    print(f"  test28.step: {size} bytes, {solids} solids, {faces} faces, {holes} cylindrical surfaces")
else:
    print("  test28.step NOT FOUND!")

print("\nDone!")