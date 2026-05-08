import bpy
import os
import bmesh
import math

# 清除场景
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete()

# 创建圆角立方体函数
def create_rounded_box(name, width, depth, height, corner_radius, segments=8):
    hw = width / 2.0
    hd = depth / 2.0
    hh = height / 2.0

    me = bpy.data.meshes.new(name=name)
    bm = bmesh.new()

    verts = [
        bm.verts.new(( hw,  hd, -hh)),
        bm.verts.new((-hw,  hd, -hh)),
        bm.verts.new((-hw, -hd, -hh)),
        bm.verts.new(( hw, -hd, -hh)),
        bm.verts.new(( hw,  hd,  hh)),
        bm.verts.new((-hw,  hd,  hh)),
        bm.verts.new((-hw, -hd,  hh)),
        bm.verts.new(( hw, -hd,  hh)),
    ]

    faces = [
        [verts[0], verts[1], verts[2], verts[3]],
        [verts[4], verts[5], verts[6], verts[7]],
        [verts[0], verts[4], verts[5], verts[1]],
        [verts[1], verts[5], verts[6], verts[2]],
        [verts[2], verts[6], verts[7], verts[3]],
        [verts[3], verts[7], verts[4], verts[0]],
    ]

    for f in faces:
        bm.faces.new(f)

    bm.to_mesh(me)
    bm.free()

    obj = bpy.data.objects.new(name, me)
    bpy.context.collection.objects.link(obj)
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)

    # 进入编辑模式，选择垂直边进行倒角
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='DESELECT')
    bpy.ops.mesh.select_mode(type='EDGE')
    
    # 选择垂直边（四个角的边）
    bpy.ops.object.mode_set(mode='OBJECT')
    for edge in obj.data.edges:
        v1 = obj.data.vertices[edge.vertices[0]]
        v2 = obj.data.vertices[edge.vertices[1]]
        # 垂直边：x和y坐标几乎相同
        if abs(v1.co.x - v2.co.x) < 0.001 and abs(v1.co.y - v2.co.y) < 0.001:
            edge.select = True
    
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.bevel(
        offset=corner_radius,
        offset_type='OFFSET',
        segments=segments,
        profile=0.5
    )
    bpy.ops.object.mode_set(mode='OBJECT')

    return obj

# 创建底壳
print("Creating bottom shell...")
shell = create_rounded_box("BottomShell", 100.0, 70.0, 10.0, 15.0, segments=8)
shell.location = (0, 0, 5.0)

# 添加材质
mat = bpy.data.materials.new(name='PlasticBlue')
mat.use_nodes = False
mat.diffuse_color = (0.4, 0.6, 0.9, 1.0)
shell.data.materials.append(mat)

print(f"Shell location: {shell.location}")
print(f"Shell dimensions: {shell.dimensions}")

# 创建相机
cam_data = bpy.data.cameras.new('Camera')
cam = bpy.data.objects.new('Camera', cam_data)
bpy.context.collection.objects.link(cam)
bpy.context.scene.camera = cam

# 顶视图相机位置
cam.location = (0, 0, 80)
cam.rotation_euler = (0, 0, 0)

# 设置渲染 - 使用Workbench引擎
bpy.context.scene.render.engine = 'BLENDER_WORKBENCH'
bpy.context.scene.render.resolution_x = 1920
bpy.context.scene.render.resolution_y = 1080

output_path = os.path.join(os.path.dirname(__file__), '..', '..', 'build', 'debug_bottom_shell.png')
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
