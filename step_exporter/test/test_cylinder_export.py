"""
测试圆柱体导出 - 验证兼容性
"""
import bpy
import sys
import os
import time

test_dir = os.path.dirname(os.path.abspath(__file__))
addon_dir = os.path.dirname(test_dir)

sys.path.insert(0, addon_dir)
from step_exporter import register
register()

bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)

sys.path.insert(0, test_dir)
exec(open(os.path.join(test_dir, 'create_mesh_cylinder.py'), encoding='utf-8').read())

output = os.path.join(test_dir, 'test_cylinder.step')

print("\n" + "="*60)
print("Testing cylinder export...")
print("="*60)

try:
    bpy.ops.export_scene.step_enhanced(
        filepath=output,
        unit='mm',
        use_selected=False,
        apply_modifiers=True,
        create_solid=True,
        advanced_brep=True,
        step_schema='AP214IS',
        sew_tolerance=0.001,
        enable_logging=True,
        fix_geometry=True
    )
    print(f"\n[OK] Export operator called")
except Exception as e:
    print(f"\n[FAIL] Export error: {e}")
    import traceback
    traceback.print_exc()

print("[INFO] Waiting for export to complete...")
max_wait = 30
for i in range(max_wait):
    time.sleep(1)
    if os.path.exists(output):
        size = os.path.getsize(output)
        print(f"[OK] Cylinder STEP: {size} bytes")
        break
    bpy.ops.wm.redraw_timer(type='DRAW_WIN_SWAP', iterations=1)

if not os.path.exists(output):
    print(f"[FAIL] Cylinder STEP not found after {max_wait}s")