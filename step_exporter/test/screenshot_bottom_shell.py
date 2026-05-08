#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
生成底壳并截图
用法: blender --background --python screenshot_bottom_shell.py
"""

import bpy
import sys
import os
import time

# 导入底壳生成脚本
exec(open(r"F:\git\blender2step\step_exporter\test\create_bottom_shell.py").read())

# 生成底壳
create_bottom_shell_scene()

# 导出STEP
import _step_exporter as cpp_exporter

scale = 1000.0
output_path = r"F:\git\blender2step\build\bottom_shell.step"

def log_callback(msg):
    print(f"  [C++] {msg}")

# 获取底壳对象
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
            print(f"\nSTEP exported: {output_path} ({size} bytes)")
        else:
            print(f"\nFailed to export STEP")
    else:
        print(f"\nFailed to init STEP export")
else:
    print(f"\nBottomShell object not found!")
