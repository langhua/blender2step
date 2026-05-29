"""
UI模式进度条测试脚本
用法: 在Blender UI中运行此脚本
  1. 打开Blender（非后台模式）
  2. 切换到Scripting工作区
  3. 打开此脚本并运行
  4. 观察状态栏中的进度条显示
"""
import bpy
import os
import sys

def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    output_dir = r'F:\git\blender2step\step_exporter'
    output_path = os.path.join(output_dir, 'test_progress_ui.step')
    
    # 清理旧文件
    for f in [output_path, output_path + '.log', output_path + '.temp0.step', output_path + '.temp1.step']:
        if os.path.exists(f):
            os.remove(f)
    
    print("=" * 60)
    print("UI MODE PROGRESS BAR TEST")
    print("=" * 60)
    print(f"Output: {output_path}")
    print("Please watch the status bar for progress updates:")
    print("  Expected: 10% -> 50% -> 90% -> 100%")
    print("=" * 60)
    
    # 调用导出操作符（在UI模式下会走modal路径）
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
        print(f"Export result: {result}")
    except Exception as e:
        print(f"Export error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
