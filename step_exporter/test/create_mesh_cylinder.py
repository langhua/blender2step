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
    创建顶部带圆角的圆柱体
    
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
        
        # 选择顶部的边
        bpy.ops.mesh.select_all(action='DESELECT')
        bpy.ops.object.mode_set(mode='OBJECT')
        
        # 选择顶部的边
        for edge in obj.data.edges:
            v1 = obj.data.vertices[edge.vertices[0]]
            v2 = obj.data.vertices[edge.vertices[1]]
            if abs(v1.co.z - height/2) < 0.001 and abs(v2.co.z - height/2) < 0.001:
                edge.select = True
        
        bpy.ops.object.mode_set(mode='EDIT')
        
        # 使用倒角工具创建圆角
        # 对于圆角，需要使用bevel工具，并设置正确的offset
        # Bevel的offset参数对于圆角（profile=0.5）实际上是圆角半径
        bpy.ops.mesh.bevel(
            offset=fillet_radius,  # offset直接等于圆角半径
            segments=8,
            profile=0.5,
            clamp_overlap=False
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
        print(f"创建圆角圆柱失败: {e}")
        import traceback
        traceback.print_exc()
        return None


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
    
    print("[1/6] 清理场景...")
    clear_scene()
    
    print("[2/6] 创建基础圆柱体...")
    cylinder = create_mesh_cylinder(
        "Cylinder_R25_H60",
        [0, 0, 0],
        25, 60,
        segments=32
    )
    print("   ✓ 实心圆柱体 R25×H60 (Mesh)")
    print("     → FreeCAD中应显示为完美解析圆柱面")
    
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
        print(f"   ✓ 带{slope_degree}°斜率的圆柱体")
        print(f"     → 底部半径: {bottom_radius}mm, 顶部半径: {top_radius:.2f}mm")
    
    print("\n[4/6] 创建45°倒角圆柱...")
    chamfer_cylinder = create_chamfered_cylinder(
        "Cylinder_Chamfer_45deg",
        [-120, 0, 0],
        25, 60, 3,  # 半径25，高度60，倒角尺寸3
        segments=64
    )
    if chamfer_cylinder:
        print("   ✓ 45°倒角圆柱体")
        print("     → 半径: 25mm, 高度: 60mm, 倒角: 3mm")
        print("     → 导出应为CONICAL_SURFACE")
    else:
        print("   ✗ 创建45°倒角圆柱失败")
    
    print("\n[5/6] 创建圆角圆柱...")
    fillet_cylinder = create_fillet_cylinder(
        "Cylinder_Fillet_Top",
        [-120, -80, 0],
        25, 60, 6,  # 半径25，高度60，圆角半径6
        segments=64
    )
    if fillet_cylinder:
        print("   ✓ 圆角圆柱体")
        print("     → 半径: 25mm, 高度: 60mm, 圆角半径: 6mm")
        print("     → 导出应为TOROIDAL_SURFACE")
    else:
        print("   ✗ 创建圆角圆柱失败")
    
    print("\n[6/6] 创建带2°斜率的参考圆柱...")
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
    print(f"   ✓ 带2°斜率的圆柱体（参考）")
    print(f"     → 底部半径: {bottom_radius}mm, 顶部半径: {top_radius:.2f}mm")
    
    print("\n" + "="*60)
    print("✓ 机械零件创建完成！（Mesh版本）")
    print("  共 7 个物体，全部为 MESH 类型:")
    print("  1. 实心圆柱体 - 导出为解析圆柱面")
    print("  2. 3°斜率圆柱 - 导出为解析圆锥面")
    print("  3. 4°斜率圆柱 - 导出为解析圆锥面")
    print("  4. 5°斜率圆柱 - 导出为解析圆锥面")
    print("  5. 45°倒角圆柱 - 导出为CONICAL_SURFACE")
    print("  6. 圆角圆柱 - 导出为TOROIDAL_SURFACE")
    print("  7. 2°斜率圆柱（参考）- 导出为解析圆锥面")
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
