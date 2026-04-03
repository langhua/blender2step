import bpy
import sys
import os

# 确保插件已加载
if "step_exporter" not in bpy.context.preferences.addons:
    # 尝试启用插件
    bpy.ops.preferences.addon_enable(module="step_exporter")
    print("Enabled step_exporter addon")

# 生成测试曲线
exec(open(os.path.join(os.path.dirname(__file__), "generate_curve_samples.py")).read())

# 选择所有曲线对象
bpy.ops.object.select_all(action='SELECT')

# 导出STEP文件
output_path = os.path.join(os.path.dirname(__file__), "test53.step")
print(f"Exporting to {output_path}")

# 调用增强导出操作
bpy.ops.export_step.enhanced_export(
    filepath=output_path,
    unit='mm',
    scale=1000.0,
    fix_geometry=True,
    create_solid=True,
    advanced_brep=True,
    enable_logging=True
)

print("Export completed")