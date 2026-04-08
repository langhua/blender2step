#!/usr/bin/env python3
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


def create_mechanical_demo_scene():
    """
    创建机械设计演示场景
    
    特点：
    - 使用Mesh API创建圆柱体
    - 导出到STEP时会被美化为曲线型圆柱体
    - 适合FreeCAD，可识别为标准体素
    """
    
    print("\n" + "="*60)
    print("机械设计物体生成器 v4.0 (Mesh版本)")
    print("="*60)
    print("特点:")
    print("  • 使用Mesh API创建圆柱体")
    print("  • 导出到STEP时美化为曲线型圆柱体")
    print("  • 无布尔运算，导出为纯解析几何体")
    print("  • FreeCAD中可识别为圆柱、棱柱等标准体素\n")
    
    print("[1/5] 清理场景...")
    clear_scene()
    
    print("[2/5] 创建基础圆柱体...")
    cylinder = create_mesh_cylinder(
        "Cylinder_R25_H60",
        [0, 0, 0],
        25, 60,
        segments=32  # 增加分段数，使圆柱体更平滑
    )
    print("   ✓ 实心圆柱体 R25×H60 (Mesh)")
    print("     → FreeCAD中应显示为完美解析圆柱面")
    
    print("\n[3/5] 创建带2°斜率的圆柱体...")
    # 计算2°斜率对应的顶部半径
    height = 100  # 高度100mm
    bottom_radius = 25  # 底部半径25mm
    slope_degree = 2  # 2°斜率
    slope_rad = math.radians(slope_degree)
    top_radius = bottom_radius - height * math.tan(slope_rad)
    
    tapered_cylinder = create_tapered_mesh_cylinder(
        "Cylinder_Tapered_2deg",
        [0, -80, 0],
        bottom_radius,
        top_radius,
        height,
        segments=32  # 增加分段数，使圆柱体更平滑
    )
    print(f"   ✓ 带2°斜率的圆柱体")
    print(f"     → 底部半径: {bottom_radius}mm")
    print(f"     → 顶部半径: {top_radius:.2f}mm")
    print(f"     → 高度: {height}mm")
    print("     → 斜率: {slope_degree}°")
    
    print("\n" + "="*60)
    print("✓ 机械零件创建完成！（Mesh版本）")
    print("  共 2 个物体，全部为 MESH 类型:")
    print("  1. 实心圆柱体 - 导出为解析圆柱面")
    print("  2. 带2°斜率的圆柱体 - 导出为解析曲面")
    print("="*60)
    print("\n下一步：File → Export → STEP (Enhanced)")
    print("在FreeCAD中验证：")
    print("  - 圆柱面应平滑无分段")
    print("  - 可测量准确直径/半径")
    print("  - 物体类型应显示为 'Cylinder' 等")


if __name__ == "__main__":
    try:
        create_mechanical_demo_scene()
    except Exception as e:
        print(f"\n✗ 执行出错: {e}")
        import traceback
        traceback.print_exc()