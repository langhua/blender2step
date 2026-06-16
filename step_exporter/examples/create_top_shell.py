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


def create_rounded_rect_cutter(name, width, height, corner_radius, depth, segments=8):
    """
    创建圆角矩形截面沿Y轴挤出的 cutter 实体（用于布尔挖孔）
    先用 BMesh 建平面轮廓，再用 Blender 原生 extrude 沿 Y 挤出
    width:  X 方向尺寸
    height: Z 方向尺寸
    corner_radius: 圆角半径
    depth:  Y 方向挤出深度
    """
    hw = width / 2.0
    hh = height / 2.0
    cr = min(corner_radius, hw * 0.99, hh * 0.99)

    # 生成圆角矩形轮廓（在 XZ 平面，Y=0）
    profile_xy = []
    # 右上角弧 (0 → π/2)
    for i in range(segments + 1):
        angle = math.pi / 2 * i / segments
        x = hw - cr + cr * math.cos(angle)
        z = hh - cr + cr * math.sin(angle)
        profile_xy.append((x, z))
    profile_xy.pop()
    # 上边
    for i in range(1, segments + 1):
        t = i / segments
        x = hw - cr - t * (width - 2 * cr)
        profile_xy.append((x, hh))
    profile_xy.pop()
    # 左上角弧 (π/2 → π)
    for i in range(1, segments + 1):
        angle = math.pi / 2 + math.pi / 2 * i / segments
        x = -hw + cr + cr * math.cos(angle)
        z = hh - cr + cr * math.sin(angle)
        profile_xy.append((x, z))
    profile_xy.pop()
    # 左边
    for i in range(1, segments + 1):
        t = i / segments
        z = hh - cr - t * (height - 2 * cr)
        profile_xy.append((-hw, z))
    profile_xy.pop()
    # 左下角弧 (π → 3π/2)
    for i in range(1, segments + 1):
        angle = math.pi + math.pi / 2 * i / segments
        x = -hw + cr + cr * math.cos(angle)
        z = -hh + cr + cr * math.sin(angle)
        profile_xy.append((x, z))
    profile_xy.pop()
    # 下边
    for i in range(1, segments + 1):
        t = i / segments
        x = -hw + cr + t * (width - 2 * cr)
        profile_xy.append((x, -hh))
    profile_xy.pop()
    # 右下角弧 (3π/2 → 2π)
    for i in range(1, segments + 1):
        angle = 3 * math.pi / 2 + math.pi / 2 * i / segments
        x = hw - cr + cr * math.cos(angle)
        z = -hh + cr + cr * math.sin(angle)
        profile_xy.append((x, z))
    profile_xy.pop()
    # 右边
    for i in range(1, segments + 1):
        t = i / segments
        z = -hh + cr + t * (height - 2 * cr)
        profile_xy.append((hw, z))
    profile_xy.pop()

    # 用 BMesh 创建平面轮廓面
    me = bpy.data.meshes.new(name=name)
    bm = bmesh.new()
    verts = [bm.verts.new((x, 0.0, z)) for x, z in profile_xy]
    bm.faces.new(verts)
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    bm.to_mesh(me)
    bm.free()
    me.update()

    obj = bpy.data.objects.new(name, me)
    bpy.context.collection.objects.link(obj)

    # 用 Blender 原生 extrude 沿 +Y 挤出
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.mesh.extrude_region_move(
        TRANSFORM_OT_translate={"value": (0, depth, 0)}
    )
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.mesh.normals_make_consistent(inside=False)
    bpy.ops.object.mode_set(mode='OBJECT')

    print(f"  [DEBUG] {name}: {len(me.polygons)} faces, {len(me.vertices)} verts")
    return obj


def add_material(obj, name=None):
    if not obj.data.materials:
        mat_name = name or f"{obj.name}_Material"
        mat = bpy.data.materials.new(name=mat_name)
        mat.use_nodes = False
        mat.diffuse_color = (0.4, 0.6, 0.9, 1.0)
        obj.data.materials.append(mat)


