"""
综合圆柱/圆锥类型测试脚本
验证所有类型的圆柱/圆锥是否仍然正确解析

测试类型：
1. 标准圆柱
2. 圆锥
3. 倒角圆柱
4. 倒角圆锥
5. 螺孔圆柱（空心圆柱）
"""

import bpy
import math

def clear_scene():
    """清除场景中的所有对象"""
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)
    
    for data_block in list(bpy.data.meshes):
        if data_block.users == 0:
            bpy.data.meshes.remove(data_block)
    for data_block in list(bpy.data.curves):
        if data_block.users == 0:
            bpy.data.curves.remove(data_block)


def create_standard_cylinder(name, center, radius, height, segments=64):
    """创建标准圆柱体"""
    bpy.ops.mesh.primitive_cylinder_add(
        radius=radius,
        depth=height,
        location=center,
        vertices=segments
    )
    obj = bpy.context.active_object
    obj.name = name
    return obj


def create_cone(name, center, bottom_radius, top_radius, height, segments=64):
    """创建圆锥体"""
    bpy.ops.mesh.primitive_cone_add(
        vertices=segments,
        radius1=bottom_radius,
        radius2=top_radius,
        depth=height,
        location=center
    )
    obj = bpy.context.active_object
    obj.name = name
    return obj


def create_chamfered_cylinder(name, center, radius, height, chamfer_size, segments=64):
    """创建倒角圆柱体"""
    # 创建圆柱体
    bpy.ops.mesh.primitive_cylinder_add(
        radius=radius,
        depth=height,
        location=center,
        vertices=segments
    )
    obj = bpy.context.active_object
    obj.name = name
    
    # 添加倒角修改器
    chamfer_mod = obj.modifiers.new(name="Chamfer", type='BEVEL')
    chamfer_mod.width = chamfer_size
    chamfer_mod.segments = 1
    chamfer_mod.limit_method = 'ANGLE'
    chamfer_mod.angle_limit = math.radians(30)
    
    # 应用修改器
    bpy.ops.object.modifier_apply(modifier=chamfer_mod.name)
    
    return obj


def create_chamfered_cone(name, center, bottom_radius, top_radius, height, chamfer_size, segments=64):
    """创建倒角圆锥体"""
    # 创建圆锥体
    bpy.ops.mesh.primitive_cone_add(
        vertices=segments,
        radius1=bottom_radius,
        radius2=top_radius,
        depth=height,
        location=center
    )
    obj = bpy.context.active_object
    obj.name = name
    
    # 添加倒角修改器
    chamfer_mod = obj.modifiers.new(name="Chamfer", type='BEVEL')
    chamfer_mod.width = chamfer_size
    chamfer_mod.segments = 1
    chamfer_mod.limit_method = 'ANGLE'
    chamfer_mod.angle_limit = math.radians(30)
    
    # 应用修改器
    bpy.ops.object.modifier_apply(modifier=chamfer_mod.name)
    
    return obj


def create_hollow_cylinder(name, center, outer_radius, inner_radius, height, segments=64):
    """创建螺孔圆柱（空心圆柱）"""
    # 创建外圆柱体
    bpy.ops.mesh.primitive_cylinder_add(
        radius=outer_radius,
        depth=height,
        location=center,
        vertices=segments
    )
    outer_obj = bpy.context.active_object
    outer_obj.name = f"{name}_outer"
    
    # 创建内圆柱体（孔）
    bpy.ops.mesh.primitive_cylinder_add(
        radius=inner_radius,
        depth=height + 2,
        location=center,
        vertices=segments
    )
    inner_obj = bpy.context.active_object
    inner_obj.name = f"{name}_inner"
    
    # 布尔差集运算
    bpy.ops.object.select_all(action='DESELECT')
    outer_obj.select_set(True)
    bpy.context.view_layer.objects.active = outer_obj
    
    bool_mod = outer_obj.modifiers.new(name="Hole", type='BOOLEAN')
    bool_mod.operation = 'DIFFERENCE'
    bool_mod.object = inner_obj
    
    bpy.ops.object.modifier_apply(modifier=bool_mod.name)
    bpy.data.objects.remove(inner_obj, do_unlink=True)
    
    outer_obj.name = name
    return outer_obj


