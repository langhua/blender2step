"""
UI模式测试：验证进度条显示功能
用法:
  blender --python test_progress_ui.py -- --test-number 28 --output-dir "f:\git\blender2step\step_exporter"
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
    
    if '--' in sys.argv:
        idx = sys.argv.index('--')
        script_args = sys.argv[idx + 1:]
    else:
        script_args = sys.argv[1:]
    
    return parser.parse_args(script_args)

def create_test_scene():
    """创建两个顶壳测试场景"""
    # 清除场景
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete()
    
    script_dir = os.path.dirname(os.path.abspath(__file__))
    from step_exporter.test.create_top_shell import create_hollow_top_shell
    
    # 创建第一个顶壳
    top_shell = create_hollow_top_shell(
        name="TestTopShell",
        width=100.0,
        depth=70.0,
        outer_height=10.0,
        top_thickness=2.0,
        wall_thickness=2.0,
        corner_radius=20.0,
        location=(0, 0, 0),
        segments=24,
        holes=None
    )
    
    # 创建第二个顶壳
    top_shell2 = create_hollow_top_shell(
        name="TestTopShell2",
        width=100.0,
        depth=70.0,
        outer_height=10.0,
        top_thickness=2.0,
        wall_thickness=2.0,
        corner_radius=20.0,
        location=(120, 0, 0),
        segments=24,
        holes=None
    )
    
    print(f"[TEST] Created {len(bpy.data.objects)} objects")
    
    # 调整视角
    for area in bpy.context.screen.areas:
        if area.type == 'VIEW_3D':
            for space in area.spaces:
                if space.type == 'VIEW_3D':
                    space.region_3d.view_location = (60, 0, 0)
                    space.region_3d.view_distance = 200
                    space.region_3d.view_rotation = (0.5, 0.5, 0.5, 0.5)
                    break

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
    src_lib = os.path.join(project_addon_dir, 'lib', '_step_exporter.pyd')
    dst_lib = os.path.join(blender_addon_dir, 'lib', '_step_exporter.pyd')
    
    if os.path.exists(src_init) and os.path.exists(dst_init):
        if not os.path.samefile(src_init, dst_init):
            shutil.copy2(src_init, dst_init)
            print(f"[TEST] Copied __init__.py")
    
    if os.path.exists(src_lib) and os.path.exists(dst_lib):
        if not os.path.samefile(src_lib, dst_lib):
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

def run_export_test(output_path):
    """运行导出测试"""
    print(f"[TEST] Starting export to: {output_path}")
    print(f"[TEST] Please watch the progress bar in the status bar")
    print(f"[TEST] Expected: 10% -> 50% -> 90% -> 100%")
    
    # 调用导出操作符
    try:
        result = bpy.ops.export_scene.step_enhanced(
            filepath=output_path,
            unit='mm',
            fix_geometry=False,
            use_selected=False,
            apply_modifiers=False,
            enable_logging=True,
            create_solid=False,
            advanced_brep=False,
            create_exploded_view=False,
            step_schema='AP214DIS',
            sew_tolerance=0.001
        )
        print(f"[TEST] Export result: {result}")
    except Exception as e:
        print(f"[TEST] Export error: {e}")
        import traceback
        traceback.print_exc()

def main():
    args = parse_args()
    
    output_path = os.path.join(args.output_dir, f'test{args.test_number}.step')
    
    # 清理旧文件
    if os.path.exists(output_path):
        os.remove(output_path)
    for ext in ['.log', '.temp0.step', '.temp1.step']:
        p = output_path + ext
        if os.path.exists(p):
            os.remove(p)
    
    print("=" * 60)
    print("UI MODE PROGRESS BAR TEST")
    print("=" * 60)
    
    # 确保插件加载
    ensure_addon_loaded()
    
    # 创建测试场景
    create_test_scene()
    
    # 运行导出
    run_export_test(output_path)
    
    # 验证结果
    if os.path.exists(output_path):
        size = os.path.getsize(output_path)
        print(f"[TEST] SUCCESS: {output_path} ({size} bytes)")
    else:
        print(f"[TEST] FAIL: Output file not created")

if __name__ == "__main__":
    main()