def apply_boolean(obj, tool_obj, operation='DIFFERENCE', solver='FAST'):
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

    # 创建内腔实体
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
                                 top_offset_y=0, ring_height=0, ring_width=0,
                                 wall_thickness=0):
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

    if ring_height > 0 and ring_width > 0:
        step_outer_top_profile = generate_top_profile_xy(
            width, depth, corner_radius, segments)
        step_inner_profile = generate_top_profile_xy(
            width - 2 * ring_width, depth - 2 * ring_width,
            max(corner_radius - ring_width, 0.1), segments)

        inner_btm = [bm.verts.new((x, y, hh)) for x, y in step_inner_profile]
        outer_top = [bm.verts.new((x, y, hh + ring_height)) for x, y in step_outer_top_profile]
        inner_top = [bm.verts.new((x, y, hh + ring_height)) for x, y in step_inner_profile]

        for i in range(num_profile):
            ni = (i + 1) % num_profile
            bm.faces.new([top_verts[i], top_verts[ni], outer_top[ni], outer_top[i]])

        for i in range(num_profile):
            ni = (i + 1) % num_profile
            bm.faces.new([inner_btm[ni], inner_btm[i], inner_top[i], inner_top[ni]])

        for i in range(num_profile):
            ni = (i + 1) % num_profile
            bm.faces.new([outer_top[i], outer_top[ni], inner_top[ni], inner_top[i]])

        if wall_thickness > 0:
            top_face_profile = generate_top_profile_xy(
                width - 2 * wall_thickness - 0.3,
                depth - 2 * wall_thickness - 0.3,
                max(corner_radius - wall_thickness - 0.15, 0.1), segments)
            top_face_verts = [bm.verts.new((x, y, hh)) for x, y in top_face_profile]
            for i in range(num_profile):
                ni = (i + 1) % num_profile
                bm.faces.new([inner_btm[ni], inner_btm[i], top_face_verts[i], top_face_verts[ni]])
            top_center = bm.verts.new((0, 0, hh))
            for i in range(num_profile):
                ni = (i + 1) % num_profile
                bm.faces.new([top_center, top_face_verts[i], top_face_verts[ni]])
        else:
            top_center = bm.verts.new((0, 0, hh))
            for i in range(num_profile):
                ni = (i + 1) % num_profile
                bm.faces.new([top_center, inner_btm[i], inner_btm[ni]])
    else:
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


def generate_top_profile_xy(width, depth, corner_radius, segments):
    """生成顶部轮廓的XY坐标（与 create_rounded_box_filleted 一致）"""
    hw = width / 2.0
    hd = depth / 2.0
    profile = []
    for i in range(segments):
        angle = (math.pi / 2) * i / segments
        x = hw - corner_radius + corner_radius * math.cos(angle)
        y = hd - corner_radius + corner_radius * math.sin(angle)
        profile.append((x, y))
    for i in range(segments):
        t = i / segments
        x = hw - corner_radius - t * (width - 2 * corner_radius)
        y = hd
        profile.append((x, y))
    for i in range(segments):
        angle = math.pi / 2 + (math.pi / 2) * i / segments
        x = -hw + corner_radius + corner_radius * math.cos(angle)
        y = hd - corner_radius + corner_radius * math.sin(angle)
        profile.append((x, y))
    for i in range(segments):
        t = i / segments
        x = -hw
        y = hd - corner_radius - t * (depth - 2 * corner_radius)
        profile.append((x, y))
    for i in range(segments):
        angle = math.pi + (math.pi / 2) * i / segments
        x = -hw + corner_radius + corner_radius * math.cos(angle)
        y = -hd + corner_radius + corner_radius * math.sin(angle)
        profile.append((x, y))
    for i in range(segments):
        t = i / segments
        x = -hw + corner_radius + t * (width - 2 * corner_radius)
        y = -hd
        profile.append((x, y))
    for i in range(segments):
        angle = 3 * math.pi / 2 + (math.pi / 2) * i / segments
        x = hw - corner_radius + corner_radius * math.cos(angle)
        y = -hd + corner_radius + corner_radius * math.sin(angle)
        profile.append((x, y))
    for i in range(segments):
        t = i / segments
        x = hw
        y = -hd + corner_radius + t * (depth - 2 * corner_radius)
        profile.append((x, y))
    return profile


