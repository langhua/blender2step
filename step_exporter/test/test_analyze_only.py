"""
最小测试：只测试 _analyze_bottom_shell_from_mesh 的孔洞检测
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

# ===== Step 1: 创建底壳 =====
print("Step 1: Creating bottom shells...")
create_script = os.path.join(script_dir, 'create_bottom_shell.py')
with open(create_script, 'r', encoding='utf-8') as f:
    code = f.read()

script_globals = {'__name__': '__main__', '__file__': create_script}
exec(compile(code, create_script, 'exec'), script_globals)
script_globals['create_filleted_bottom_shells_with_holes_scene']()

print(f"Scene objects: {len(bpy.context.scene.objects)}")
for obj in bpy.context.scene.objects:
    print(f"  {obj.name}")

# ===== Step 2: 测试 analyze (直接从已导入的模块获取) =====
print("\nStep 2: Testing analyze...")

# step_exporter 已在 Blender 启动时加载，通过 sys.modules 获取
import step_exporter
import step_exporter.__init__ as init_mod

analyze_fn = init_mod._analyze_bottom_shell_from_mesh

# 设置日志
log_path = os.path.join(step_exporter_dir, 'test28.step.log')
log_f = open(log_path, 'w', encoding='utf-8')
init_mod._export_log_file = log_f

context = bpy.context
scale = 1000.0

detected = []
for obj in bpy.context.scene.objects:
    if obj.type == 'MESH':
        print(f"  Checking: {obj.name}")
        params = analyze_fn(obj, context, scale)
        if params:
            hh = params.get('has_holes', False)
            print(f"    -> Bottom shell! has_holes={hh}")
            if hh:
                print(f"       hole_radius={params.get('hole_radius')}")
                print(f"       hole_offset=({params.get('hole_offset_x')}, {params.get('hole_offset_y')})")
            detected.append((obj.name, hh))
        else:
            print(f"    -> NOT a bottom shell")

log_f.close()

print(f"\nResult: detected {len(detected)} bottom shell(s)")
for name, hh in detected:
    print(f"  {name}: has_holes={hh}")

if len(detected) >= 2:
    print("\nPASS: Both shells detected correctly")
else:
    print(f"\nFAIL: Expected 2 shells, found {len(detected)}")

print("\nDone!")