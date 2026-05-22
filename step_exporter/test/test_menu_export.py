"""
测试：底部壳检测和参数化导出逻辑 (通过已加载的 addon 模块)
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
print("=" * 60)
print("Step 1: Creating bottom shells...")
print("=" * 60)

create_script = os.path.join(script_dir, 'create_bottom_shell.py')
with open(create_script, 'r', encoding='utf-8') as f:
    code = f.read()

script_globals = {'__name__': '__main__', '__file__': create_script}
exec(compile(code, create_script, 'exec'), script_globals)
script_globals['create_filleted_bottom_shells_with_holes_scene']()

print(f"\nScene objects: {len(bpy.context.scene.objects)}")
for obj in bpy.context.scene.objects:
    print(f"  {obj.name} ({obj.type})")

# ===== Step 2: 通过 addon 模块访问 _analyze_bottom_shell_from_mesh =====
print("\n" + "=" * 60)
print("Step 2: Testing analyze via addon module...")
print("=" * 60)

# 通过 sys.modules 获取已加载的 step_exporter
import step_exporter.__init__ as init_mod
# 重新加载以获取最新代码
import importlib
importlib.reload(init_mod)

analyze_fn = init_mod._analyze_bottom_shell_from_mesh
log_to_file = init_mod.log_to_file

# 设置日志文件
log_path = os.path.join(step_exporter_dir, 'test28.step.log')
log_f = open(log_path, 'w', encoding='utf-8')
init_mod._export_log_file = log_f

context = bpy.context
scale = 1000.0

detected_shells = []
for obj in bpy.context.scene.objects:
    if obj.type == 'MESH':
        print(f"\nAnalyzing: {obj.name}")
        params = analyze_fn(obj, context, scale)
        if params:
            has_holes = params.get('has_holes', False)
            print(f"  -> Bottom shell detected! has_holes={has_holes}")
            if has_holes:
                print(f"     hole_radius={params.get('hole_radius')}")
                print(f"     hole_offset=({params.get('hole_offset_x')}, {params.get('hole_offset_y')})")
            detected_shells.append((obj.name, params))
        else:
            print(f"  -> NOT a bottom shell")

log_f.close()

print(f"\nDetected {len(detected_shells)} bottom shells in total")
for name, p in detected_shells:
    print(f"  {name}: has_holes={p.get('has_holes', False)}")

# ===== Step 3: 直接调用 C++ 参数化导出 =====
print("\n" + "=" * 60)
print("Step 3: Exporting parametrically...")
print("=" * 60)

import _step_exporter as cpp_exporter

output_path = os.path.join(step_exporter_dir, 'test28.step')

for idx, (name, params) in enumerate(detected_shells):
    has_holes = params.get('has_holes', False)
    target = output_path if idx == 0 else output_path + f".shell{idx}.step"
    
    if has_holes:
        print(f"  Exporting {name} WITH holes to {target}")
        success = cpp_exporter.export_bottom_shell_filleted_with_holes_step(
            target,
            params['width'], params['depth'], params['outer_height'],
            params['bottom_thickness'], params['wall_thickness'], params['corner_radius'],
            params['outer_fillet_radius'], params['inner_fillet_radius'],
            params.get('step_height', 1.0),
            params.get('hole_radius', 1.5),
            params.get('hole_offset_x', 13.0),
            params.get('hole_offset_y', 11.0),
            'AP214IS', 'MILLIMETER', 1
        )
    else:
        print(f"  Exporting {name} (no holes) to {target}")
        success = cpp_exporter.export_bottom_shell_filleted_step(
            target,
            params['width'], params['depth'], params['outer_height'],
            params['bottom_thickness'], params['wall_thickness'], params['corner_radius'],
            params['outer_fillet_radius'], params['inner_fillet_radius'],
            params.get('step_height', 1.0),
            'AP214IS', 'MILLIMETER', 1
        )
    
    print(f"  Result: {'OK' if success else 'FAILED'}")

# ===== Step 4: 检查结果 =====
print("\n" + "=" * 60)
print("Step 4: Checking results...")
print("=" * 60)

import re

if os.path.exists(output_path):
    size = os.path.getsize(output_path)
    print(f"test28.step: {size} bytes")
    with open(output_path, 'r') as f:
        content = f.read()
    faces = len(re.findall(r'ADVANCED_FACE\(', content))
    has_cyl = 'CYLINDRICAL_SURFACE' in content
    print(f"  Faces: {faces}")
    print(f"  Has cylindrical surfaces: {has_cyl}")
else:
    print("test28.step NOT FOUND!")

print("\nDone!")