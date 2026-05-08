import bpy
import os

# 清除场景
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete()

# 创建简单立方体
bpy.ops.mesh.primitive_cube_add(size=2, location=(0, 0, 0))
cube = bpy.context.active_object
cube.name = "TestCube"

# 添加材质
mat = bpy.data.materials.new(name='TestMat')
mat.use_nodes = False
mat.diffuse_color = (0.8, 0.2, 0.2, 1.0)
cube.data.materials.append(mat)

# 创建相机
cam_data = bpy.data.cameras.new('Camera')
cam = bpy.data.objects.new('Camera', cam_data)
bpy.context.collection.objects.link(cam)
bpy.context.scene.camera = cam

# 顶视图相机位置 - 调整距离
cam.location = (0, 0, 15)
cam.rotation_euler = (0, 0, 0)  # Workbench相机默认朝-Z，不需要旋转

# 添加灯光 - 调整位置
light_data = bpy.data.lights.new(name='Light', type='SUN')
light_data.energy = 5
light_obj = bpy.data.objects.new(name='Light', object_data=light_data)
light_obj.location = (5, 5, 10)
bpy.context.collection.objects.link(light_obj)

# 设置渲染 - 使用Workbench引擎（后台模式更可靠）
bpy.context.scene.render.engine = 'BLENDER_WORKBENCH'
bpy.context.scene.render.resolution_x = 800
bpy.context.scene.render.resolution_y = 600

output_path = os.path.join(os.path.dirname(__file__), '..', '..', 'build', 'debug_test.png')
bpy.context.scene.render.filepath = output_path
bpy.context.scene.render.image_settings.file_format = 'PNG'

# Workbench渲染设置
bpy.context.scene.display.shading.light = 'STUDIO'
bpy.context.scene.display.shading.studio_light = 'Default'
bpy.context.scene.display.shading.color_type = 'MATERIAL'

print(f"Camera location: {cam.location}")
print(f"Camera rotation: {cam.rotation_euler}")
print(f"Scene objects: {[obj.name for obj in bpy.context.scene.objects]}")
print(f"Output path: {output_path}")

# 渲染
bpy.ops.render.render(write_still=True)

if os.path.exists(output_path):
    print(f"SUCCESS: Image saved to {output_path}")
else:
    print(f"ERROR: Image not saved")
