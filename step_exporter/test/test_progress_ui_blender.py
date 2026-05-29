"""
UI模式进度条测试 - Blender 4.2.1
用法:
  blender --python test_progress_ui_blender.py -- --test-number 28 --output-dir "f:\git\blender2step\step_exporter" --screenshot-dir "F:\git\blender2step\build"
"""
import bpy
import sys
import os
import time
import shutil

def parse_args():
    import argparse
    parser = argparse.ArgumentParser(description='Test progress bar in UI mode')
    parser.add_argument('--test-number', type=str, default='28')
    parser.add_argument('--output-dir', type=str, default=r'F:\git\blender2step\step_exporter')
    parser.add_argument('--screenshot-dir', type=str, default=r'F:\git\blender2step\build')
    
    if '--' in sys.argv:
        idx = sys.argv.index('--')
        script_args = sys.argv[idx + 1:]
    else:
        script_args = sys.argv[1:]
    
    return parser.parse_args(script_args)

def ensure_addon_loaded():
    """确保step_exporter插件已加载"""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_addon_dir = os.path.abspath(os.path.join(script_dir, '..'))
    blender_addon_dir = os.path.join(bpy.utils.user_resource('SCRIPTS', path='addons'), 'step_exporter')
    
    print(f"[TEST] Project addon dir: {project_addon_dir}")
    print(f"[TEST] Blender addon dir: {blender_addon_dir}")
    
    # 复制最新代码
    src_init = os.path.join(project_addon_dir, '__init__.py')
    dst_init = os.path.join(blender_addon_dir, '__init__.py')
    src_progress = os.path.join(project_addon_dir, 'progress_report.py')
    dst_progress = os.path.join(blender_addon_dir, 'progress_report.py')
    src_lib = os.path.join(project_addon_dir, 'lib', '_step_exporter.pyd')
    dst_lib = os.path.join(blender_addon_dir, 'lib', '_step_exporter.pyd')
    
    if os.path.exists(src_init) and os.path.exists(dst_init):
        if not os.path.samefile(src_init, dst_init):
            shutil.copy2(src_init, dst_init)
            print(f"[TEST] Copied __init__.py")
    
    if os.path.exists(src_progress) and os.path.exists(dst_progress):
        if not os.path.samefile(src_progress, dst_progress):
            shutil.copy2(src_progress, dst_progress)
            print(f"[TEST] Copied progress_report.py")
    
    if os.path.exists(src_lib):
        os.makedirs(os.path.dirname(dst_lib), exist_ok=True)
        if os.path.exists(dst_lib) and os.path.samefile(src_lib, dst_lib):
            print("[TEST] C++ extension is the same file, skipping copy")
        else:
            shutil.copy2(src_lib, dst_lib)
            print(f"[TEST] Copied _step_exporter.pyd")
    
    # 重新加载插件
    try:
        bpy.ops.preferences.addon_disable(module="step_exporter")
    except:
        pass
    
    try:
        bpy.ops.preferences.addon_enable(module="step_exporter")
        print("[TEST] step_exporter addon enabled")
    except Exception as e:
        print(f"[TEST] addon_enable warning: {e}")

def create_test_scene():
    """创建两个顶壳测试场景"""
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete()
    
    from step_exporter.test.create_top_shell import create_hollow_top_shell
    
    top_shell = create_hollow_top_shell(
        name="TestTopShell",
        width=100.0, depth=70.0, outer_height=10.0,
        top_thickness=2.0, wall_thickness=2.0, corner_radius=20.0,
        location=(0, 0, 0), segments=24, holes=None
    )
    
    top_shell2 = create_hollow_top_shell(
        name="TestTopShell2",
        width=100.0, depth=70.0, outer_height=10.0,
        top_thickness=2.0, wall_thickness=2.0, corner_radius=20.0,
        location=(120, 0, 0), segments=24, holes=None
    )
    
    print(f"[TEST] Created {len(bpy.data.objects)} objects")

def screenshot_viewport(filepath):
    """对3D视图截图"""
    for area in bpy.context.screen.areas:
        if area.type == 'VIEW_3D':
            area.spaces[0].region_3d.view_location = (60, 0, 0)
            area.spaces[0].region_3d.view_distance = 200
            area.spaces[0].region_3d.view_rotation = (0.5, 0.5, 0.5, 0.5)
            break
    bpy.ops.screen.screenshot(filepath=filepath)

def run_export_with_screenshot(output_path, screenshot_path):
    """运行导出，在导出过程中截图进度条"""
    print(f"[TEST] Starting export to: {output_path}")
    print(f"[TEST] Progress bar should show in 3D viewport top-left corner")
    print(f"[TEST] Expected: 10% -> 50% -> 90% -> 100%")
    
    # 使用timer在导出过程中截图
    import step_exporter.progress_report as progress_report
    
    original_update = progress_report.update_progress
    
    screenshot_taken = [False]
    
    def patched_update(progress, text=None, context=None):
        original_update(progress, text, context)
        # 在50%时截图，此时进度条应该可见
        if progress >= 50 and not screenshot_taken[0]:
            screenshot_taken[0] = True
            print(f"[TEST] Taking screenshot at {progress}%...")
            # 使用timer延迟截图，确保UI刷新
            def do_screenshot():
                screenshot_viewport(screenshot_path)
                print(f"[TEST] Screenshot saved to: {screenshot_path}")
                return None  # 只执行一次
            bpy.app.timers.register(do_screenshot, first_interval=0.05)
    
    progress_report.update_progress = patched_update
    
    # 调用导出操作符（UI模式下走modal路径）
    try:
        result = bpy.ops.export_scene.step_enhanced(
            filepath=output_path,
            unit='mm', fix_geometry=False, use_selected=False,
            apply_modifiers=False, enable_logging=True,
            create_solid=False, advanced_brep=False,
            create_exploded_view=False, step_schema='AP214DIS',
            sew_tolerance=0.001
        )
        print(f"[TEST] Export result: {result}")
    except Exception as e:
        print(f"[TEST] Export error: {e}")
        import traceback
        traceback.print_exc()
    
    # 恢复原始函数
    progress_report.update_progress = original_update

def main():
    args = parse_args()
    output_path = os.path.join(args.output_dir, f'test{args.test_number}.step')
    screenshot_path = os.path.join(args.screenshot_dir, f'test{args.test_number}_progress.png')
    
    # 清理旧文件
    for f in [output_path, output_path + '.log', screenshot_path]:
        if os.path.exists(f):
            os.remove(f)
    
    print("=" * 60)
    print("UI MODE PROGRESS BAR TEST")
    print("=" * 60)
    
    ensure_addon_loaded()
    create_test_scene()
    run_export_with_screenshot(output_path, screenshot_path)
    
    if os.path.exists(output_path):
        size = os.path.getsize(output_path)
        print(f"[TEST] SUCCESS: {output_path} ({size} bytes)")
    else:
        print(f"[TEST] FAIL: Output file not created")
    
    if os.path.exists(screenshot_path):
        size = os.path.getsize(screenshot_path)
        print(f"[TEST] Screenshot: {screenshot_path} ({size} bytes)")
    else:
        print(f"[TEST] WARNING: Screenshot not created")

if __name__ == "__main__":
    main()
