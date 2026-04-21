"""
独立螺孔圆柱创建脚本
用于完整测试螺孔圆柱的解析和导出

用法: 
  blender --background --python create_hollow_cylinder_standalone.py
"""

import bpy
import math

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


def create_hollow_cylinder_scene():
    """创建螺孔圆柱测试场景"""
    
    print("\n" + "="*60)
    print("螺孔圆柱创建脚本 v1.0")
    print("="*60)
    
    # 清除场景
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)
    
    print("\n创建螺孔圆柱...")
    print("  外半径：25mm")
    print("  内半径：10mm")
    print("  高度：60mm")
    print("  分段数：64")
    
    hollow_cylinder = create_hollow_cylinder(
        "Hollow_Cylinder_R25_r10_H60",
        [0, 0, 0],
        25,  # 外半径
        10,  # 内半径（孔半径）
        60,  # 高度
        segments=64
    )
    
    if hollow_cylinder:
        print("\n✓ 螺孔圆柱创建成功")
        print(f"  名称：{hollow_cylinder.name}")
        print(f"  顶点数：{len(hollow_cylinder.data.vertices)}")
        print(f"  面数：{len(hollow_cylinder.data.polygons)}")
        print(f"  位置：{hollow_cylinder.location}")
    else:
        print("\n✗ 螺孔圆柱创建失败")
    
    print("\n" + "="*60)
    print("下一步：File → Export → STEP (Enhanced)")
    print("在 FreeCAD 中验证：")
    print("  - 圆柱面应平滑无分段")
    print("  - 可测量准确直径/半径")
    print("  - 物体类型应显示为 'Cylinder' 等")
    print("  - 视图 → 绘图式样 → 着色，可隐藏接缝边")
    print("="*60)
    
    return hollow_cylinder


if __name__ == "__main__":
    try:
        create_hollow_cylinder_scene()
    except Exception as e:
        print(f"\n✗ 执行出错: {e}")
        import traceback
        traceback.print_exc()
