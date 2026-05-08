#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
塑料底壳生成器
使用Mesh创建塑料底壳，导出时美化为解析曲面

结构组成：
1. 外盒体 - 带圆角的矩形盒
2. 内腔体 - 挖空形成托盘
3. 螺丝孔 x4（在底板表面）

使用方法：
1. 在Blender中打开Scripting工作区
2. 打开此脚本
3. 点击运行按钮
"""

import bpy
import bmesh
import math


def clear_scene():
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)

    for data_block in list(bpy.data.meshes):
        if data_block.users == 0:
            bpy.data.meshes.remove(data_block)


def apply_boolean(obj, tool_obj, operation='DIFFERENCE'):
    mod = obj.modifiers.new(name="Boolean", type='BOOLEAN')
    mod.operation = operation
    mod.object = tool_obj
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.modifier_apply(modifier=mod.name)


def add_material(obj, name=None):
    if not obj.data.materials:
        mat_name = name or f"{obj.name}_Material"
        mat = bpy.data.materials.new(name=mat_name)
        mat.use_nodes = False
        mat.diffuse_color = (0.4, 0.6, 0.9, 1.0)
        obj.data.materials.append(mat)


def create_rounded_box(name, width, depth, height, corner_radius, segments=32):
    """创建一个带有圆角的立方体，从顶视图看四个角是圆角
    使用 BMesh 手动创建干净的圆角矩形"""
    import math
    
    hw = width / 2.0
    hd = depth / 2.0
    hh = height / 2.0
    
    # 确保圆角半径不超过最小尺寸的一半
    max_radius = min(hw, hd) * 0.99
    corner_radius = min(corner_radius, max_radius)
    
    # 计算圆角矩形的轮廓点
    top_profile = []
    bottom_profile = []
    
    # 右上角圆角：圆心 (hw - corner_radius, hd - corner_radius)
    for i in range(segments):
        angle = (math.pi/2) * i / segments
        x = hw - corner_radius + corner_radius * math.cos(angle)
        y = hd - corner_radius + corner_radius * math.sin(angle)
        top_profile.append((x, y, hh))
        bottom_profile.append((x, y, -hh))
    
    # 上边直边
    for i in range(segments):
        t = i / segments
        x = hw - corner_radius - t * (width - 2 * corner_radius)
        y = hd
        top_profile.append((x, y, hh))
        bottom_profile.append((x, y, -hh))
    
    # 左上角圆角
    for i in range(segments):
        angle = math.pi/2 + (math.pi/2) * i / segments
        x = -hw + corner_radius + corner_radius * math.cos(angle)
        y = hd - corner_radius + corner_radius * math.sin(angle)
        top_profile.append((x, y, hh))
        bottom_profile.append((x, y, -hh))
    
    # 左边直边
    for i in range(segments):
        t = i / segments
        x = -hw
        y = hd - corner_radius - t * (depth - 2 * corner_radius)
        top_profile.append((x, y, hh))
        bottom_profile.append((x, y, -hh))
    
    # 左下角圆角
    for i in range(segments):
        angle = math.pi + (math.pi/2) * i / segments
        x = -hw + corner_radius + corner_radius * math.cos(angle)
        y = -hd + corner_radius + corner_radius * math.sin(angle)
        top_profile.append((x, y, hh))
        bottom_profile.append((x, y, -hh))
    
    # 下边直边
    for i in range(segments):
        t = i / segments
        x = -hw + corner_radius + t * (width - 2 * corner_radius)
        y = -hd
        top_profile.append((x, y, hh))
        bottom_profile.append((x, y, -hh))
    
    # 右下角圆角
    for i in range(segments):
        angle = 3*math.pi/2 + (math.pi/2) * i / segments
        x = hw - corner_radius + corner_radius * math.cos(angle)
        y = -hd + corner_radius + corner_radius * math.sin(angle)
        top_profile.append((x, y, hh))
        bottom_profile.append((x, y, -hh))
    
    # 右边直边
    for i in range(segments):
        t = i / segments
        x = hw
        y = -hd + corner_radius + t * (depth - 2 * corner_radius)
        top_profile.append((x, y, hh))
        bottom_profile.append((x, y, -hh))
    
    # 创建网格
    me = bpy.data.meshes.new(name=name)
    bm = bmesh.new()
    
    # 添加顶点
    top_verts = [bm.verts.new(v) for v in top_profile]
    bottom_verts = [bm.verts.new(v) for v in bottom_profile]
    
    # 创建侧面
    num_profile = len(top_profile)
    for i in range(num_profile):
        next_i = (i + 1) % num_profile
        face = [top_verts[i], top_verts[next_i], bottom_verts[next_i], bottom_verts[i]]
        bm.faces.new(face)
    
    # 创建顶面和底面
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
    
    # 应用平滑着色
    bpy.ops.object.shade_smooth()
    
    print(f"  Created rounded box with {len(obj.data.vertices)} vertices and {len(obj.data.edges)} edges")
    
    return obj


def create_bottom_shell(
    name="BottomShell",
    location=(0, 0, 0),
):
    print(f"\n{'='*60}")
    print(f"Creating bottom shell: {name}")
    print(f"  Creating single rounded box")

    width = 100.0
    depth = 70.0
    height = 10.0
    corner_r = 20.0
    
    # 使用 create_rounded_box 创建单个圆角矩形盒
    obj = create_rounded_box(
        name=name,
        width=width,
        depth=depth,
        height=height,
        corner_radius=corner_r,
        segments=32
    )
    obj.location = (location[0], location[1], location[2])
    add_material(obj)
    
    print(f"  [OK] Rounded box created: {width} x {depth} x {height} mm, corner radius={corner_r} mm")

    print(f"\n  [DONE] Bottom shell '{name}' created successfully!")
    print(f"{'='*60}\n")

    return [obj]


def create_bottom_shell_scene():
    print("\n" + "="*60)
    print("Plastic Bottom Shell Generator")
    print("="*60)

    print("[1/2] Clearing scene...")
    clear_scene()

    print("[2/2] Creating bottom shell...")
    shell = create_bottom_shell(
        name="BottomShell",
        location=(0, 0, 0),
    )

    for area in bpy.context.screen.areas:
        if area.type == 'VIEW_3D':
            for space in area.spaces:
                if space.type == 'VIEW_3D':
                    space.shading.type = 'SOLID'
                    space.overlay.show_wireframes = False

    print("\n" + "="*60)
    print("[OK] Bottom shell scene created!")
    print("="*60)
    print("\nNext: File -> Export -> STEP (Enhanced)")


if __name__ == "__main__":
    try:
        create_bottom_shell_scene()
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()
