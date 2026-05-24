#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
机械设计物体生成器 v4.0 - Mesh版本
使用Mesh创建圆柱体，导出时美化为曲线型圆柱体

核心策略：
1. 使用Blender的Mesh API创建圆柱体
2. 通过STEP导出器将Mesh美化为曲线型圆柱体
3. 确保在FreeCAD中显示为完美解析曲面

使用方法：
1. 在Blender中打开Scripting工作区
2. 打开此脚本
3. 点击运行按钮
4. File → Export → STEP (Enhanced)
5. 在FreeCAD中打开，物体应显示为完美解析曲面

作者: Blender STEP Exporter Team
"""

import bpy
import math
import os


def clear_scene():
    """清除场景中的所有对象"""
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)
    
    # 清理孤立数据块
    for data_block in list(bpy.data.meshes):
        if data_block.users == 0:
            bpy.data.meshes.remove(data_block)
    for data_block in list(bpy.data.curves):
        if data_block.users == 0:
            bpy.data.curves.remove(data_block)


def create_mesh_cylinder(name, center, radius, height, segments=32):
    """
    使用Mesh API创建圆柱体
    
    Args:
        name: 圆柱体名称
        center: 圆柱体中心位置 (x, y, z)
        radius: 圆柱体半径
        height: 圆柱体高度
        segments: 圆柱体圆周方向的分段数
    
    Returns:
        圆柱体网格对象
    """
    # 创建网格圆柱体
    bpy.ops.mesh.primitive_cylinder_add(
        radius=radius,
        depth=height,
        location=center,
        vertices=segments
    )
    
    # 获取创建的对象
    obj = bpy.context.active_object
    obj.name = name
    
    # 调整显示设置
    obj.display_type = 'SOLID'  # 对象显示为实心
    obj.show_wire = False  # 不显示线框
    obj.show_all_edges = False  # 不显示所有边缘
    
    # 确保圆柱体有材质，这样在实心视图中会显示为实体
    if not obj.data.materials:
        # 创建一个默认材质
        mat = bpy.data.materials.new(name=f"{obj.name}_Material")
        mat.use_nodes = True
        # 设置一个简单的漫反射材质
        principled = mat.node_tree.nodes.get('Principled BSDF')
        if principled:
            principled.inputs['Base Color'].default_value = (0.8, 0.8, 0.8, 1.0)  # 灰色
        obj.data.materials.append(mat)
    
    # 调整Blender视图设置，确保在实体视图中显示
    # 获取当前视图
    for area in bpy.context.screen.areas:
        if area.type == 'VIEW_3D':
            for space in area.spaces:
                if space.type == 'VIEW_3D':
                    # 设置为实体视图
                    space.shading.type = 'SOLID'
                    # 禁用线框显示
                    space.overlay.show_wireframes = False
    
    # 强制更新对象
    obj.update_tag()
    bpy.context.view_layer.update()
    
    return obj


def create_tapered_mesh_cylinder(name, center, bottom_radius, top_radius, height, segments=32):
    """
    使用Mesh API创建带斜率的圆柱体
    
    Args:
        name: 圆柱体名称
        center: 圆柱体中心位置 (x, y, z)
        bottom_radius: 底部半径
        top_radius: 顶部半径
        height: 圆柱体高度
        segments: 圆柱体圆周方向的分段数
    
    Returns:
        带斜率的圆柱体网格对象
    """
    # 创建网格圆柱体
    bpy.ops.mesh.primitive_cylinder_add(
        radius=bottom_radius,
        depth=height,
        location=center,
        vertices=segments
    )
    
    # 获取创建的对象
    obj = bpy.context.active_object
    obj.name = name
    
    # 进入编辑模式
    bpy.ops.object.mode_set(mode='EDIT')
    
    # 选择顶部面
    bpy.ops.mesh.select_all(action='DESELECT')
    bpy.ops.object.mode_set(mode='OBJECT')
    
    # 选择顶部顶点
    for vertex in obj.data.vertices:
        if abs(vertex.co.z - height/2) < 0.001:
            vertex.select = True
    
    # 进入编辑模式
    bpy.ops.object.mode_set(mode='EDIT')
    
    # 缩放顶部面
    scale_factor = top_radius / bottom_radius
    bpy.ops.transform.resize(value=(scale_factor, scale_factor, 1.0))
    
    # 退出编辑模式
    bpy.ops.object.mode_set(mode='OBJECT')
    
    # 调整显示设置
    obj.display_type = 'SOLID'  # 对象显示为实心
    obj.show_wire = False  # 不显示线框
    obj.show_all_edges = False  # 不显示所有边缘
    
    # 确保圆柱体有材质，这样在实心视图中会显示为实体
    if not obj.data.materials:
        # 创建一个默认材质
        mat = bpy.data.materials.new(name=f"{obj.name}_Material")
        mat.use_nodes = True
        # 设置一个简单的漫反射材质
        principled = mat.node_tree.nodes.get('Principled BSDF')
        if principled:
            principled.inputs['Base Color'].default_value = (0.8, 0.8, 0.8, 1.0)  # 灰色
        obj.data.materials.append(mat)
    
    # 调整Blender视图设置，确保在实体视图中显示
    # 获取当前视图
    for area in bpy.context.screen.areas:
        if area.type == 'VIEW_3D':
            for space in area.spaces:
                if space.type == 'VIEW_3D':
                    # 设置为实体视图
                    space.shading.type = 'SOLID'
                    # 禁用线框显示
                    space.overlay.show_wireframes = False
    
    # 强制更新对象
    obj.update_tag()
    bpy.context.view_layer.update()
    
    return obj


def create_chamfered_cylinder(name, center, radius, height, chamfer_size, segments=64):
    """
    创建顶部带45°倒角的圆柱体
    
    Args:
        name: 圆柱体名称
        center: 圆柱体中心位置 (x, y, z)
        radius: 圆柱体半径
        height: 圆柱体高度
        chamfer_size: 倒角尺寸（径向减少量）
        segments: 圆周分段数
    
    Returns:
        带倒角的圆柱体网格对象
    """
    try:
        # 创建基础圆柱体
        bpy.ops.mesh.primitive_cylinder_add(
            radius=radius,
            depth=height,
            location=[0, 0, 0],
            vertices=segments
        )
        
        obj = bpy.context.active_object
        obj.name = name
        
        # 进入编辑模式
        bpy.ops.object.mode_set(mode='EDIT')
        
        # 选择顶部边
        bpy.ops.mesh.select_all(action='DESELECT')
        bpy.ops.object.mode_set(mode='OBJECT')
        
        # 选择顶部的边
        for edge in obj.data.edges:
            v1 = obj.data.vertices[edge.vertices[0]]
            v2 = obj.data.vertices[edge.vertices[1]]
            if abs(v1.co.z - height/2) < 0.001 and abs(v2.co.z - height/2) < 0.001:
                edge.select = True
        
        bpy.ops.object.mode_set(mode='EDIT')
        
        # 使用倒角工具创建45°倒角
        bpy.ops.mesh.bevel(offset=chamfer_size, segments=1, profile=1.0, clamp_overlap=True)
        
        # 退出编辑模式
        bpy.ops.object.mode_set(mode='OBJECT')
        
        # 移动到指定位置
        obj.location = center
        
        # 添加材质
        if not obj.data.materials:
            mat = bpy.data.materials.new(name=f"{obj.name}_Material")
            mat.use_nodes = True
            principled = mat.node_tree.nodes.get('Principled BSDF')
            if principled:
                principled.inputs['Base Color'].default_value = (0.8, 0.8, 0.8, 1.0)
            obj.data.materials.append(mat)
        
        obj.update_tag()
        bpy.context.view_layer.update()
        
        return obj
    except Exception as e:
        print(f"创建倒角圆柱失败: {e}")
        import traceback
        traceback.print_exc()
        return None


def create_fillet_cylinder(name, center, radius, height, fillet_radius, segments=64):
    """
    创建顶部带圆角的圆柱体（使用 Bevel 修改器创建标准圆角）
    
    Args:
        name: 圆柱体名称
        center: 圆柱体中心位置 (x, y, z)
        radius: 圆柱体半径
        height: 圆柱体高度
        fillet_radius: 圆角半径
        segments: 圆周分段数
    
    Returns:
        带圆角的圆柱体网格对象
    """
    import math
    
    try:
        # 创建基础圆柱体
        bpy.ops.mesh.primitive_cylinder_add(
            radius=radius,
            depth=height,
            location=[0, 0, 0],
            vertices=segments
        )
        
        obj = bpy.context.active_object
        obj.name = name
        
        # 进入编辑模式，选择顶部的边
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.select_all(action='DESELECT')
        
        # 选择顶部的边
        bpy.ops.object.mode_set(mode='OBJECT')
        for edge in obj.data.edges:
            v1 = obj.data.vertices[edge.vertices[0]]
            v2 = obj.data.vertices[edge.vertices[1]]
            # 选择顶部边缘（Z 坐标接近 height/2）
            if abs(v1.co.z - height/2) < 0.001 and abs(v2.co.z - height/2) < 0.001:
                edge.select = True
        
        bpy.ops.object.mode_set(mode='EDIT')
        
        # 使用 Bevel 操作符创建圆角（只影响选中的边）
        # 使用 OFFSET 类型，profile=0.5 创建圆形圆角
        # 注意：解析器会自动应用 1.88 的补偿系数
        bpy.ops.mesh.bevel(
            offset_type='OFFSET',  # 使用边偏移
            offset=fillet_radius,  # 圆角半径（解析器会补偿）
            segments=36,  # 圆角分段数
            profile=0.5,  # 0.5 创建圆形圆角
            clamp_overlap=False,
            affect='EDGES'  # 只影响边
        )
        
        # 退出编辑模式
        bpy.ops.object.mode_set(mode='OBJECT')
        
        # 移动到指定位置
        obj.location = center
        
        # 添加材质
        if not obj.data.materials:
            mat = bpy.data.materials.new(name=f"{obj.name}_Material")
            mat.use_nodes = True
            principled = mat.node_tree.nodes.get('Principled BSDF')
            if principled:
                principled.inputs['Base Color'].default_value = (0.8, 0.8, 0.8, 1.0)
            obj.data.materials.append(mat)
        
        obj.update_tag()
        bpy.context.view_layer.update()
        
        return obj
    except Exception as e:
        print(f"创建圆角圆柱失败：{e}")
        import traceback
        traceback.print_exc()
        return None


def create_tapered_cylinder_with_fillet_and_chamfer(name, center, bottom_radius, top_radius, height, fillet_radius, chamfer_size, segments=64):
    """
    创建带斜率、顶部圆角和底部倒角的圆柱体
    
    Args:
        name: 圆柱体名称
        center: 圆柱体中心位置 (x, y, z)
        bottom_radius: 底部半径
        top_radius: 顶部半径
        height: 圆柱体高度
        fillet_radius: 顶部圆角半径
        chamfer_size: 底部倒角尺寸
        segments: 圆周分段数
    
    Returns:
        带斜率、圆角和倒角的圆柱体网格对象
    """
    import math
    
    try:
        # 1. 创建基础圆柱体（在原点）
        bpy.ops.mesh.primitive_cylinder_add(
            radius=bottom_radius,
            depth=height,
            location=[0, 0, 0],
            vertices=segments
        )
        
        obj = bpy.context.active_object
        obj.name = name
        
        # 2. 进入编辑模式，缩放顶部面创建斜率
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.select_all(action='DESELECT')
        bpy.ops.object.mode_set(mode='OBJECT')
        
        # 选择顶部顶点
        for vertex in obj.data.vertices:
            if abs(vertex.co.z - height/2) < 0.001:
                vertex.select = True
        
        bpy.ops.object.mode_set(mode='EDIT')
        
        # 缩放顶部面
        scale_factor = top_radius / bottom_radius
        bpy.ops.transform.resize(value=(scale_factor, scale_factor, 1.0))
        
        # 3. 选择顶部边，创建圆角
        bpy.ops.mesh.select_all(action='DESELECT')
        bpy.ops.object.mode_set(mode='OBJECT')
        
        # 选择顶部边缘
        for edge in obj.data.edges:
            v1 = obj.data.vertices[edge.vertices[0]]
            v2 = obj.data.vertices[edge.vertices[1]]
            if abs(v1.co.z - height/2) < 0.001 and abs(v2.co.z - height/2) < 0.001:
                edge.select = True
        
        bpy.ops.object.mode_set(mode='EDIT')
        
        # 使用 Bevel 创建顶部圆角
        bpy.ops.mesh.bevel(
            offset_type='OFFSET',
            offset=fillet_radius,
            segments=36,
            profile=0.5,
            clamp_overlap=False,
            affect='EDGES'
        )
        
        # 4. 选择底部边，创建倒角
        bpy.ops.mesh.select_all(action='DESELECT')
        bpy.ops.object.mode_set(mode='OBJECT')
        
        # 选择底部边缘
        for edge in obj.data.edges:
            v1 = obj.data.vertices[edge.vertices[0]]
            v2 = obj.data.vertices[edge.vertices[1]]
            if abs(v1.co.z + height/2) < 0.001 and abs(v2.co.z + height/2) < 0.001:
                edge.select = True
        
        bpy.ops.object.mode_set(mode='EDIT')
        
        # 使用 Bevel 创建底部倒角（45°）
        bpy.ops.mesh.bevel(
            offset=chamfer_size,
            segments=1,
            profile=1.0,
            clamp_overlap=True,
            affect='EDGES'
        )
        
        # 退出编辑模式
        bpy.ops.object.mode_set(mode='OBJECT')
        
        # 移动到指定位置
        obj.location = center
        
        # 添加材质
        if not obj.data.materials:
            mat = bpy.data.materials.new(name=f"{obj.name}_Material")
            mat.use_nodes = True
            principled = mat.node_tree.nodes.get('Principled BSDF')
            if principled:
                principled.inputs['Base Color'].default_value = (0.8, 0.8, 0.8, 1.0)
            obj.data.materials.append(mat)
        
        obj.update_tag()
        bpy.context.view_layer.update()
        
        return obj
    except Exception as e:
        print(f"创建带圆角和倒角的斜率圆柱失败：{e}")
        import traceback
        traceback.print_exc()
        return None


def create_tapered_hollow_cylinder(name, center, outer_bottom_radius, outer_top_radius, inner_bottom_radius, inner_top_radius, height, segments=64):
    """
    创建锥形螺柱（外柱面上小下大，内柱面上大下小）
    
    Args:
        name: 圆柱体名称
        center: 圆柱体中心位置 (x, y, z)
        outer_bottom_radius: 外柱底部半径
        outer_top_radius: 外柱顶部半径
        inner_bottom_radius: 内孔底部半径
        inner_top_radius: 内孔顶部半径
        height: 圆柱体高度
        segments: 圆周分段数
    
    Returns:
        锥形螺柱网格对象
    """
    import math
    
    try:
        # 1. 创建外锥形柱体（在原点）
        bpy.ops.mesh.primitive_cylinder_add(
            radius=outer_bottom_radius,
            depth=height,
            location=[0, 0, 0],
            vertices=segments
        )
        
        outer_obj = bpy.context.active_object
        outer_obj.name = f"{name}_outer"
        
        # 进入编辑模式，缩放顶部
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.select_all(action='DESELECT')
        bpy.ops.object.mode_set(mode='OBJECT')
        
        # 选择顶部顶点
        for vertex in outer_obj.data.vertices:
            if abs(vertex.co.z - height/2) < 0.001:
                vertex.select = True
        
        bpy.ops.object.mode_set(mode='EDIT')
        outer_scale = outer_top_radius / outer_bottom_radius
        bpy.ops.transform.resize(value=(outer_scale, outer_scale, 1.0))
        bpy.ops.object.mode_set(mode='OBJECT')
        
        # 2. 创建内锥形柱体（孔）
        bpy.ops.mesh.primitive_cylinder_add(
            radius=inner_bottom_radius,
            depth=height + 2,  # 稍微长一点，确保完全穿透
            location=[0, 0, 0],
            vertices=segments
        )
        
        inner_obj = bpy.context.active_object
        inner_obj.name = f"{name}_inner"
        
        # 进入编辑模式，缩放顶部
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.select_all(action='DESELECT')
        bpy.ops.object.mode_set(mode='OBJECT')
        
        # 选择顶部顶点
        for vertex in inner_obj.data.vertices:
            if abs(vertex.co.z - (height+2)/2) < 0.001:
                vertex.select = True
        
        bpy.ops.object.mode_set(mode='EDIT')
        inner_scale = inner_top_radius / inner_bottom_radius
        bpy.ops.transform.resize(value=(inner_scale, inner_scale, 1.0))
        bpy.ops.object.mode_set(mode='OBJECT')
        
        # 3. 使用布尔差集运算创建孔
        # 选择外圆柱体
        bpy.ops.object.select_all(action='DESELECT')
        outer_obj.select_set(True)
        bpy.context.view_layer.objects.active = outer_obj
        
        # 添加布尔修改器
        bool_mod = outer_obj.modifiers.new(name="Hole", type='BOOLEAN')
        bool_mod.operation = 'DIFFERENCE'
        bool_mod.object = inner_obj
        
        # 应用布尔修改器
        bpy.ops.object.modifier_apply(modifier=bool_mod.name)
        
        # 删除内圆柱体
        bpy.data.objects.remove(inner_obj, do_unlink=True)
        
        # 重命名外圆柱体
        outer_obj.name = name
        
        # 移动到指定位置
        outer_obj.location = center
        
        # 添加材质
        if not outer_obj.data.materials:
            mat = bpy.data.materials.new(name=f"{name}_Material")
            mat.use_nodes = True
            principled = mat.node_tree.nodes.get('Principled BSDF')
            if principled:
                principled.inputs['Base Color'].default_value = (0.8, 0.8, 0.8, 1.0)
            outer_obj.data.materials.append(mat)
        
        outer_obj.update_tag()
        bpy.context.view_layer.update()
        
        return outer_obj
    except Exception as e:
        print(f"创建锥形螺柱失败：{e}")
        import traceback
        traceback.print_exc()
        return None


def create_hollow_cylinder(name, center, outer_radius, inner_radius, height, segments=64):
    """
    创建带中心孔的圆柱体（螺孔圆柱）
    
    Args:
        name: 圆柱体名称
        center: 圆柱体中心位置 (x, y, z)
        outer_radius: 外半径
        inner_radius: 内半径（孔的半径）
        height: 圆柱体高度
        segments: 圆周分段数
    
    Returns:
        带孔的圆柱体网格对象
    """
    import math
    
    try:
        # 1. 创建外圆柱体（在原点）
        bpy.ops.mesh.primitive_cylinder_add(
            radius=outer_radius,
            depth=height,
            location=[0, 0, 0],
            vertices=segments
        )
        
        outer_obj = bpy.context.active_object
        outer_obj.name = f"{name}_outer"
        
        # 2. 创建内圆柱体（孔）
        bpy.ops.mesh.primitive_cylinder_add(
            radius=inner_radius,
            depth=height + 2,  # 稍微长一点，确保完全穿透
            location=[0, 0, 0],
            vertices=segments
        )
        
        inner_obj = bpy.context.active_object
        inner_obj.name = f"{name}_inner"
        
        # 3. 使用布尔差集运算创建孔
        # 选择外圆柱体
        bpy.ops.object.select_all(action='DESELECT')
        outer_obj.select_set(True)
        bpy.context.view_layer.objects.active = outer_obj
        
        # 添加布尔修改器
        bool_mod = outer_obj.modifiers.new(name="Hole", type='BOOLEAN')
        bool_mod.operation = 'DIFFERENCE'
        bool_mod.object = inner_obj
        
        # 应用布尔修改器
        bpy.ops.object.modifier_apply(modifier=bool_mod.name)
        
        # 删除内圆柱体
        bpy.data.objects.remove(inner_obj, do_unlink=True)
        
        # 重命名外圆柱体
        outer_obj.name = name
        
        # 移动到指定位置
        outer_obj.location = center
        
        # 添加材质
        if not outer_obj.data.materials:
            mat = bpy.data.materials.new(name=f"{name}_Material")
            mat.use_nodes = True
            principled = mat.node_tree.nodes.get('Principled BSDF')
            if principled:
                principled.inputs['Base Color'].default_value = (0.8, 0.8, 0.8, 1.0)
            outer_obj.data.materials.append(mat)
        
        outer_obj.update_tag()
        bpy.context.view_layer.update()
        
        return outer_obj
    except Exception as e:
        print(f"创建螺孔圆柱失败：{e}")
        import traceback
        traceback.print_exc()
        return None


def create_tapered_stepped_hole_cylinder(name, center, bottom_radius, top_radius,
                                          small_hole_radius, small_hole_height,
                                          large_hole_radius, height, segments=64):
    """
    创建带台阶内孔的锥形圆柱体

    台阶内孔结构：
        TOP
    ┌────────────┐  ← small hole (small_hole_radius, height=small_hole_height)
    │  ┌──────┐  │
    │  │      │  │
    │  │      │  │
    │  └──────┘  │  ← step transition
    │  ┌────────┐│
    │  │        ││  ← large hole (large_hole_radius, remaining height)
    │  │        ││
    │  └────────┘│
    └────────────┘
        BOTTOM

    Args:
        name: 物体名称
        center: 中心位置 (x, y, z)
        bottom_radius: 外锥底部半径
        top_radius: 外锥顶部半径
        small_hole_radius: 顶部小孔半径
        small_hole_height: 顶部小孔高度 (mm)
        large_hole_radius: 其余大孔半径
        height: 总高度
        segments: 圆周分段数

    Returns:
        带台阶内孔的锥形圆柱体网格对象
    """
    import math

    try:
        # 1. 创建外锥形圆柱体
        bpy.ops.mesh.primitive_cylinder_add(
            radius=bottom_radius,
            depth=height,
            location=[0, 0, 0],
            vertices=segments
        )
        outer_obj = bpy.context.active_object
        outer_obj.name = f"{name}_outer"

        # 缩放顶部面形成锥形
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.select_all(action='DESELECT')
        bpy.ops.object.mode_set(mode='OBJECT')
        for vertex in outer_obj.data.vertices:
            if abs(vertex.co.z - height / 2) < 0.001:
                vertex.select = True
        bpy.ops.object.mode_set(mode='EDIT')
        scale_factor = top_radius / bottom_radius
        bpy.ops.transform.resize(value=(scale_factor, scale_factor, 1.0))
        bpy.ops.object.mode_set(mode='OBJECT')

        # 2. 创建台阶内孔切割工具（均以原点为中心，确保同心）
        # 大孔：2°锥形圆柱（与外锥平行），底部r由台阶处large_hole_radius按2°外推
        # 小孔：直圆柱，r=small_hole_radius
        # 微量偏移避免两个切割体在台阶处共面导致布尔运算失败
        large_hole_h = height - small_hole_height
        inner_bottom_r = large_hole_radius + large_hole_h * math.tan(math.radians(2))
        offset = 0.01
        bottom_z = -(height / 2) - 1
        top_z = -(height / 2) + large_hole_h + offset  # 延伸到台阶上0.01mm
        depth_val = top_z - bottom_z
        loc_z = (bottom_z + top_z) / 2
        bpy.ops.mesh.primitive_cylinder_add(
            radius=inner_bottom_r,
            depth=depth_val,
            location=[0, 0, loc_z],
            vertices=segments
        )
        large_hole_obj = bpy.context.active_object
        large_hole_obj.name = f"{name}_large_hole"

        # 缩放顶部面形成内锥形（2°锥度，与外锥平行，台阶处半径=large_hole_radius）
        local_top_z = depth_val / 2
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.select_all(action='DESELECT')
        bpy.ops.object.mode_set(mode='OBJECT')
        for vertex in large_hole_obj.data.vertices:
            if abs(vertex.co.z - local_top_z) < 0.001:
                vertex.select = True
        bpy.ops.object.mode_set(mode='EDIT')
        inner_scale = large_hole_radius / inner_bottom_r
        bpy.ops.transform.resize(value=(inner_scale, inner_scale, 1.0))
        bpy.ops.object.mode_set(mode='OBJECT')

        # 小孔：顶部通孔，从台阶下方延伸到顶部以上，半径 = small_hole_radius
        small_bottom_z = -(height / 2) + large_hole_h - offset  # 延伸到台阶下0.01mm
        small_depth = (height / 2) + 2 - small_bottom_z  # 向上多延伸确保切穿顶面
        small_loc_z = (small_bottom_z + (height / 2) + 2) / 2
        bpy.ops.mesh.primitive_cylinder_add(
            radius=small_hole_radius,
            depth=small_depth,
            location=[0, 0, small_loc_z],
            vertices=segments
        )
        small_hole_obj = bpy.context.active_object
        small_hole_obj.name = f"{name}_small_hole"

        # 3. 执行布尔差集（分两步，避免两个孔圆柱交叉导致闭合面）
        # 第一步：切除大孔
        bpy.ops.object.select_all(action='DESELECT')
        outer_obj.select_set(True)
        bpy.context.view_layer.objects.active = outer_obj
        bool_mod1 = outer_obj.modifiers.new(name="LargeHole", type='BOOLEAN')
        bool_mod1.operation = 'DIFFERENCE'
        bool_mod1.object = large_hole_obj
        bpy.ops.object.modifier_apply(modifier=bool_mod1.name)
        bpy.data.objects.remove(large_hole_obj, do_unlink=True)

        # 第二步：切除顶部小孔
        bool_mod2 = outer_obj.modifiers.new(name="SmallHole", type='BOOLEAN')
        bool_mod2.operation = 'DIFFERENCE'
        bool_mod2.object = small_hole_obj
        bpy.ops.object.modifier_apply(modifier=bool_mod2.name)
        bpy.data.objects.remove(small_hole_obj, do_unlink=True)

        # 重命名
        outer_obj.name = name

        # 移动到指定位置
        outer_obj.location = center

        # 添加材质
        if not outer_obj.data.materials:
            mat = bpy.data.materials.new(name=f"{name}_Material")
            mat.use_nodes = True
            principled = mat.node_tree.nodes.get('Principled BSDF')
            if principled:
                principled.inputs['Base Color'].default_value = (0.8, 0.8, 0.8, 1.0)
            outer_obj.data.materials.append(mat)

        outer_obj.update_tag()
        bpy.context.view_layer.update()

        return outer_obj

    except Exception as e:
        print(f"创建台阶内孔锥形圆柱失败：{e}")
        import traceback
        traceback.print_exc()
        return None


def create_trapezoid_prism_cutter(name, z_center, radius, groove_depth,
                                   bottom_width, top_width, extrusion_length):
    """
    创建一个横截面为等边梯形的长方体棱柱（用于布尔切割直槽凹槽）

    使用 Cube 基元 + 顶点变形，确保面法线正确。

    横截面（XZ 平面，沿 Y 轴挤出）：
    
         Z (height)
         ^
         |      top_width（凹槽底部，较窄）
         |      <-->
         |  P2----------P3     <- groove bottom (X = radius - groove_depth)
         |   \          /      <- 等边梯形斜边
         |    \        /
         |  P1----------P0     <- cylinder surface (X = radius + epsilon)
         |    <-------->
         |     bottom_width（圆柱表面，较宽）
         |
         +------------------> X (radial direction)

    Args:
        name: 棱柱名称
        z_center: 凹槽中心的 Z 坐标
        radius: 圆柱在凹槽位置的表面半径（X 坐标）
        groove_depth: 凹槽深度（径向切削量）
        bottom_width: 梯形在圆柱表面的宽度（较宽边，沿 Z 方向）
        top_width: 梯形在凹槽底部的宽度（较窄边，沿 Z 方向）
        extrusion_length: 沿 Y 轴的挤出长度（凹槽的纵向宽度）

    Returns:
        棱柱网格对象
    """
    import bmesh

    R_surface = radius + 1.5
    r_inner = R_surface - groove_depth
    hb = bottom_width / 2.0
    ht = top_width / 2.0
    half_ext = extrusion_length / 2.0

    # 使用 Cube 基元创建，保证法线正确
    bpy.ops.mesh.primitive_cube_add(
        size=1.0,
        location=(0, 0, 0),
    )
    obj = bpy.context.active_object
    obj.name = name

    # 进入编辑模式，用 bmesh 移动8个顶点到梯形棱柱位置
    bpy.ops.object.mode_set(mode='EDIT')
    bm = bmesh.from_edit_mesh(obj.data)

    # Cube 的 8 个顶点在 (±0.5, ±0.5, ±0.5)，需要映射到梯形棱柱顶点
    # 目标: X 方向 = 径向（inner/outer），Y = 挤出方向（±half_ext），Z = 高度（±hb/±ht）
    # 
    # 顶点映射（按 Cube 的局部坐标符号）:
    # Y+ 面(前):   X+ X-  ×  Z+ Z-  = 4个顶点
    # Y- 面(后):   X+ X-  ×  Z+ Z-  = 4个顶点

    for v in bm.verts:
        x_sign = 1 if v.co.x > 0 else -1
        z_sign = 1 if v.co.z > 0 else -1

        # Y 坐标：根据符号映射到 ±half_ext
        new_y = half_ext if v.co.y > 0 else -half_ext

        # X 坐标：+X → 外表面(R_surface)，-X → 内表面(r_inner)
        new_x = R_surface if x_sign > 0 else r_inner

        # Z 坐标：+Z → 根据 X 位置使用 hb 或 ht
        #  外表面(X+)的 Z 范围: z_center ± hb
        #  内表面(X-)的 Z 范围: z_center ± ht
        if x_sign > 0:
            new_z = z_center + hb if z_sign > 0 else z_center - hb
        else:
            new_z = z_center + ht if z_sign > 0 else z_center - ht

        v.co = (new_x, new_y, new_z)

    bmesh.update_edit_mesh(obj.data)
    bpy.ops.object.mode_set(mode='OBJECT')

    print(f"     -> Prism cutter: {len(obj.data.vertices)} verts, {len(obj.data.polygons)} faces")
    return obj


def apply_top_fillet_to_mesh(obj, height, fillet_radius, fillet_segments=16):
    """
    对网格对象的顶部边缘应用圆倒角（包括外边缘和内边缘）

    适用于空心圆柱体，顶部为环形面，同时对外圆边界和内圆边界进行圆角。
    先清理网格（合并重复顶点、融并共面边），再执行圆角，消除布尔运算产生的凸起。

    Args:
        obj: 网格对象（必须已定位到最终位置）
        height: 圆柱体高度（用于定位顶部边缘）
        fillet_radius: 圆角半径
        fillet_segments: 圆角分段数（默认16，产生平滑圆角）
    """
    import bpy

    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj

    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')

    bpy.ops.mesh.remove_doubles(threshold=0.0001)

    bpy.ops.mesh.dissolve_limited(angle_limit=math.radians(1.0))

    bpy.ops.mesh.select_all(action='DESELECT')
    bpy.ops.object.mode_set(mode='OBJECT')

    top_z = height / 2.0
    selected_count = 0

    for edge in obj.data.edges:
        v1 = obj.data.vertices[edge.vertices[0]]
        v2 = obj.data.vertices[edge.vertices[1]]
        if abs(v1.co.z - top_z) < 0.001 and abs(v2.co.z - top_z) < 0.001:
            edge.select = True
            selected_count += 1

    print(f"     -> Selected {selected_count} top edges for fillet")

    bpy.ops.object.mode_set(mode='EDIT')

    bpy.ops.mesh.bevel(
        offset=fillet_radius,
        segments=fillet_segments,
        profile=0.5,
        clamp_overlap=False,
        affect='EDGES'
    )

    bpy.ops.object.mode_set(mode='OBJECT')
    obj.update_tag()
    bpy.context.view_layer.update()


def create_mechanical_demo_scene():
    """
    创建机械设计演示场景
    
    特点：
    - 使用Mesh API创建圆柱体
    - 导出到STEP时会被美化为曲线型圆柱体
    - 适合FreeCAD，可识别为标准体素
    """
    
    print("\n" + "="*60)
    print("Mechanical Object Generator v4.0 (Mesh Version)")
    print("="*60)
    print("Features:")
    print("  - Use Mesh API to create cylinders")
    print("  - Export to STEP with curve beautification")
    print("  - No boolean operations, pure analytical geometry")
    print("  - Recognizable as standard primitives in FreeCAD\n")
    
    print("[1/6] 清理场景...")
    clear_scene()
    
    print("[2/6] 创建基础圆柱体...")
    cylinder = create_mesh_cylinder(
        "Cylinder_R25_H60",
        [0, 0, 0],
        25, 60,
        segments=32
    )
    print("   [OK] Solid cylinder R25xH60 (Mesh)")
    print("     -> Should show as perfect analytical cylinder in FreeCAD")
    
    print("\n[3/6] 创建带斜率的圆柱体...")
    # 创建3°、4°、5°斜率圆柱
    slope_configs = [
        ("Cylinder_Tapered_3deg", 3, [0, -80, 0]),
        ("Cylinder_Tapered_4deg", 4, [0, 80, 0]),
        ("Cylinder_Tapered_5deg", 5, [120, 0, 0]),
    ]
    
    height = 100
    bottom_radius = 25
    
    for name, slope_degree, pos in slope_configs:
        slope_rad = math.radians(slope_degree)
        top_radius = bottom_radius - height * math.tan(slope_rad)
        
        tapered_cylinder = create_tapered_mesh_cylinder(
            name,
            pos,
            bottom_radius,
            top_radius,
            height,
            segments=32
        )
        print(f"   [OK] Tapered cylinder with {slope_degree} degree slope")
        print(f"     -> Bottom radius: {bottom_radius}mm, Top radius: {top_radius:.2f}mm")
    
    print("\n[4/6] 创建45°倒角圆柱...")
    chamfer_cylinder = create_chamfered_cylinder(
        "Cylinder_Chamfer_45deg",
        [-120, 0, 0],
        25, 60, 3,  # 半径25，高度60，倒角尺寸3
        segments=64
    )
    if chamfer_cylinder:
        print("   [OK] 45-degree chamfered cylinder")
        print("     -> Radius: 25mm, Height: 60mm, Chamfer: 3mm")
        print("     -> Should export as CONICAL_SURFACE")
    else:
        print("   [FAIL] Failed to create 45-degree chamfered cylinder")
    
    print("\n[5/6] 创建圆角圆柱...")
    fillet_cylinder = create_fillet_cylinder(
        "Cylinder_Fillet_Top",
        [-120, -80, 0],
        25, 60, 6,  # 半径 25，高度 60，圆角半径 6
        segments=64
    )
    if fillet_cylinder:
        print("   [OK] Fillet cylinder")
        print("     -> Radius: 25mm, Height: 60mm, Fillet radius: 6mm")
        print("     -> Should export as TOROIDAL_SURFACE")
        print("     -> Parser auto-compensates 1.88 factor")
    else:
        print("   [FAIL] Failed to create fillet cylinder")
    
    # 添加一个不同半径的测试圆柱
    print("\n[5b/6] 创建小半径圆角圆柱（验证系数）...")
    small_fillet_cylinder = create_fillet_cylinder(
        "Cylinder_Fillet_Small",
        [-60, -80, 0],
        15, 40, 3,  # 半径 15，高度 40，圆角半径 3
        segments=64
    )
    if small_fillet_cylinder:
        print("   [OK] Small fillet cylinder")
        print("     -> Radius: 15mm, Height: 40mm, Fillet radius: 3mm")
        print("     -> Parser auto-compensates 1.88 factor")
    else:
        print("   [FAIL] Failed to create small fillet cylinder")
    
    print("\n[5c/6] 创建带圆角和倒角的斜率圆柱...")
    tapered_complex = create_tapered_cylinder_with_fillet_and_chamfer(
        "Cylinder_Tapered_Fillet_Chamfer",
        [60, -80, 0],
        25,  # 底部半径
        18,  # 顶部半径（约 3°斜率）
        80,  # 高度
        5,   # 顶部圆角半径
        3,   # 底部倒角尺寸
        segments=64
    )
    if tapered_complex:
        print("   [OK] Tapered cylinder with fillet and chamfer")
        print("     -> Bottom radius: 25mm, Top radius: 18mm, Height: 80mm")
        print("     -> Top fillet radius: 5mm, Bottom chamfer: 3mm")
        print("     -> Should export as complex analytical surface")
    else:
        print("   [FAIL] Failed to create tapered cylinder with fillet and chamfer")
    
    print("\n[5d/6] 创建螺孔圆柱...")
    hollow_cylinder = create_hollow_cylinder(
        "Cylinder_Hollow_R25_r10_H60",
        [120, -80, 0],
        25,  # 外半径
        10,  # 内半径（孔半径）
        60,  # 高度
        segments=64
    )
    if hollow_cylinder:
        print("   [OK] Hollow cylinder")
        print("     -> Outer radius: 25mm, Inner radius: 10mm, Height: 60mm")
        print("     -> Should export as cylinder with hole")
    else:
        print("   [FAIL] Failed to create hollow cylinder")
    
    print("\n[5e/6] 创建锥形螺柱（外柱面上小下大，内柱面上大下小）...")
    tapered_hollow = create_tapered_hollow_cylinder(
        "Cylinder_Tapered_Hollow",
        [120, 80, 0],
        25,  # 外柱底部半径
        20,  # 外柱顶部半径（上小下大）
        8,   # 内孔底部半径
        12,  # 内孔顶部半径（上大下小）
        60,  # 高度
        segments=64
    )
    if tapered_hollow:
        print("   [OK] Tapered hollow cylinder")
        print("     -> Outer: bottom 25mm, top 20mm (smaller top, larger bottom)")
        print("     -> Inner: bottom 8mm, top 12mm (larger top, smaller bottom)")
        print("     -> Height: 60mm")
        print("     -> Should export as cone with tapered hole")
    else:
        print("   [FAIL] Failed to create tapered hollow cylinder")

    print("\n[5f/7] 创建带顶部倒角的锥形空心螺柱...")
    tapered_hollow_chamfer = create_tapered_hollow_cylinder(
        "Cylinder_Tapered_Hollow_Chamfer",
        [180, 80, 0],
        25,  # 外柱底部半径
        20,  # 外柱顶部半径（上小下大）
        8,   # 内孔底部半径
        12,  # 内孔顶部半径（上大下小）
        60,  # 高度
        segments=64
    )
    if tapered_hollow_chamfer:
        apply_top_fillet_to_mesh(tapered_hollow_chamfer, 60, 1.5, fillet_segments=16)
        print("   [OK] Tapered hollow cylinder with top fillet (no groove)")
        print("     -> Outer: bottom 25mm, top 20mm (smaller top, larger bottom)")
        print("     -> Inner: bottom 8mm, top 12mm (larger top, smaller bottom)")
        print("     -> Height: 60mm, Top fillet: R1.5mm (outer + inner edges)")
    else:
        print("   [FAIL] Failed to create tapered hollow cylinder with chamfer")
    
    print("\n[6/7] 创建带 2°斜率的参考圆柱...")
    slope_rad = math.radians(2)
    top_radius = bottom_radius - height * math.tan(slope_rad)
    
    tapered_2deg = create_tapered_mesh_cylinder(
        "Cylinder_Tapered_2deg",
        [0, 160, 0],
        bottom_radius,
        top_radius,
        height,
        segments=32
    )
    print(f"   [OK] Tapered cylinder with 2 degree slope (reference)")
    print(f"     -> Bottom radius: {bottom_radius}mm, Top radius: {top_radius:.2f}mm")
    
    print("\n[7/7] 创建带梯形凹槽的锥形空心螺柱...")
    groove_cylinder = create_tapered_hollow_cylinder(
        "Cylinder_Tapered_Hollow_Chamfer_Grooved",
        [300, 80, 0],
        25,  # 外柱底部半径
        20,  # 外柱顶部半径（上小下大）
        8,   # 内孔底部半径
        12,  # 内孔顶部半径（上大下小）
        60,  # 高度
        segments=64
    )
    if groove_cylinder:
        apply_top_fillet_to_mesh(groove_cylinder, 60, 1.5, fillet_segments=16)
        print("   [OK] Tapered hollow cylinder with top fillet")
        print("     -> Outer: bottom 25mm, top 20mm (smaller top, larger bottom)")
        print("     -> Inner: bottom 8mm, top 12mm (larger top, smaller bottom)")
        print("     -> Height: 60mm, Top fillet: R1.5mm (outer + inner edges)")

        # 在中间位置切割等边梯形凹槽（长方体式直槽）
        print("     -> Cutting isosceles trapezoid groove at middle (straight slot)...")
        try:
            mid_outer_radius = (25.0 + 20.0) / 2.0  # 22.5mm at z=0
            
            groove_cutter = create_trapezoid_prism_cutter(
                "Temp_Trapezoid_Prism",
                z_center=0.0,
                radius=mid_outer_radius,
                groove_depth=5.0,       # 径向切削深度
                bottom_width=16.0,      # 圆柱表面宽度（较宽）
                top_width=10.0,         # 凹槽底部宽度（较窄）
                extrusion_length=50.0,  # 沿 Y 轴的槽宽
            )
            if groove_cutter is None or len(groove_cutter.data.vertices) == 0:
                raise RuntimeError("Prism cutter mesh is empty")

            # 棱柱放置于圆柱中心（X 正方向指向圆柱表面）
            groove_cutter.location = (300, 80, 0)

            # 布尔运算：从圆柱中减去梯形棱柱
            bpy.ops.object.select_all(action='DESELECT')
            groove_cylinder.select_set(True)
            bpy.context.view_layer.objects.active = groove_cylinder

            bool_mod = groove_cylinder.modifiers.new(
                name="TrapezoidGroove", type='BOOLEAN'
            )
            bool_mod.operation = 'DIFFERENCE'
            bool_mod.object = groove_cutter
            bpy.ops.object.modifier_apply(modifier=bool_mod.name)

            # 删除 cutter
            bpy.data.objects.remove(groove_cutter, do_unlink=True)
            print("     [OK] Straight trapezoid groove: depth=5mm, surface_width=16mm, bottom_width=10mm, slot_width=50mm")
            # 设置凹槽参数到自定义属性，供 STEP 导出器使用
            groove_cylinder['step_groove_depth'] = 5.0
            groove_cylinder['step_groove_bottom_width'] = 16.0
            groove_cylinder['step_groove_top_width'] = 10.0
            groove_cylinder['step_groove_extrusion_length'] = 50.0
        except Exception as groove_err:
            print(f"     [WARN] Trapezoid groove cutting failed: {groove_err}")
            import traceback
            traceback.print_exc()
            # 清理
            cutter = bpy.data.objects.get("Temp_Trapezoid_Prism")
            if cutter:
                bpy.data.objects.remove(cutter, do_unlink=True)
            print("     -> Continuing without groove (cylinder still created)")
    else:
        print("   [FAIL] Failed to create grooved cylinder")
    
    # ============================================================
    # [8/8] 2°锥形台阶内孔圆柱
    # ============================================================
    print("\n[8/8] 创建2°锥形台阶内孔圆柱...")
    slope_2deg = math.radians(2)
    stepped_outer_bottom_r = 25.0
    stepped_outer_top_r = stepped_outer_bottom_r - 60.0 * math.tan(slope_2deg)
    stepped_cylinder = create_tapered_stepped_hole_cylinder(
        "Cylinder_Tapered_Stepped_Hole",
        [300, -80, 0],
        stepped_outer_bottom_r,   # 外锥底部半径
        stepped_outer_top_r,      # 外锥顶部半径
        2.0,   # 顶部小孔半径 (2mm)
        2.0,   # 小孔高度 (2mm)
        4.0,   # 大孔参考半径（实际底部半径由2°锥度自动计算）
        60,    # 总高度
        segments=64
    )
    if stepped_cylinder:
        # 几何参数由 STEP 导出器从 mesh 自动识别，无需自定义属性
        print("   [OK] Tapered cylinder with stepped inner hole")
        print(f"     -> Outer: bottom {stepped_outer_bottom_r:.0f}mm, top {stepped_outer_top_r:.2f}mm, "
              f"2\u00b0 taper")
        inner_bot = 2.0 + 58.0 * math.tan(math.radians(2))
        print(f"     -> Inner: top 2mm straight hole r2mm + "
              f"58mm 2\u00b0 tapered hole (r{2.0:.1f} -> r{inner_bot:.1f}mm)")
        print(f"     -> Inner hole min diameter: 4mm at top")
    else:
        print("   [FAIL] Failed to create stepped hole tapered cylinder")
    
    print("\n" + "="*60)
    print("[OK] Mechanical parts created! (Mesh version)")
    print("  Total 14 objects, all MESH type:")
    print("  1. Solid cylinder - exports as analytical cylinder")
    print("  2. 3-degree tapered cylinder - exports as analytical cone")
    print("  3. 4-degree tapered cylinder - exports as analytical cone")
    print("  4. 5-degree tapered cylinder - exports as analytical cone")
    print("  5. 45-degree chamfered cylinder - exports as CONICAL_SURFACE")
    print("  6. Fillet cylinder - exports as TOROIDAL_SURFACE")
    print("  7. Small fillet cylinder - exports as TOROIDAL_SURFACE")
    print("  8. Tapered cylinder with fillet and chamfer - exports as complex analytical surface")
    print("  9. Hollow cylinder - exports as cylinder with hole")
    print("  10. Tapered hollow cylinder - exports as cone with tapered hole")
    print("  11. Tapered hollow cylinder with top fillet - exports as cone with tapered hole and fillets")
    print("  12. 2-degree tapered reference cylinder - exports as analytical cone")
    print("  13. Tapered hollow cylinder with top fillet and trapezoid straight groove - exports as grooved cone")
    print("  14. Tapered cylinder with stepped inner hole (top r2mm h2mm, bottom r4mm)")
    print("="*60)
    print("\nNext: File -> Export -> STEP (Enhanced)")
    print("Verify in FreeCAD:")
    print("  - Cylinder surfaces should be smooth without segments")
    print("  - Accurate diameter/radius measurements")
    print("  - Object type should show as 'Cylinder' etc.")
    print("  - View -> Draw Style -> Shaded, can hide seam edges")


if __name__ == "__main__":
    try:
        print("\n" + "="*60)
        print("Starting create_mesh_cylinder.py...")
        print("="*60)
        create_mechanical_demo_scene()

        # 自动导出 STEP（已禁用，请在 Blender 菜单中手动导出）
        # try:
        #     # 获取脚本所在目录（兼容Blender文本编辑器中__file__未定义）
        #     try:
        #         script_dir = os.path.dirname(os.path.abspath(__file__))
        #     except (NameError, TypeError):
        #         fallback = bpy.data.filepath if bpy.data.filepath else os.getcwd()
        #         script_dir = os.path.dirname(fallback) if fallback else os.getcwd()
        #     step_output = os.path.join(script_dir, "test28.step")
        #     print(f"\nExporting STEP: {step_output}")
        #     bpy.ops.export_scene.step_enhanced(filepath=step_output)
        #     print(f"[OK] STEP exported: {step_output}")
        #     print(f"     Log file: {step_output}.log")
        # except Exception as export_err:
        #     print(f"[WARN] STEP export failed: {export_err}")
        #     print("       Objects are still created in the scene.")

    except Exception as e:
        print(f"\n[ERROR] Script failed: {e}")
        import traceback
        traceback.print_exc()