def create_step_ring_mesh(name, width, depth, corner_radius, ring_width,
                         ring_height, z_bottom, z_top, segments):
    outer_profile = generate_top_profile_xy(width, depth, corner_radius, segments)
    inner_profile = generate_top_profile_xy(
        width - 2 * ring_width, depth - 2 * ring_width,
        max(corner_radius - ring_width, 0.1), segments
    )

    me = bpy.data.meshes.new(name=name)
    bm = bmesh.new()

    outer_btm = [bm.verts.new((x, y, z_bottom)) for x, y in outer_profile]
    inner_btm = [bm.verts.new((x, y, z_bottom)) for x, y in inner_profile]
    outer_top = [bm.verts.new((x, y, z_top)) for x, y in outer_profile]
    inner_top = [bm.verts.new((x, y, z_top)) for x, y in inner_profile]

    num = len(outer_profile)
    for i in range(num):
        ni = (i + 1) % num
        bm.faces.new([outer_btm[i], outer_btm[ni], outer_top[ni], outer_top[i]])
    for i in range(num):
        ni = (i + 1) % num
        bm.faces.new([inner_btm[ni], inner_btm[i], inner_top[i], inner_top[ni]])

    bm.to_mesh(me)
    bm.free()
    me.update(calc_edges=True)
    for p in me.polygons:
        p.use_smooth = False
    obj = bpy.data.objects.new(name, me)
    bpy.context.collection.objects.link(obj)
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    print(f"  [DEBUG] {name}: {len(me.polygons)} faces, {len(me.vertices)} verts")
    return obj


