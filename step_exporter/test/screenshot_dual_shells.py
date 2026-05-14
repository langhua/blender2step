#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
生成双底壳截图（Blender渲染）
用法: blender --background --python screenshot_dual_shells.py
"""

import bpy
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import create_bottom_shell

create_bottom_shell.create_filleted_bottom_shells_scene()

cam = bpy.data.objects.get('Camera')
if not cam:
    cam_data = bpy.data.cameras.new('Camera')
    cam = bpy.data.objects.new('Camera', cam_data)
    bpy.context.collection.objects.link(cam)
    bpy.context.scene.camera = cam

cam.location = (0, -280, 90)
cam.rotation_euler = (1.2, 0, 0)
cam.data.type = 'PERSP'
cam.data.lens = 35

main_light = bpy.data.lights.new(name='MainLight', type='SUN')
main_light.energy = 8
main_light_obj = bpy.data.objects.new(name='MainLight', object_data=main_light)
main_light_obj.location = (60, -60, 80)
main_light_obj.rotation_euler = (0.7, 0, 0.5)
bpy.context.collection.objects.link(main_light_obj)

fill_light = bpy.data.lights.new(name='FillLight', type='SUN')
fill_light.energy = 3
fill_light_obj = bpy.data.objects.new(name='FillLight', object_data=fill_light)
fill_light_obj.location = (-60, 60, 30)
fill_light_obj.rotation_euler = (0.4, 0, 2.8)
bpy.context.collection.objects.link(fill_light_obj)

back_light = bpy.data.lights.new(name='BackLight', type='SUN')
back_light.energy = 4
back_light_obj = bpy.data.objects.new(name='BackLight', object_data=back_light)
back_light_obj.location = (0, 80, 50)
back_light_obj.rotation_euler = (1.0, 0, 3.14)
bpy.context.collection.objects.link(back_light_obj)

bpy.context.scene.render.engine = 'BLENDER_EEVEE_NEXT'
bpy.context.scene.render.resolution_x = 1920
bpy.context.scene.render.resolution_y = 1080
bpy.context.scene.render.filepath = r"F:\git\blender2step\build\bottom_shell_blender.png"
bpy.context.scene.render.image_settings.file_format = 'PNG'

bpy.context.scene.eevee.use_shadows = True
bpy.context.scene.eevee.use_gtao = True
bpy.context.scene.eevee.gtao_distance = 5.0

bpy.context.scene.world = bpy.data.worlds.new('World')
bpy.context.scene.world.use_nodes = False
bpy.context.scene.world.color = (0.85, 0.88, 0.92)

for obj in bpy.context.scene.objects:
    if obj.type == 'MESH':
        print(f"  Object: {obj.name}, vertices: {len(obj.data.vertices)}, location: {obj.location}")

bpy.ops.render.render(write_still=True)
print(f"Rendered to {bpy.context.scene.render.filepath}")