"""
端到端测试：通过菜单导出两个底壳到同一个 STEP 文件
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

# Step 1: 创建底壳
print("Step 1: Creating shells...")
create_script = os.path.join(script_dir, 'create_bottom_shell.py')
with open(create_script, 'r', encoding='utf-8') as f:
    code = f.read()
script_globals = {'__name__': '__main__', '__file__': create_script}
exec(compile(code, create_script, 'exec'), script_globals)
script_globals['create_filleted_bottom_shells_with_holes_scene']()

# Step 2: 全选并导出
print("\nStep 2: Exporting via operator...")
output_path = os.path.join(step_exporter_dir, 'test28.step')

bpy.ops.object.select_all(action='SELECT')

result = bpy.ops.export_scene.step_enhanced(
    filepath=output_path,
    unit='mm',
    fix_geometry=True,
    create_solid=True,
    advanced_brep=True,
    step_schema='AP214IS',
    enable_logging=True,
    use_selected=True,
)
print(f"  Export result: {result}")

# Step 3: 等待计时器完成
print("\nStep 3: Waiting for timer...")
for i in range(6):
    time.sleep(0.5)
    if os.path.exists(output_path):
        break

# Step 4: 检查结果
print("\nStep 4: Checking output...")
if os.path.exists(output_path):
    import re
    size = os.path.getsize(output_path)
    with open(output_path, 'r') as f:
        content = f.read()
    faces = len(re.findall(r'ADVANCED_FACE\(', content))
    has_cyl = 'CYLINDRICAL_SURFACE' in content
    print(f"  test28.step: {size} bytes, {faces} faces, cylindrical_surfaces={has_cyl}")
    
    # 也检查 .log
    log_path = output_path + '.log'
    if os.path.exists(log_path):
        with open(log_path, 'r', encoding='utf-8') as f:
            log = f.read()
        print(f"\n  Log highlights:")
        for line in log.split('\n'):
            if 'bottom shell' in line.lower() or 'has_holes' in line.lower() or 'with_holes' in line.lower() or 'Exporting shell' in line.lower():
                print(f"    {line.strip()}")
else:
    print("  test28.step NOT FOUND!")

print("\nDone!")