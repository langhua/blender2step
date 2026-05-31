#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
塑料顶壳生成器
使用Mesh创建塑料顶壳，导出时美化为解析曲面

结构组成：
1. 外盒体 - 带圆角的矩形盒
2. 内腔体 - 挖空形成顶壳（开口朝下）
3. 螺丝柱 x4（在顶板内侧，向下延伸）

与底壳的区别：
- 底壳：底板在底部，侧壁向上，开口朝上（托盘状）
- 顶壳：顶板在顶部，侧壁向下，开口朝下（盖子状）

使用方法：
1. 在Blender中打开Scripting工作区
2. 打开此脚本
3. 点击运行按钮
"""

import bpy
import bmesh
import math
import sys
import os
from collections import defaultdict


def clear_scene():
    for obj in list(bpy.data.objects):
        obj.modifiers.clear()
    for obj in list(bpy.data.objects):
        bpy.data.objects.remove(obj, do_unlink=True)
    for mesh in list(bpy.data.meshes):
        if mesh.users == 0:
            bpy.data.meshes.remove(mesh)


def add_material(obj, name=None):
    if not obj.data.materials:
        mat_name = name or f"{obj.name}_Material"
        mat = bpy.data.materials.new(name=mat_name)
        mat.use_nodes = False
        mat.diffuse_color = (0.4, 0.6, 0.9, 1.0)
        obj.data.materials.append(mat)


def apply_boolean(obj, tool_obj, operation='DIFFERENCE', solver='EXACT'):
    mod = obj.modifiers.new(name="Boolean", type='BOOLEAN')
    mod.operation = operation
    mod.object = tool_obj
    mod.solver = solver
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)

    # 保存原始网格数据（用于 EXACT 失败后回退）
    source_mesh = None
    if solver == 'EXACT':
        source_mesh = obj.data.copy()

    try:
        bpy.ops.object.modifier_apply(modifier=mod.name)
    except RuntimeError:
        if solver == 'EXACT':
            print(f"  [WARN] EXACT solver crashed, retrying with FAST...")
            if source_mesh:
                old_data = obj.data
                obj.data = source_mesh
                if old_data and old_data.users == 0:
                    bpy.data.meshes.remove(old_data)
            return apply_boolean(obj, tool_obj, operation, solver='FAST')
        raise

    # 检查结果是否为空
    if len(obj.data.polygons) == 0:
        if solver == 'EXACT':
            print(f"  [WARN] EXACT produced empty mesh, retrying with FAST...")
            if source_mesh:
                obj.data = source_mesh
            return apply_boolean(obj, tool_obj, operation, solver='FAST')
        else:
            print(f"  [ERROR] FAST solver also produced empty mesh!")

    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.mesh.remove_doubles(threshold=0.0001)
    bpy.ops.mesh.dissolve_limited(angle_limit=math.radians(1.0))
    bpy.ops.mesh.normals_make_consistent(inside=False)
    bpy.ops.object.mode_set(mode='OBJECT')


def create_rounded_box(name, width, depth, height, corner_radius, segments=24):
    """创建一个带有圆角的立方体，四个角是圆角"""
    hw = width / 2.0
    hd = depth / 2.0
    hh = height / 2.0

    max_radius = min(hw, hd) * 0.99
    corner_radius = min(corner_radius, max_radius)

    top_profile = []
    bottom_profile = []

    for i in range(segments):
        angle = (math.pi / 2) * i / segments
        x = hw - corner_radius + corner_radius * math.cos(angle)
        y = hd - corner_radius + corner_radius * math.sin(angle)
        top_profile.append((x, y, hh))
        bottom_profile.append((x, y, -hh))

    for i in range(segments):
        t = i / segments
        x = hw - corner_radius - t * (width - 2 * corner_radius)
        y = hd
        top_profile.append((x, y, hh))
        bottom_profile.append((x, y, -hh))

    for i in range(segments):
        angle = math.pi / 2 + (math.pi / 2) * i / segments
        x = -hw + corner_radius + corner_radius * math.cos(angle)
        y = hd - corner_radius + corner_radius * math.sin(angle)
        top_profile.append((x, y, hh))
        bottom_profile.append((x, y, -hh))

    for i in range(segments):
        t = i / segments
        x = -hw
        y = hd - corner_radius - t * (depth - 2 * corner_radius)
        top_profile.append((x, y, hh))
        bottom_profile.append((x, y, -hh))

    for i in range(segments):
        angle = math.pi + (math.pi / 2) * i / segments
        x = -hw + corner_radius + corner_radius * math.cos(angle)
        y = -hd + corner_radius + corner_radius * math.sin(angle)
        top_profile.append((x, y, hh))
        bottom_profile.append((x, y, -hh))

    for i in range(segments):
        t = i / segments
        x = -hw + corner_radius + t * (width - 2 * corner_radius)
        y = -hd
        top_profile.append((x, y, hh))
        bottom_profile.append((x, y, -hh))

    for i in range(segments):
        angle = 3 * math.pi / 2 + (math.pi / 2) * i / segments
        x = hw - corner_radius + corner_radius * math.cos(angle)
        y = -hd + corner_radius + corner_radius * math.sin(angle)
        top_profile.append((x, y, hh))
        bottom_profile.append((x, y, -hh))

    for i in range(segments):
        t = i / segments
        x = hw
        y = -hd + corner_radius + t * (depth - 2 * corner_radius)
        top_profile.append((x, y, hh))
        bottom_profile.append((x, y, -hh))

    me = bpy.data.meshes.new(name=name)
    bm = bmesh.new()

    top_verts = [bm.verts.new(v) for v in top_profile]
    bottom_verts = [bm.verts.new(v) for v in bottom_profile]

    num_profile = len(top_profile)
    for i in range(num_profile):
        next_i = (i + 1) % num_profile
        face = [top_verts[i], top_verts[next_i], bottom_verts[next_i], bottom_verts[i]]
        bm.faces.new(face)

    top_center = bm.verts.new((0, 0, hh))
    for i in range(num_profile):
        next_i = (i + 1) % num_profile
        face = [top_center, top_verts[i], top_verts[next_i]]
        bm.faces.new(face)

    bottom_center = bm.verts.new((0, 0, -hh))
    for i in range(num_profile):
        next_i = (i + 1) % num_profile
        face = [bottom_center, bottom_verts[next_i], bottom_verts[i]]
        bm.faces.new(face)

    bm.to_mesh(me)
    bm.free()

    obj = bpy.data.objects.new(name, me)
    bpy.context.collection.objects.link(obj)
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    bpy.ops.object.shade_smooth()

    return obj


def create_hollow_top_shell(name, width, depth, outer_height, top_thickness,
                            wall_thickness, corner_radius, location, segments=24,
                            holes=None):
    """
    创建中空顶壳：内盒向下偏移 → 外盒切除
    与底壳相反：顶壳的开口朝下（内腔从底部挖入）
    """
    outer = create_rounded_box(
        name=f"{name}_Outer",
        width=width,
        depth=depth,
        height=outer_height,
        corner_radius=corner_radius,
        segments=segments
    )
    outer.location = location

    inner_width = width - 2 * wall_thickness
    inner_depth = depth - 2 * wall_thickness
    inner_height = outer_height - top_thickness + 0.1
    inner_corner_r = max(corner_radius - wall_thickness, 1.0)

    inner = create_rounded_box(
        name=f"{name}_Inner",
        width=inner_width,
        depth=inner_depth,
        height=inner_height,
        corner_radius=inner_corner_r,
        segments=segments
    )
    # 内盒向下偏移（开口朝下）
    outer_half_h = outer_height / 2.0
    inner_half_h = inner_height / 2.0
    inner_z = location[2] + outer_half_h - top_thickness - inner_half_h - 0.05
    inner.location = (location[0], location[1], inner_z)

    # 螺丝柱（从顶板内面向下延伸到接近底边）
    if holes:
        hole_radius, hole_offset_x, hole_offset_y, boss_depth = holes
        hw = width / 2.0
        hd = depth / 2.0
        hole_cx = hw - hole_offset_x
        hole_cy = hd - hole_offset_y
        # 顶板内面 Z
        top_inner_z = location[2] + outer_half_h - top_thickness
        # 底边 Z（开口处）
        bottom_edge_z = location[2] - outer_half_h

        corner_positions = [
            (hole_cx, hole_cy),
            (-hole_cx, hole_cy),
            (-hole_cx, -hole_cy),
            (hole_cx, -hole_cy),
        ]
        boss_objs = []
        for i, (cx, cy) in enumerate(corner_positions):
            cyl_h = abs(top_inner_z - bottom_edge_z) + 1.0
            cyl_z = (top_inner_z + bottom_edge_z) / 2.0
            bpy.ops.mesh.primitive_cylinder_add(
                vertices=64,
                radius=hole_radius,
                depth=cyl_h,
                location=(location[0] + cx, location[1] + cy, cyl_z),
            )
            boss_obj = bpy.context.active_object
            boss_obj.name = f"{name}_Boss_{i}"
            boss_objs.append(boss_obj)

        # 螺丝柱与内盒融合 → 再切除
        for i, boss_obj in enumerate(boss_objs):
            mod = outer.modifiers.new(name=f"Boolean_Boss_{i}", type='BOOLEAN')
            mod.operation = 'DIFFERENCE'
            mod.object = boss_obj
            mod.solver = 'FAST'

        bpy.context.view_layer.objects.active = outer
        for i in range(len(boss_objs)):
            bpy.ops.object.modifier_apply(modifier=f"Boolean_Boss_{i}")

        for boss_obj in boss_objs:
            bpy.data.objects.remove(boss_obj, do_unlink=True)

    apply_boolean(outer, inner, operation='DIFFERENCE')
    bpy.data.objects.remove(inner, do_unlink=True)
    outer.name = name
    return outer


def create_rounded_box_filleted(name, width, depth, height, corner_radius,
                                 bottom_fillet_radius, segments=24, top_recess=0,
                                 top_offset_y=0):
    """
    创建带底部圆倒角的圆角矩形体
    使用 BMesh，底部添加圆角过渡
    top_recess: 底部平面在圆角基础上额外内收量（用于顶壳翻转后顶面内收）
    top_offset_y: 底面向-Y偏移量（用于顶壳翻转后顶面后移）
    """
    hw = width / 2.0
    hd = depth / 2.0
    hh = height / 2.0
    fr = min(bottom_fillet_radius, height * 0.45)

    me = bpy.data.meshes.new(name=name)
    bm = bmesh.new()

    # 顶部轮廓
    top_profile = []
    for i in range(segments):
        angle = (math.pi / 2) * i / segments
        x = hw - corner_radius + corner_radius * math.cos(angle)
        y = hd - corner_radius + corner_radius * math.sin(angle)
        top_profile.append((x, y, hh))
    for i in range(segments):
        t = i / segments
        x = hw - corner_radius - t * (width - 2 * corner_radius)
        y = hd
        top_profile.append((x, y, hh))
    for i in range(segments):
        angle = math.pi / 2 + (math.pi / 2) * i / segments
        x = -hw + corner_radius + corner_radius * math.cos(angle)
        y = hd - corner_radius + corner_radius * math.sin(angle)
        top_profile.append((x, y, hh))
    for i in range(segments):
        t = i / segments
        x = -hw
        y = hd - corner_radius - t * (depth - 2 * corner_radius)
        top_profile.append((x, y, hh))
    for i in range(segments):
        angle = math.pi + (math.pi / 2) * i / segments
        x = -hw + corner_radius + corner_radius * math.cos(angle)
        y = -hd + corner_radius + corner_radius * math.sin(angle)
        top_profile.append((x, y, hh))
    for i in range(segments):
        t = i / segments
        x = -hw + corner_radius + t * (width - 2 * corner_radius)
        y = -hd
        top_profile.append((x, y, hh))
    for i in range(segments):
        angle = 3 * math.pi / 2 + (math.pi / 2) * i / segments
        x = hw - corner_radius + corner_radius * math.cos(angle)
        y = -hd + corner_radius + corner_radius * math.sin(angle)
        top_profile.append((x, y, hh))
    for i in range(segments):
        t = i / segments
        x = hw
        y = -hd + corner_radius + t * (depth - 2 * corner_radius)
        top_profile.append((x, y, hh))

    # 曲线侧壁：从顶部全宽到底部内收，余弦曲线平滑过渡
    total_recess = fr + top_recess
    side_segs = segments * 2  # 侧壁曲线层数
    layers = []

    num_profile = len(top_profile)

    for sl in range(1, side_segs + 1):
        # z 从接近 +hh（紧贴顶面）到底部 -hh（完全内收）
        z_val = hh - (2 * hh) * sl / side_segs
        t = sl / side_segs  # 0 at +hh(full), 1 at -hh(recessed)
        inset = total_recess * (1 - math.cos(math.pi / 2 * t))
        y_offs = top_offset_y * (1 - math.cos(math.pi / 2 * t))  # Y偏移随曲线同步

        layer_hw = hw - inset
        layer_hd = hd - inset
        layer_cr = max(corner_radius - inset, 0.1)
        profile = []
        for i in range(segments):
            angle = (math.pi / 2) * i / segments
            x = layer_hw - layer_cr + layer_cr * math.cos(angle)
            y = layer_hd - layer_cr + layer_cr * math.sin(angle) - y_offs
            profile.append((x, y, z_val))
        for i in range(segments):
            t_seg = i / segments
            x = layer_hw - layer_cr - t_seg * (layer_hw * 2 - 2 * layer_cr)
            y = layer_hd - y_offs
            profile.append((x, y, z_val))
        for i in range(segments):
            angle = math.pi / 2 + (math.pi / 2) * i / segments
            x = -layer_hw + layer_cr + layer_cr * math.cos(angle)
            y = layer_hd - layer_cr + layer_cr * math.sin(angle) - y_offs
            profile.append((x, y, z_val))
        for i in range(segments):
            t_seg = i / segments
            x = -layer_hw
            y = layer_hd - layer_cr - t_seg * (layer_hd * 2 - 2 * layer_cr) - y_offs
            profile.append((x, y, z_val))
        for i in range(segments):
            angle = math.pi + (math.pi / 2) * i / segments
            x = -layer_hw + layer_cr + layer_cr * math.cos(angle)
            y = -layer_hd + layer_cr + layer_cr * math.sin(angle) - y_offs
            profile.append((x, y, z_val))
        for i in range(segments):
            t_seg = i / segments
            x = -layer_hw + layer_cr + t_seg * (layer_hw * 2 - 2 * layer_cr)
            y = -layer_hd - y_offs
            profile.append((x, y, z_val))
        for i in range(segments):
            angle = 3 * math.pi / 2 + (math.pi / 2) * i / segments
            x = layer_hw - layer_cr + layer_cr * math.cos(angle)
            y = -layer_hd + layer_cr + layer_cr * math.sin(angle) - y_offs
            profile.append((x, y, z_val))
        for i in range(segments):
            t_seg = i / segments
            x = layer_hw
            y = -layer_hd + layer_cr + t_seg * (layer_hd * 2 - 2 * layer_cr) - y_offs
            profile.append((x, y, z_val))
        layers.append(profile)

    top_verts = [bm.verts.new(v) for v in top_profile]
    layer_verts = []
    for profile in layers:
        layer_verts.append([bm.verts.new(v) for v in profile])

    # 顶面（全宽，翻转后成为开口底部）
    top_center = bm.verts.new((0, 0, hh))
    for i in range(num_profile):
        next_i = (i + 1) % num_profile
        bm.faces.new([top_center, top_verts[i], top_verts[next_i]])

    # 侧壁曲线：top_verts → layers[0] → ... → layers[-1]
    for i in range(num_profile):
        next_i = (i + 1) % num_profile
        bm.faces.new([top_verts[i], top_verts[next_i],
                      layer_verts[0][next_i], layer_verts[0][i]])

    for li in range(len(layers) - 1):
        for i in range(num_profile):
            next_i = (i + 1) % num_profile
            bm.faces.new([layer_verts[li][i], layer_verts[li][next_i],
                          layer_verts[li + 1][next_i], layer_verts[li + 1][i]])

    # 底面（内收，翻转后成为顶面）：layers[-1] 直接作为底面轮廓
    bottom_z = -hh
    bottom_profile = layers[-1]
    bottom_center = bm.verts.new((0, -top_offset_y, bottom_z))
    bottom_verts = [bm.verts.new(v) for v in bottom_profile]
    for i in range(num_profile):
        next_i = (i + 1) % num_profile
        bm.faces.new([bottom_center, bottom_verts[next_i], bottom_verts[i]])

    bm.to_mesh(me)
    bm.free()
    me.update(calc_edges=True)
    # 验证网格
    print(f"  [DEBUG] {name}: {len(me.polygons)} faces, {len(me.vertices)} verts, {len(me.edges)} edges")
    if len(me.polygons) == 0:
        print(f"  [WARNING] {name}: 0 faces in mesh!")
    # 确保法线向外
    for p in me.polygons:
        p.use_smooth = False
    obj = bpy.data.objects.new(name, me)
    bpy.context.collection.objects.link(obj)
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    return obj


def create_ring_solid(name, width, depth, corner_radius, ring_width, ring_height,
                      segments=24):
    """
    创建环形实体（1×1mm 横截面），沿圆角矩形轮廓走一圈
    外轮廓：rounded rect (width/2, depth/2, corner_radius) — 与侧壁外侧对齐
    内轮廓：rounded rect (width/2-ring_width, depth/2-ring_width, corner_radius-ring_width) — 向内收缩
    顶面在 z=0，底面在 z=-ring_height
    """
    hw = width / 2.0
    hd = depth / 2.0
    cr = corner_radius
    inner_hw = hw - ring_width
    inner_hd = hd - ring_width
    inner_cr = max(cr - ring_width, 0.1)

    def gen_profile(hw, hd, cr, z_val, y_offs=0):
        profile = []
        for i in range(segments):
            angle = (math.pi / 2) * i / segments
            x = hw - cr + cr * math.cos(angle)
            y = hd - cr + cr * math.sin(angle) - y_offs
            profile.append((x, y, z_val))
        for i in range(segments):
            t = i / segments
            x = hw - cr - t * (hw * 2 - 2 * cr)
            y = hd - y_offs
            profile.append((x, y, z_val))
        for i in range(segments):
            angle = math.pi / 2 + (math.pi / 2) * i / segments
            x = -hw + cr + cr * math.cos(angle)
            y = hd - cr + cr * math.sin(angle) - y_offs
            profile.append((x, y, z_val))
        for i in range(segments):
            t = i / segments
            x = -hw
            y = hd - cr - t * (hd * 2 - 2 * cr) - y_offs
            profile.append((x, y, z_val))
        for i in range(segments):
            angle = math.pi + (math.pi / 2) * i / segments
            x = -hw + cr + cr * math.cos(angle)
            y = -hd + cr + cr * math.sin(angle) - y_offs
            profile.append((x, y, z_val))
        for i in range(segments):
            t = i / segments
            x = -hw + cr + t * (hw * 2 - 2 * cr)
            y = -hd - y_offs
            profile.append((x, y, z_val))
        for i in range(segments):
            angle = 3 * math.pi / 2 + (math.pi / 2) * i / segments
            x = hw - cr + cr * math.cos(angle)
            y = -hd + cr + cr * math.sin(angle) - y_offs
            profile.append((x, y, z_val))
        for i in range(segments):
            t = i / segments
            x = hw
            y = -hd + cr + t * (hd * 2 - 2 * cr) - y_offs
            profile.append((x, y, z_val))
        return profile

    inner_top = gen_profile(inner_hw, inner_hd, inner_cr, 0)
    outer_top = gen_profile(hw, hd, cr, 0)
    inner_bot = gen_profile(inner_hw, inner_hd, inner_cr, -ring_height)
    outer_bot = gen_profile(hw, hd, cr, -ring_height)

    num_profile = len(inner_top)

    me = bpy.data.meshes.new(name=name)
    bm = bmesh.new()

    itv = [bm.verts.new(v) for v in inner_top]
    otv = [bm.verts.new(v) for v in outer_top]
    ibv = [bm.verts.new(v) for v in inner_bot]
    obv = [bm.verts.new(v) for v in outer_bot]

    for i in range(num_profile):
        ni = (i + 1) % num_profile
        bm.faces.new([itv[i], itv[ni], otv[ni], otv[i]])

    for i in range(num_profile):
        ni = (i + 1) % num_profile
        bm.faces.new([obv[i], obv[ni], ibv[ni], ibv[i]])

    for i in range(num_profile):
        ni = (i + 1) % num_profile
        bm.faces.new([otv[i], otv[ni], obv[ni], obv[i]])

    for i in range(num_profile):
        ni = (i + 1) % num_profile
        bm.faces.new([ibv[i], ibv[ni], itv[ni], itv[i]])

    bm.to_mesh(me)
    bm.free()
    me.update(calc_edges=True)

    obj = bpy.data.objects.new(name, me)
    bpy.context.collection.objects.link(obj)
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    return obj


def create_filleted_top_shell(name, width, depth, outer_height, top_thickness,
                               wall_thickness, corner_radius,
                               outer_fillet_radius, inner_fillet_radius,
                               location=(0, 0, 0), segments=24, step_height=1.5,
                               holes=None, top_offset_y=3, window=None,
                               outer_ring_width=0, outer_ring_height=0):
    """
    创建带圆倒角的中空顶壳
    create_rounded_box_filleted 构建从底部到顶部内收的余弦曲线侧壁，
    翻转 180° 使开口朝下、曲线侧壁从底全宽平滑过渡到顶内收面
    top_offset_y: 顶面相对底框的Y向偏移量
    window: (length, width) 顶面矩形窗口尺寸，None 则不开口
    outer_ring_width: 底部边框外侧环的宽度（水平向外扩展）
    outer_ring_height: 底部边框外侧环的高度（垂直向下延伸）
    """
    outer_half_h = outer_height / 2.0
    actual_outer_r = min(outer_fillet_radius, outer_height * 0.45, corner_radius * 0.45)
    print(f"  Outer fillet radius: {actual_outer_r:.3f} mm")

    # 创建外盒（倒角在底部），绕 X 轴翻转 180° → 倒角在顶部
    outer = create_rounded_box_filleted(
        name=f"{name}_Outer",
        width=width,
        depth=depth,
        height=outer_height,
        corner_radius=corner_radius,
        bottom_fillet_radius=actual_outer_r,
        segments=segments,
        top_recess=10,
        top_offset_y=top_offset_y,
    )
    bpy.context.view_layer.objects.active = outer
    outer.select_set(True)
    outer.rotation_euler = (math.pi, 0, 0)
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=False)
    outer.location = location

    # 内腔：尺寸比外盒小 wall_thickness
    inner_width = width - 2 * wall_thickness
    inner_depth = depth - 2 * wall_thickness
    inner_height = outer_height - top_thickness + 0.1
    inner_corner_r = max(corner_radius - wall_thickness, 1.0)
    actual_inner_r = min(inner_fillet_radius, inner_height * 0.45, inner_corner_r * 0.45)

    inner = create_rounded_box_filleted(
        name=f"{name}_Inner",
        width=inner_width,
        depth=inner_depth,
        height=inner_height,
        corner_radius=inner_corner_r,
        bottom_fillet_radius=actual_inner_r,
        segments=segments,
        top_recess=10,
        top_offset_y=top_offset_y
    )
    bpy.context.view_layer.objects.active = inner
    inner.select_set(True)
    inner.rotation_euler = (math.pi, 0, 0)
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=False)
    # 内盒向下偏移（开口朝下）
    inner_z = location[2] + outer_half_h - top_thickness - inner_height / 2.0 - 0.05
    inner.location = (location[0], location[1], inner_z)
    print(f"  Inner fillet radius: {actual_inner_r:.3f} mm")

    # 先切内腔，再开窗（避免 EXACT 对已有窗口的几何体处理异常）
    apply_boolean(outer, inner, operation='DIFFERENCE')
    bpy.data.objects.remove(inner, do_unlink=True)

    # 顶面矩形窗口
    if window:
        win_len, win_wid = window
        top_wall_center_z = location[2] + outer_half_h - top_thickness / 2.0
        top_center_y = location[1] - top_offset_y
        cutter_depth = top_thickness + 4.0

        bpy.ops.mesh.primitive_cube_add(
            size=1.0,
            location=(location[0], top_center_y, top_wall_center_z),
        )
        cutter = bpy.context.active_object
        cutter.name = f"{name}_WindowCutter"
        cutter.dimensions = (win_len, win_wid, cutter_depth)
        bpy.ops.object.transform_apply(scale=True)

        apply_boolean(outer, cutter, operation='DIFFERENCE')
        bpy.data.objects.remove(cutter, do_unlink=True)

    if outer_ring_width > 0 and outer_ring_height > 0:
        ring_z = location[2] - outer_half_h
        ring = create_ring_solid(
            name=f"{name}_Ring",
            width=width,
            depth=depth,
            corner_radius=corner_radius,
            ring_width=outer_ring_width,
            ring_height=outer_ring_height,
            segments=segments,
        )
        ring.location = (location[0], location[1], ring_z)
        apply_boolean(outer, ring, operation='UNION')
        bpy.data.objects.remove(ring, do_unlink=True)

    outer.name = name
    return outer


def measure_top_shell_fillet_radii(obj):
    """
    测量顶壳的顶部外壁圆倒角半径
    顶壳的倒角在顶部（z 坐标最高处），不是底部
    """
    depsgraph = bpy.context.evaluated_depsgraph_get()
    eval_obj = obj.evaluated_get(depsgraph)
    mesh_data = eval_obj.data

    bm = bmesh.new()
    bm.from_mesh(mesh_data)
    bm.verts.ensure_lookup_table()

    z_layers = defaultdict(list)
    for v in bm.verts:
        z_key = round(v.co.z / 0.01) * 0.01
        z_layers[z_key].append(v)

    sorted_z = sorted(z_layers.keys())
    if len(sorted_z) < 2:
        bm.free()
        return None, None

    total_z = len(sorted_z)
    max_z = sorted_z[-1]
    min_z = sorted_z[0]

    # 顶部外壁圆角：从最高处向下找第一个间隙
    outer_top_z = max_z
    outer_wall_start_z = None
    for i in range(total_z - 1, 0, -1):
        gap = sorted_z[i] - sorted_z[i - 1]
        levels_before = i
        if levels_before > total_z * 0.25 and gap > 0.1:
            outer_wall_start_z = sorted_z[i]
            break

    if outer_wall_start_z is None:
        outer_wall_start_z = sorted_z[1] if total_z > 1 else sorted_z[0]

    outer_radius = max_z - outer_wall_start_z
    if outer_radius is not None and outer_radius > 0.01:
        print(f"  Measured outer top fillet radius: {outer_radius:.3f} mm")
    else:
        outer_radius = None
        print(f"  Measured outer top fillet radius: N/A")

    inner_radius = None
    print(f"  Measured inner fillet radius: N/A (bevel-based, use preset)")

    bm.free()
    return outer_radius, inner_radius


# ============================================================================
# 场景生成
# ============================================================================

def create_top_shell_scene():
    print("\n" + "=" * 60)
    print("Plastic Top Shell Generator")
    print("=" * 60)

    print("[1/5] Clearing scene...")
    clear_scene()

    width = 100.0
    depth = 70.0
    outer_height = 10.0
    top_thickness = 2.0
    wall_thickness = 2.0
    corner_radius = 20.0
    outer_fillet_radius = 1.5
    inner_fillet_radius = 0.75
    window_length = 20.0
    window_width = 10.0

    print("[2/5] Creating filleted top shell WITHOUT window...")
    shell_no_holes = create_filleted_top_shell(
        name="TopShell_NoHoles",
        width=width,
        depth=depth,
        outer_height=outer_height,
        top_thickness=top_thickness,
        wall_thickness=wall_thickness,
        corner_radius=corner_radius,
        outer_fillet_radius=outer_fillet_radius,
        inner_fillet_radius=inner_fillet_radius,
        location=(-60, 0, 0),
        segments=24,
        outer_ring_width=1.0,
        outer_ring_height=1.0,
    )
    add_material(shell_no_holes, name="TopShellNoHolesMaterial")
    print(f"  [OK] Top shell (no window) created")

    print("[3/5] Creating filleted top shell WITH window...")
    shell_with_holes = create_filleted_top_shell(
        name="TopShell_WithHoles",
        width=width,
        depth=depth,
        outer_height=outer_height,
        top_thickness=top_thickness,
        wall_thickness=wall_thickness,
        corner_radius=corner_radius,
        outer_fillet_radius=outer_fillet_radius,
        inner_fillet_radius=inner_fillet_radius,
        location=(60, 0, 0),
        segments=24,
        window=(window_length, window_width),
        outer_ring_width=1.0,
        outer_ring_height=1.0,
    )
    add_material(shell_with_holes, name="TopShellWithHolesMaterial")
    print(f"  [OK] Top shell (with window) created")

    for area in bpy.context.screen.areas:
        if area.type == 'VIEW_3D':
            for space in area.spaces:
                if space.type == 'VIEW_3D':
                    space.shading.type = 'SOLID'
                    space.overlay.show_wireframes = False

    print("[4/5] Measuring top fillet radii from mesh...")
    outer_fr, inner_fr = measure_top_shell_fillet_radii(shell_no_holes)

    print("\n" + "=" * 60)
    print("[OK] Top shell scene created!")
    print("=" * 60)
    print(f"\n  Parameters:")
    print(f"    Outer: {width} x {depth} x {outer_height} mm")
    print(f"    Corner radius: {corner_radius} mm")
    print(f"    Top thickness: {top_thickness} mm")
    print(f"    Wall thickness: {wall_thickness} mm")
    print(f"    Outer fillet radius: {outer_fr:.3f} mm" if outer_fr else f"    Outer fillet: default {outer_fillet_radius} mm")
    print(f"    Inner fillet radius: {inner_fr:.3f} mm" if inner_fr else f"    Inner fillet: default {inner_fillet_radius} mm")
    print(f"    Window: {window_length} x {window_width} mm")
    print(f"\n  Objects:")
    print(f"    1. TopShell_NoHoles  (left,  no window)")
    print(f"    2. TopShell_WithWindow (right, with window)")
    print("\nNext: File -> Export -> STEP (Enhanced)")


def create_top_shell_simple():
    """创建简单顶壳（无圆倒角）"""
    print("\n" + "=" * 60)
    print("Simple Top Shell Generator")
    print("=" * 60)

    print("[1/3] Clearing scene...")
    clear_scene()

    width = 100.0
    depth = 70.0
    height = 10.0
    corner_r = 20.0

    print("[2/3] Creating simple rounded box...")
    obj = create_rounded_box(
        name="SimpleTopShell",
        width=width,
        depth=depth,
        height=height,
        corner_radius=corner_r,
        segments=32
    )
    obj.location = (0, 0, 0)
    add_material(obj)

    print(f"  [OK] Simple top shell: {width} x {depth} x {height} mm")
    print("\n" + "=" * 60)
    print("[OK] Simple top shell scene created!")
    print("=" * 60)


if __name__ == "__main__":
    create_top_shell_scene()