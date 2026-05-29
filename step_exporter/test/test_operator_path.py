"""
测试菜单导出路径 - 直接导入addon并测试operator
"""
import bpy
import sys
import os
import time

# 初始化路径
script_dir = os.path.dirname(os.path.abspath(__file__))
step_exporter_dir = os.path.dirname(script_dir)
lib_dir = os.path.join(step_exporter_dir, 'lib')

# Ensure paths
if step_exporter_dir not in sys.path:
    sys.path.insert(0, step_exporter_dir)
if lib_dir not in os.environ.get('PATH', ''):
    os.environ['PATH'] = lib_dir + os.pathsep + os.environ.get('PATH', '')
if hasattr(os, 'add_dll_directory') and os.path.exists(lib_dir):
    os.add_dll_directory(lib_dir)

# Manually register the steps_exporter module
import step_exporter
step_exporter.register()

print("Add-on registered:", hasattr(bpy.ops.export, 'step_enhanced'))

# 清除场景
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete()

# 创建底壳场景  
print("=" * 60)
print("Creating bottom shell scene")
print("=" * 60)

create_script = os.path.join(script_dir, 'create_bottom_shell.py')
with open(create_script, 'r', encoding='utf-8') as f:
    code = f.read()

script_globals = {'__name__': '__main__', '__file__': create_script}
exec(compile(code, create_script, 'exec'), script_globals)
script_globals['create_filleted_bottom_shells_scene']()

for o in bpy.data.objects:
    print(f"  Object: {o.name} ({o.type}, {len(o.data.vertices)} verts)")

# 调用STEP导出operator
# 注意：--background模式没有window manager, modal operator返回{'RUNNING_MODAL'}会导致问题
output = os.path.join(script_dir, 'test28_op.step')
print("=" * 60)
print(f"Exporting: {output}")
print("=" * 60)

try:
    result = bpy.ops.export.step_enhanced(
        filepath=output,
        use_selected=False,
        unit='mm',
        step_schema='AP214DIS',
        enable_logging=True,
        fix_geometry=True,
        create_solid=True,
        advanced_brep=False,
        sew_tolerance=0.001,
        apply_modifiers=True
    )
    print(f"Operator result: {result}")
except Exception as e:
    print(f"Operator ERROR: {e}")
    import traceback
    traceback.print_exc()

# Check output
if os.path.exists(output):
    size = os.path.getsize(output)
    with open(output) as f:
        content = f.read()
        solids = content.count('MANIFOLD_SOLID_BREP')
    print(f"SUCCESS: {output} ({size} bytes, {solids} solids)")
else:
    print(f"FAIL: {output} not found!")

# Check log
log_path = output + '.log'
if os.path.exists(log_path):
    with open(log_path, 'r', encoding='utf-8') as f:
        log = f.read()
    print(f"\nLog ({len(log)} chars):")
    for line in log.split('\n'):
        if any(k in line.lower() for k in ['progress', 'timer', 'modal', 'error', 'fail', 'success']):
            print(f"  {line}")