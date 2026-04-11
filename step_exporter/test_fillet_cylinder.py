#!/usr/bin/env python3
"""
测试圆角圆柱体的STEP导出
"""

import bpy
import os
import sys

# 清理场景
def clear_scene():
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete()

# 创建圆角圆柱体
def create_fillet_cylinder():
    # 创建基础圆柱体
    bpy.ops.mesh.primitive_cylinder_add(
        radius=25,
        depth=60,
        location=[0, 0, 0],
        vertices=64
    )
    
    obj = bpy.context.active_object
    obj.name = "圆角圆柱"
    
    # 进入编辑模式
    bpy.ops.object.mode_set(mode='EDIT')
    
    # 选择顶部边
    bpy.ops.mesh.select_all(action='DESELECT')
    bpy.ops.object.mode_set(mode='OBJECT')
    
    # 选择顶部的边
    for edge in obj.data.edges:
        v1 = obj.data.vertices[edge.vertices[0]]
        v2 = obj.data.vertices[edge.vertices[1]]
        if abs(v1.co.z - 30) < 0.001 and abs(v2.co.z - 30) < 0.001:
            edge.select = True
    
    bpy.ops.object.mode_set(mode='EDIT')
    
    # 使用倒角工具创建圆角
    bpy.ops.mesh.bevel(
        offset=5,
        segments=8,
        profile=0.5,
        clamp_overlap=False
    )
    
    # 退出编辑模式
    bpy.ops.object.mode_set(mode='OBJECT')
    
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

# 主函数
def main():
    # 清理场景
    clear_scene()
    
    # 创建圆角圆柱体
    print("创建圆角圆柱体...")
    create_fillet_cylinder()
    
    # 导出STEP文件
    output_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "test76.step")
    print(f"导出STEP文件到: {output_path}")
    
    # 使用增强版STEP导出器
    try:
        # 选择所有对象
        bpy.ops.object.select_all(action='SELECT')
        
        # 导出STEP文件
        bpy.ops.export_scene.step_enhanced(
            filepath=output_path,
            check_existing=True,
            filter_glob="*.step;*.stp",
            unit='mm',
            fix_geometry=True,
            create_solid=True,
            advanced_brep=True,
            create_exploded_view=False,
            step_schema='AP214DIS',
            sew_tolerance=0.001
        )
        print("导出成功！")
    except Exception as e:
        print(f"导出失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()