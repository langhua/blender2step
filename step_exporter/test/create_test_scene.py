"""
创建测试场景并导出STEP文件
包含11个物体：圆柱体、立方体、圆锥体等
"""
import bpy
import math

# 清除场景中的所有物体
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete()

# 创建11个测试物体
objects = []

# 1. 圆柱体 R25 H60 at (0, 0, 0)
bpy.ops.mesh.primitive_cylinder_add(radius=25, depth=60, location=(0, 0, 0))
bpy.context.active_object.name = "Cylinder_1_R25_H60"
objects.append(bpy.context.active_object)

# 2. 立方体 50x50x100 at (100, 0, 0)
bpy.ops.mesh.primitive_cube_add(size=1, location=(100, 0, 0))
bpy.context.active_object.scale = (50, 50, 100)
bpy.context.active_object.name = "Cube_2_50x50x100"
objects.append(bpy.context.active_object)

# 3. 圆柱体 R30 H80 at (200, 0, 0)
bpy.ops.mesh.primitive_cylinder_add(radius=30, depth=80, location=(200, 0, 0))
bpy.context.active_object.name = "Cylinder_3_R30_H80"
objects.append(bpy.context.active_object)

# 4. 圆锥体 R25 H60 at (0, 100, 0)
bpy.ops.mesh.primitive_cone_add(radius1=25, radius2=0, depth=60, location=(0, 100, 0))
bpy.context.active_object.name = "Cone_4_R25_H60"
objects.append(bpy.context.active_object)

# 5. 圆柱体 R20 H50 at (100, 100, 0)
bpy.ops.mesh.primitive_cylinder_add(radius=20, depth=50, location=(100, 100, 0))
bpy.context.active_object.name = "Cylinder_5_R20_H50"
objects.append(bpy.context.active_object)

# 6. 立方体 40x40x80 at (200, 100, 0)
bpy.ops.mesh.primitive_cube_add(size=1, location=(200, 100, 0))
bpy.context.active_object.scale = (40, 40, 80)
bpy.context.active_object.name = "Cube_6_40x40x80"
objects.append(bpy.context.active_object)

# 7. 圆柱体 R35 H70 at (0, 200, 0)
bpy.ops.mesh.primitive_cylinder_add(radius=35, depth=70, location=(0, 200, 0))
bpy.context.active_object.name = "Cylinder_7_R35_H70"
objects.append(bpy.context.active_object)

# 8. 圆环体 R15 r5 at (100, 200, 0)
bpy.ops.mesh.primitive_torus_add(major_radius=15, minor_radius=5, location=(100, 200, 0))
bpy.context.active_object.name = "Torus_8_R15_r5"
objects.append(bpy.context.active_object)

# 9. 圆柱体 R25 H60 at (200, 200, 0)
bpy.ops.mesh.primitive_cylinder_add(radius=25, depth=60, location=(200, 200, 0))
bpy.context.active_object.name = "Cylinder_9_R25_H60"
objects.append(bpy.context.active_object)

# 10. 球体 R20 at (0, 300, 0)
bpy.ops.mesh.primitive_uv_sphere_add(radius=20, location=(0, 300, 0))
bpy.context.active_object.name = "Sphere_10_R20"
objects.append(bpy.context.active_object)

# 11. 圆柱体 R40 H100 at (100, 300, 0)
bpy.ops.mesh.primitive_cylinder_add(radius=40, depth=100, location=(100, 300, 0))
bpy.context.active_object.name = "Cylinder_11_R40_H100"
objects.append(bpy.context.active_object)

print(f"Created {len(objects)} test objects")

# 保存.blend文件
blend_path = r"F:\git\blender2step\step_exporter\test\test28.blend"
bpy.ops.wm.save_as_mainfile(filepath=blend_path)
print(f"Saved blend file to: {blend_path}")

# 选择所有物体
bpy.ops.object.select_all(action='SELECT')

# 导出STEP文件
output_path = r"F:\git\blender2step\step_exporter\test28.step"
print(f"Will export to: {output_path}")

# 运行导出脚本
import sys
sys.argv = ['--', '--test-number', '28', '--output-dir', r'F:\git\blender2step\step_exporter']

# 导入并运行导出函数
exec(open(r"F:\git\blender2step\step_exporter\test\run_test.py").read())
