#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
保存场景并导出STEP文件
"""
import bpy
import sys
import os

# 保存blend文件
blend_path = r"F:\git\blender2step\step_exporter\test\test28_mesh_cylinder.blend"
bpy.ops.wm.save_as_mainfile(filepath=blend_path)
print(f"Saved blend file to: {blend_path}")

# 选择所有物体
bpy.ops.object.select_all(action='SELECT')

# 设置导出参数
output_path = r"F:\git\blender2step\step_exporter\test28_mesh_cylinder.step"
print(f"Will export to: {output_path}")

# 运行导出脚本
sys.argv = ['--', '--test-number', '28_mesh_cylinder', '--output-dir', r'F:\git\blender2step\step_exporter']

# 导入并运行导出函数
exec(open(r"F:\git\blender2step\step_exporter\test\run_test.py").read())