def create_fillet_cylinder(name, center, radius, height, fillet_radius, segments=64):
    """创建圆倒角圆柱体"""
    # 创建圆柱体
    bpy.ops.mesh.primitive_cylinder_add(
        radius=radius,
        depth=height,
        location=center,
        vertices=segments
    )
    obj = bpy.context.active_object
    obj.name = name
    
    # 添加倒角修改器（圆角）
    fillet_mod = obj.modifiers.new(name="Fillet", type='BEVEL')
    fillet_mod.width = fillet_radius
    fillet_mod.segments = 4  # 使用4个段来创建圆角
    fillet_mod.limit_method = 'ANGLE'
    fillet_mod.angle_limit = math.radians(30)
    
    # 应用修改器
    bpy.ops.object.modifier_apply(modifier=fillet_mod.name)
    
    return obj


def create_test_scene():
    """创建综合测试场景"""
    
    print("\n" + "="*60)
    print("综合圆柱/圆锥类型测试脚本 v1.0")
    print("="*60)
    
    # 清除场景
    clear_scene()
    
    # 1. 标准圆柱：R=20mm, H=50mm
    print("\n[1/5] 创建标准圆柱体...")
    create_standard_cylinder(
        "Standard_Cylinder_R20_H50",
        [0, 0, 0],
        20,  # 半径
        50,  # 高度
        segments=64
    )
    print("   ✓ 标准圆柱体 R=20mm, H=50mm")
    
    # 2. 圆锥：底部R=25mm, 顶部R=10mm, H=60mm
    print("\n[2/5] 创建圆锥体...")
    create_cone(
        "Cone_R25_R10_H60",
        [60, 0, 0],
        25,  # 底部半径
        10,  # 顶部半径
        60,  # 高度
        segments=64
    )
    print("   ✓ 圆锥体 底部R=25mm, 顶部R=10mm, H=60mm")
    
    # 3. 倒角圆柱：R=15mm, H=40mm, 倒角2mm
    print("\n[3/5] 创建倒角圆柱体...")
    create_chamfered_cylinder(
        "Chamfered_Cylinder_R15_H40_C2",
        [120, 0, 0],
        15,  # 半径
        40,  # 高度
        2,   # 倒角大小
        segments=64
    )
    print("   ✓ 倒角圆柱体 R=15mm, H=40mm, 倒角=2mm")
    
    # 4. 倒角圆锥：底部R=20mm, 顶部R=8mm, H=50mm, 倒角1.5mm
    print("\n[4/5] 创建倒角圆锥体...")
    create_chamfered_cone(
        "Chamfered_Cone_R20_R8_H50_C1.5",
        [180, 0, 0],
        20,  # 底部半径
        8,   # 顶部半径
        50,  # 高度
        1.5, # 倒角大小
        segments=64
    )
    print("   ✓ 倒角圆锥体 底部R=20mm, 顶部R=8mm, H=50mm, 倒角=1.5mm")
    
    # 5. 螺孔圆柱：外R=25mm, 内R=10mm, H=60mm
    print("\n[5/5] 创建螺孔圆柱体...")
    create_hollow_cylinder(
        "Hollow_Cylinder_R25_r10_H60",
        [240, 0, 0],
        25,  # 外半径
        10,  # 内半径
        60,  # 高度
        segments=64
    )
    print("   ✓ 螺孔圆柱体 外R=25mm, 内R=10mm, H=60mm")
    
    # 6. 圆倒角圆柱：R=18mm, H=45mm, 圆倒角3mm
    print("\n[6/6] 创建圆倒角圆柱体...")
    create_fillet_cylinder(
        "Fillet_Cylinder_R18_H45_F3",
        [300, 0, 0],
        18,  # 半径
        45,  # 高度
        3,   # 圆倒角半径
        segments=64
    )
    print("   ✓ 圆倒角圆柱体 R=18mm, H=45mm, 圆倒角=3mm")
    
    print("\n" + "="*60)
    print("✓ 测试场景创建完成！")
    print("  共 6 个物体:")
    print("  1. 标准圆柱体 - R=20mm, H=50mm")
    print("  2. 圆锥体 - 底部R=25mm, 顶部R=10mm, H=60mm")
    print("  3. 倒角圆柱体 - R=15mm, H=40mm, 倒角=2mm")
    print("  4. 倒角圆锥体 - 底部R=20mm, 顶部R=8mm, H=50mm, 倒角=1.5mm")
    print("  5. 螺孔圆柱体 - 外R=25mm, 内R=10mm, H=60mm")
    print("  6. 圆倒角圆柱体 - R=18mm, H=45mm, 圆倒角=3mm")
    print("="*60)
    print("\n下一步：File → Export → STEP (Enhanced)")
    print("在FreeCAD中验证所有类型的解析曲面是否正确")
    print("="*60)


if __name__ == "__main__":
    try:
        create_test_scene()
    except Exception as e:
        print(f"\n✗ 执行出错: {e}")
        import traceback
        traceback.print_exc()
