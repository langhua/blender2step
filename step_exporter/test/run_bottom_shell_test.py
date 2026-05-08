#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
生成底壳并截图（使用Blender内置渲染）
用法: blender --background --python run_bottom_shell_test.py
"""

import bpy
import sys
import os

# 导入底壳生成脚本
exec(open(r"F:\git\blender2step\step_exporter\test\create_bottom_shell.py").read())

# 生成底壳
create_bottom_shell_scene()

# 设置相机位置 - 等轴测视角，能看到完整底壳
cam = bpy.data.objects.get('Camera')
if not cam:
    cam_data = bpy.data.cameras.new('Camera')
    cam = bpy.data.objects.new('Camera', cam_data)
    bpy.context.collection.objects.link(cam)
    bpy.context.scene.camera = cam

# 等轴测视角：从较远距离拍摄，展示完整底壳和墙壁
cam.location = (120, -120, 55)
cam.rotation_euler = (1.15, 0, 0.785)

# 设置灯光 - 增强对比度的三点布光
# 主光（强，从右上方）
main_light = bpy.data.lights.new(name='MainLight', type='SUN')
main_light.energy = 8
main_light_obj = bpy.data.objects.new(name='MainLight', object_data=main_light)
main_light_obj.location = (60, -60, 80)
main_light_obj.rotation_euler = (0.7, 0, 0.5)
bpy.context.collection.objects.link(main_light_obj)

# 补光（弱，从左下方，填充阴影）
fill_light = bpy.data.lights.new(name='FillLight', type='SUN')
fill_light.energy = 3
fill_light_obj = bpy.data.objects.new(name='FillLight', object_data=fill_light)
fill_light_obj.location = (-60, 60, 30)
fill_light_obj.rotation_euler = (0.4, 0, 2.8)
bpy.context.collection.objects.link(fill_light_obj)

# 背光（中等，从后方，勾勒轮廓）
back_light = bpy.data.lights.new(name='BackLight', type='SUN')
back_light.energy = 4
back_light_obj = bpy.data.objects.new(name='BackLight', object_data=back_light)
back_light_obj.location = (0, 80, 50)
back_light_obj.rotation_euler = (1.0, 0, 3.14)
bpy.context.collection.objects.link(back_light_obj)

# 设置渲染
bpy.context.scene.render.engine = 'BLENDER_EEVEE_NEXT'
bpy.context.scene.render.resolution_x = 1920
bpy.context.scene.render.resolution_y = 1080
bpy.context.scene.render.filepath = r"F:\git\blender2step\build\bottom_shell-blender.png"
bpy.context.scene.render.image_settings.file_format = 'PNG'

# 启用阴影和环境光遮蔽
bpy.context.scene.eevee.use_shadows = True
bpy.context.scene.eevee.use_gtao = True
bpy.context.scene.eevee.gtao_distance = 5.0

# 设置背景为浅蓝灰色（与白色物体形成对比）
bpy.context.scene.world = bpy.data.worlds.new('World')
bpy.context.scene.world.use_nodes = False
bpy.context.scene.world.color = (0.85, 0.88, 0.92)

# 给底壳添加材质 - 浅蓝色塑料
shell_obj = bpy.data.objects.get('BottomShell')
if shell_obj:
    mat = bpy.data.materials.new(name='PlasticBlue')
    mat.use_nodes = False
    mat.diffuse_color = (0.4, 0.6, 0.9, 1.0)
    mat.specular_intensity = 0.5
    if shell_obj.data.materials:
        shell_obj.data.materials[0] = mat
    else:
        shell_obj.data.materials.append(mat)

# 渲染
bpy.ops.render.render(write_still=True)
print(f"Rendered to {bpy.context.scene.render.filepath}")

# 导出STEP
import _step_exporter as cpp_exporter

scale = 1000.0
output_path = r"F:\git\blender2step\build\bottom_shell.step"

def log_callback(msg):
    pass  # Silent export

shell_obj = None
for obj in bpy.context.scene.objects:
    if obj.type == 'MESH' and obj.name == 'BottomShell':
        shell_obj = obj
        break

if shell_obj:
    depsgraph = bpy.context.evaluated_depsgraph_get()
    eval_obj = shell_obj.evaluated_get(depsgraph)
    mesh = eval_obj.data

    vertices = []
    for vert in mesh.vertices:
        world_co = eval_obj.matrix_world @ vert.co
        vertices.append([float(world_co.x) * scale, float(world_co.y) * scale, float(world_co.z) * scale])

    mesh.calc_loop_triangles()
    faces = []
    for tri in mesh.loop_triangles:
        faces.append(list(tri.vertices))

    normals = []
    for tri in mesh.loop_triangles:
        normals.append([float(tri.normal.x), float(tri.normal.y), float(tri.normal.z)])

    obj_data = {
        'name': shell_obj.name,
        'type': 'mesh',
        'vertices': vertices,
        'faces': faces,
        'normals': normals,
        'matrix_world': list(eval_obj.matrix_world),
    }

    success = cpp_exporter.init_incremental_export(
        output_path, 1, scale,
        1, 1, 1,
        'AP214DIS', 'MILLIMETER',
        1, 0.001,
        log_callback
    )

    if success:
        ok = cpp_exporter.add_object_to_export(obj_data, None)
        cpp_exporter.finalize_incremental_export()
        if ok:
            size = os.path.getsize(output_path)
            print(f"STEP exported: {output_path} ({size} bytes)")
        else:
            print(f"Failed to export STEP")
    else:
        print(f"Failed to init STEP export")
else:
    print(f"BottomShell object not found!")