def create_filleted_top_shell(name, width, depth, outer_height, top_thickness,
                               wall_thickness, corner_radius,
                               outer_fillet_radius, inner_fillet_radius,
                               location=(0, 0, 0), segments=24, step_height=1.5,
                               holes=None, top_offset_y=3, window=None,
                               outer_ring_height=0, outer_ring_width=0):
    """
    创建带圆倒角的中空顶壳
    create_rounded_box_filleted 构建从底部到顶部内收的余弦曲线侧壁，
    翻转 180° 使开口朝下、曲线侧壁从底全宽平滑过渡到顶内收面
    top_offset_y: 顶面相对底框的Y向偏移量
    window: (length, width) 顶面矩形窗口尺寸，None 则不开口
    outer_ring_height: 底面外侧环形台阶高度（mm），0 则不添加
    outer_ring_width: 底面外侧环形台阶宽度（mm），0 则不添加
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
        ring_height=outer_ring_height,
        ring_width=outer_ring_width,
        wall_thickness=wall_thickness,
    )
    bpy.context.view_layer.objects.active = outer
    outer.select_set(True)

    outer.rotation_euler = (math.pi, 0, 0)
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=False)
    outer.location = location

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
    inner_z = location[2] + outer_half_h - top_thickness - inner_height / 2.0 - 0.05
    inner.location = (location[0], location[1], inner_z)
    print(f"  Inner fillet radius: {actual_inner_r:.3f} mm")

    apply_boolean(outer, inner, operation='DIFFERENCE')
    bpy.data.objects.remove(inner, do_unlink=True)

    if window:
        # Normalize to list of (len, wid, off_x, off_y)
        if isinstance(window[0], (int, float)):
            windows = [window if len(window) == 4 else (*window, 0.0, 0.0)]
        else:
            windows = [w if len(w) == 4 else (*w, 0.0, 0.0) for w in window]

        top_wall_center_z = location[2] + outer_half_h - top_thickness / 2.0
        top_center_y = location[1] - top_offset_y
        cutter_depth = top_thickness + 4.0

        for i, w in enumerate(windows):
            win_len, win_wid, win_off_x, win_off_y = w
            bpy.ops.mesh.primitive_cube_add(
                size=1.0,
                location=(location[0] + win_off_x, top_center_y + win_off_y, top_wall_center_z),
            )
            cutter = bpy.context.active_object
            cutter.name = f"{name}_WindowCutter_{i}"
            cutter.dimensions = (win_len, win_wid, cutter_depth)
            bpy.ops.object.transform_apply(scale=True)

            apply_boolean(outer, cutter, operation='DIFFERENCE')
            bpy.data.objects.remove(cutter, do_unlink=True)

    outer.name = name

    if outer_ring_height > 0 and outer_ring_width > 0:
        outer['step_ring_height'] = outer_ring_height
        outer['step_ring_width'] = outer_ring_width

    outer['wall_thickness'] = wall_thickness

    if window:
        if isinstance(window[0], (int, float)):
            windows = [window if len(window) == 4 else (*window, 0.0, 0.0)]
        else:
            windows = [w if len(w) == 4 else (*w, 0.0, 0.0) for w in window]
        entries = []
        for w in windows:
            win_len, win_wid, win_off_x, win_off_y = w
            dx = win_off_x
            dy = win_off_y - top_offset_y
            entries.append(f"{dx:.3f},{dy:.3f},{win_len:.3f},{win_wid:.3f}")
        outer['window_data'] = ";".join(entries)

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
        outer_ring_height=1.0,
        outer_ring_width=1.0,
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
        window=[
            (window_length, window_width, 20.0, 20.0),
            (15.0, 8.0, -25.0, 0.0),
            (14.0, 10.0, 0.0, -15.0),
        ],
        outer_ring_height=1.0,
        outer_ring_width=1.0,
    )
    add_material(shell_with_holes, name="TopShellWithHolesMaterial")
    print(f"  [OK] Top shell (with window) created")

    # 后壁通孔（4°圆锥，外侧细内侧粗）
    hole_radius_outer = 2.0 * 2.0 / 3.0  # ≈1.333 mm，外侧半径
    taper_angle = 4.0  # 锥度角度
    hole_y = depth / 2.0  # 孔在后壁位置

    # 计算内侧半径（外侧 + 壁厚 * tan(锥度角)）
    hole_radius_inner = hole_radius_outer + wall_thickness * math.tan(math.radians(taper_angle))

    # 孔位置：世界坐标
    shell_loc = shell_with_holes.location
    hole_cx = shell_loc.x + 26.0  # 世界 X
    hole_cz = shell_loc.z - 2.0   # 世界 Z（壳中心Z=0, 减2得-2）

    print(f"  [DEBUG] Tapered hole: outer_r={hole_radius_outer:.3f}, inner_r={hole_radius_inner:.3f}, taper={taper_angle}°")

    # 用圆锥体切通孔（外侧细，内侧粗）
    cyl_depth = wall_thickness + 10.0  # 增加长度确保完全穿透
    bpy.ops.mesh.primitive_cone_add(
        vertices=128,
        radius1=hole_radius_inner,  # 大端（内侧）
        radius2=hole_radius_outer,  # 小端（外侧）
        depth=cyl_depth,
        location=(hole_cx, hole_y - wall_thickness / 2.0, hole_cz),
    )
    cone_cutter = bpy.context.active_object
    cone_cutter.name = "Hole_ConeCutter"
    cone_cutter.rotation_euler = (math.pi / 2, 0, 0)

    pre_faces = len(shell_with_holes.data.polygons)
    apply_boolean(shell_with_holes, cone_cutter, operation='DIFFERENCE')
    bpy.data.objects.remove(cone_cutter, do_unlink=True)
    post_faces = len(shell_with_holes.data.polygons)
    print(f"  [OK] Tapered hole cut: {hole_radius_outer*2:.1f}mm -> {hole_radius_inner*2:.1f}mm, faces {pre_faces} -> {post_faces}")

    # 强制更新依赖图，确保导出器能获取到最新的网格数据
    bpy.context.view_layer.update()

    # 清理孔边缘的多余几何（仅融合重复顶点）
    bpy.context.view_layer.objects.active = shell_with_holes
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.mesh.remove_doubles(threshold=0.05)
    bpy.ops.object.mode_set(mode='OBJECT')

    hole_fillet_radius = 0.3  # 通孔圆倒角半径（仅在 STEP 导出中生效）
    print(f"  [DEBUG] Hole world: ({hole_cx:.1f}, {hole_y:.1f}, {hole_cz:.1f})")

    # 标记对象包含通孔，让 STEP 导出器使用参数化导出 + 圆孔切割（含圆倒角）
    # window_data 格式: cx,cy,cz,radius,1[,fillet_radius] (type=1 表示圆孔)
    hole_relative_cx = hole_cx - shell_loc.x  # 26.0
    hole_relative_cy = depth / 2.0  # 后壁
    hole_relative_cz = hole_cz - shell_loc.z  # -2.0
    hole_data = f"{hole_relative_cx:.3f},{hole_relative_cy:.3f},{hole_relative_cz:.3f},{hole_radius_outer:.3f},1,{hole_fillet_radius:.3f}"
    shell_with_holes["hole_fillet_radius"] = hole_fillet_radius  # 单独属性，方便在Blender中修改
    existing_wd = shell_with_holes.get("window_data", "")
    if existing_wd:
        shell_with_holes["window_data"] = existing_wd + ";" + hole_data
    else:
        shell_with_holes["window_data"] = hole_data

    # 后壁左侧圆角矩形通孔
    rect_hole_w = 12.0     # 宽度 (X)
    rect_hole_h = 4.0      # 高度 (Z)
    rect_hole_cr = 1.5     # 圆角半径
    rect_hole_cx = shell_loc.x - 24.0  # 左侧，与圆形孔对称（向中间移动2mm）
    rect_hole_cz = shell_loc.z - 2.0   # 壳中心往下2mm

    rect_depth = wall_thickness + 20.0  # 确保穿透（加长）

    # 创建立方体 cutter，只对 Y 方向 4 条棱倒角形成圆角矩形截面
    bpy.ops.mesh.primitive_cube_add(
        size=1.0,
        location=(rect_hole_cx, hole_y - wall_thickness / 2.0, rect_hole_cz),
    )
    rect_cutter = bpy.context.active_object
    rect_cutter.name = "RectHole_Cutter"
    # scale 为全尺寸（不是半尺寸，因为 size=1 的立方体半长为 0.5）
    rect_cutter.scale = (rect_hole_w, rect_depth, rect_hole_h)
    bpy.ops.object.transform_apply(scale=True)

    # 只对 Y 轴方向的 4 条棱倒角（形成 XZ 平面内的圆角矩形截面）
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='DESELECT')
    bpy.ops.mesh.select_mode(type='EDGE')
    bm = bmesh.from_edit_mesh(rect_cutter.data)
    bm.edges.ensure_lookup_table()
    for e in bm.edges:
        v0, v1 = e.verts
        delta = v1.co - v0.co
        # Y 方向棱：Y 分量主导，X/Z 分量接近 0
        if abs(delta.y) > abs(delta.x) and abs(delta.y) > abs(delta.z):
            e.select = True
    bmesh.update_edit_mesh(rect_cutter.data)
    bpy.ops.mesh.bevel(
        offset=rect_hole_cr,
        offset_type='OFFSET',
        segments=6,
        profile=0.5,
        affect='EDGES',
        clamp_overlap=False,
    )
    bpy.ops.object.mode_set(mode='OBJECT')

    pre_faces = len(shell_with_holes.data.polygons)
    apply_boolean(shell_with_holes, rect_cutter, operation='DIFFERENCE', solver='EXACT')
    bpy.data.objects.remove(rect_cutter, do_unlink=True)
    post_faces = len(shell_with_holes.data.polygons)
    print(f"  [OK] Rounded rect hole: {rect_hole_w:.0f}x{rect_hole_h:.0f}mm (r={rect_hole_cr:.1f}), faces {pre_faces} -> {post_faces}")

    # 标记圆角矩形孔到 window_data（供 STEP 参数化导出）
    # 格式: cx,cy,cz,width,height,2,corner_radius[,fillet_radius] (type=2 表示圆角矩形孔)
    rect_hole_relative_cx = rect_hole_cx - shell_loc.x  # -24.0
    rect_hole_relative_cy = depth / 2.0  # 后壁
    rect_hole_relative_cz = rect_hole_cz - shell_loc.z  # -2.0
    rect_hole_fillet_radius = 0.3  # 圆角矩形孔圆倒角半径（仅在 STEP 导出中生效，设为 0 则不加倒角）
    rect_hole_data = f"{rect_hole_relative_cx:.3f},{rect_hole_relative_cy:.3f},{rect_hole_relative_cz:.3f},{rect_hole_w:.3f},{rect_hole_h:.3f},2,{rect_hole_cr:.3f},{rect_hole_fillet_radius:.3f}"
    existing_wd = shell_with_holes.get("window_data", "")
    if existing_wd:
        shell_with_holes["window_data"] = existing_wd + ";" + rect_hole_data
    else:
        shell_with_holes["window_data"] = rect_hole_data

    # 清理孔边缘
    bpy.context.view_layer.objects.active = shell_with_holes
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.mesh.remove_doubles(threshold=0.05)
    bpy.ops.object.mode_set(mode='OBJECT')

    # 清理
    bpy.context.view_layer.objects.active = shell_with_holes
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.mesh.delete_loose()
    bpy.ops.mesh.normals_make_consistent(inside=False)
    bpy.ops.object.mode_set(mode='OBJECT')

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