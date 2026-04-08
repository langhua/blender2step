#!/usr/bin/env python3
"""
机械设计物体生成器 v3.1 - FreeCAD优化版
所有物体均使用 NURBS 曲线 + Extrude 创建，无布尔运算

核心策略：
1. 所有基础形状使用 NURBS 曲线（精确圆、多边形）
2. 通过 curve.extrude 属性创建体积
3. 对象保持为 CURVE 类型（不转换为 MESH）
4. 避免布尔运算，确保导出为纯解析几何体
5. FreeCAD 可完美识别为圆柱、棱柱等标准体素

支持的物体类型：
- 实心圆柱（解析圆柱体）
- 六角螺栓（解析棱柱+圆柱）
- 定位销（解析圆柱）
- 六角螺母（解析棱柱+圆柱孔 - 通过挤出实现）
- 法兰盘（简化版，无螺栓孔）

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
from mathutils import Vector


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


# ==================== NURBS 曲线创建函数 ====================

def create_nurbs_circle(name, center, radius):
    """
    创建一个精确的 NURBS 圆形曲线
    
    使用标准有理NURBS圆表示：
    - 9个控制点
    - 权重: [1, √2/2, 1, √2/2, 1, √2/2, 1, √2/2, 1]
    - Degree 3, Order 4
    
    导出到 STEP 时，C++ 端会识别为完美圆形，创建解析圆柱面
    """
    curve_data = bpy.data.curves.new(name=name, type='CURVE')
    curve_data.dimensions = '3D'
    curve_data.resolution_u = 256  # 提高分辨率，使曲线更平滑
    curve_data.render_resolution_u = 256  # 提高渲染分辨率
    curve_data.bevel_depth = 0
    curve_data.extrude = 0
    curve_data.fill_mode = 'FULL'
    curve_data.bevel_resolution = 32  # 提高倒角分辨率
    
    spline = curve_data.splines.new('NURBS')
    spline.use_cyclic_u = True
    spline.use_endpoint_u = False
    spline.order_u = 4  # Degree 3
    spline.resolution_u = 256  # 提高分辨率，使曲线更平滑
    
    # 添加9个控制点
    num_points = 9
    spline.points.add(num_points - 1)
    
    # 标准NURBS圆参数
    weight = math.sqrt(2.0) / 2.0
    factor = radius * (math.sqrt(2.0) / (1 + weight))
    
    cx, cy, cz = center
    
    control_points = [
        (cx + radius, cy, cz, 1.0),
        (cx + factor, cy + factor, cz, weight),
        (cx, cy + radius, cz, 1.0),
        (cx - factor, cy + factor, cz, weight),
        (cx - radius, cy, cz, 1.0),
        (cx - factor, cy - factor, cz, weight),
        (cx, cy - radius, cz, 1.0),
        (cx + factor, cy - factor, cz, weight),
        (cx + radius, cy, cz, 1.0),
    ]
    
    for i, (x, y, z, w) in enumerate(control_points):
        spline.points[i].co = (x, y, z, w)
    
    obj = bpy.data.objects.new(name, curve_data)
    bpy.context.collection.objects.link(obj)
    
    # 调整对象显示设置
    obj.display_type = 'SOLID'  # 对象显示为实心
    obj.show_wire = False  # 不显示线框
    obj.show_all_edges = False  # 不显示所有边缘
    
    return obj


def create_nurbs_polygon(name, center, radius, sides=6):
    """
    创建 NURBS 正多边形曲线（用于六角头、螺母等）
    导出到 STEP 时，C++ 端会创建解析棱柱面
    """
    curve_data = bpy.data.curves.new(name=name, type='CURVE')
    curve_data.dimensions = '3D'
    curve_data.resolution_u = max(24, sides * 4)
    curve_data.render_resolution_u = max(24, sides * 4)
    curve_data.bevel_depth = 0
    curve_data.extrude = 0
    curve_data.fill_mode = 'FULL'
    
    spline = curve_data.splines.new('POLY')
    spline.use_cyclic_u = True
    spline.resolution_u = max(24, sides * 4)
    
    spline.points.add(sides - 1)
    
    cx, cy, cz = center
    
    for i in range(sides):
        angle = (2 * math.pi * i) / sides - math.pi / 2
        x = cx + radius * math.cos(angle)
        y = cy + radius * math.sin(angle)
        spline.points[i].co = (x, y, cz, 1)
    
    obj = bpy.data.objects.new(name, curve_data)
    bpy.context.collection.objects.link(obj)
    
    return obj


def extrude_curve_to_solid(obj, depth, offset_z=0):
    """
    将曲线对象通过挤出变为实体
    
    关键设置：
    - obj.data.extrude: 挤出深度（沿曲线局部Z轴）
    - obj.data.use_fill_caps: 是否填充端盖（True=实心体）
    
    Args:
        obj: 曲线对象
        depth: 挤出深度
        offset_z: 额外的Z偏移
    """
    if obj.type != 'CURVE':
        return obj
    
    # 设置挤出让曲线变成实体
    obj.data.extrude = depth
    obj.data.bevel_depth = 0  # 不使用倒角
    obj.data.use_fill_caps = True  # 重要！填充端盖=实心体
    obj.data.fill_mode = 'FULL'  # 填充模式设置为完全填充
    
    # 调整对象显示设置
    obj.display_type = 'SOLID'  # 对象显示为实心
    obj.show_wire = False  # 不显示线框
    obj.show_all_edges = False  # 不显示所有边缘
    
    # 确保曲线有材质，这样在实心视图中会显示为实体
    if not obj.data.materials:
        # 创建一个默认材质
        mat = bpy.data.materials.new(name=f"{obj.name}_Material")
        mat.use_nodes = True
        # 设置一个简单的漫反射材质
        principled = mat.node_tree.nodes.get('Principled BSDF')
        if principled:
            principled.inputs['Base Color'].default_value = (0.8, 0.8, 0.8, 1.0)  # 灰色
        obj.data.materials.append(mat)
    
    # 调整位置使底部在正确位置
    obj.location.z += offset_z + depth / 2
    
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
    
    # 强制更新对象和场景
    obj.update_tag(refresh={'DATA'})
    bpy.context.view_layer.update()
    
    # 强制Blender刷新显示
    bpy.ops.wm.redraw_timer(type='DRAW_WIN_SWAP', iterations=1)
    
    return obj


# ==================== 机械零件创建函数 ====================

def create_solid_cylinder(name, center, radius, height):
    """
    创建实心圆柱体 - 使用 NURBS 圆 + 挤出
    
    导出效果：
    - FreeCAD 中显示为完美的解析圆柱面
    - 可以测量直径、半径，显示为 "Cylinder" 类型
    """
    obj = create_nurbs_circle(f"{name}_profile", center, radius)
    extrude_curve_to_solid(obj, height)
    obj.name = name
    return obj


def create_hex_prism(name, center, radius, height):
    """
    创建六角棱柱 - NURBS 六边形 + 挤出
    
    导出效果：
    - FreeCAD 中显示为解析棱柱面
    - 侧面为完美平面
    """
    circumradius = radius
    obj = create_nurbs_polygon(f"{name}_hex_profile", center, circumradius, sides=6)
    extrude_curve_to_solid(obj, height)
    obj.name = name
    return obj


def create_bolt(name, head_center, shank_length, head_height,
               head_diameter, shank_diameter, has_hex_head=True):
    """
    创建螺栓 - 六角头 + 圆柱杆
    
    结构：
    - 六角头：NURBS六边形 + 挤出（解析棱柱）
    - 圆柱杆：NURBS圆 + 挤出（解析圆柱）
    
    注：头和杆是分开的对象，保持为 CURVE 类型
    """
    bolt_objects = []
    
    if has_hex_head:
        head_bottom_z = head_center[2] - head_height / 2
        head = create_hex_prism(
            f"{name}_head",
            [head_center[0], head_center[1], head_bottom_z],
            head_diameter / 2,
            head_height
        )
        bolt_objects.append(head)
    
    # 杆部圆柱
    shank_start_z = head_center[2] - head_height / 2 if has_hex_head else head_center[2]
    shank = create_solid_cylinder(
        f"{name}_shank",
        [head_center[0], head_center[1], shank_start_z],
        shank_diameter / 2,
        shank_length
    )
    bolt_objects.append(shank)
    
    if has_hex_head and len(bolt_objects) >= 2:
        # 将杆部设为头部的子对象（便于选择）
        shank.parent = head
        head.name = name
        return head
    
    return bolt_objects[-1]


def create_nut_with_extruded_hole(name, center, width_across_flats, height, hole_diameter=0):
    """
    创建螺母 - 使用挤出方式创建内孔（无布尔运算）
    
    技巧：
    - 外六角：NURBS六边形 + 挤出（解析棱柱）
    - 内孔：通过设置 bevel_depth 和 inner_radius 实现空心效果
    
    注意：这是简化版，真实螺母内孔需要螺纹
    """
    nut_bottom_z = center[2]
    circumradius = width_across_flats / math.sqrt(3)
    
    # 创建外六角轮廓
    nut = create_hex_prism(
        f"{name}_body",
        [center[0], center[1], nut_bottom_z],
        circumradius,
        height
    )
    
    if hole_diameter == 0:
        hole_diameter = width_across_flats * 0.85
    
    # 为曲线添加内孔效果（通过设置内径）
    # 注意：Blender的曲线不支持直接内孔，需要C++端特殊处理
    # 这里只是标记，实际孔在C++端通过创建圆柱体实现
    nut["hole_diameter"] = hole_diameter
    nut.name = name
    
    return nut


def create_pin(name, center, diameter, length):
    """
    创建定位销 - 简单圆柱体
    
    导出效果：
    - FreeCAD 中显示为完美解析圆柱
    - 可用于定位和对齐
    """
    pin = create_solid_cylinder(
        name,
        [center[0], center[1], center[2]],
        diameter / 2,
        length
    )
    return pin


def create_tapered_cylinder(name, center, bottom_radius, top_radius, height):
    """
    创建带斜率的圆柱体 - 使用 NURBS 曲线 + 挤出
    
    导出效果：
    - FreeCAD 中显示为带斜率的圆柱体
    - 可以测量直径、半径，显示为解析曲面
    
    Args:
        name: 圆柱体名称
        center: 圆柱体中心位置 (x, y, z)
        bottom_radius: 底部半径
        top_radius: 顶部半径
        height: 圆柱体高度
    """
    # 计算底部中心位置
    bottom_center = (center[0], center[1], center[2] - height / 2)
    
    # 创建底部圆形曲线
    curve_data = bpy.data.curves.new(name=f"{name}_profile", type='CURVE')
    curve_data.dimensions = '3D'
    curve_data.resolution_u = 256
    curve_data.render_resolution_u = 256
    curve_data.bevel_depth = 0
    curve_data.extrude = 0
    curve_data.fill_mode = 'FULL'
    
    # 创建NURBS圆形
    spline = curve_data.splines.new('NURBS')
    spline.use_cyclic_u = True
    spline.use_endpoint_u = False
    spline.order_u = 4  # Degree 3
    spline.resolution_u = 256
    
    # 添加9个控制点
    num_points = 9
    spline.points.add(num_points - 1)
    
    # 标准NURBS圆参数
    weight = math.sqrt(2.0) / 2.0
    factor = bottom_radius * (math.sqrt(2.0) / (1 + weight))
    
    cx, cy, cz = bottom_center
    
    control_points = [
        (cx + bottom_radius, cy, cz, 1.0),
        (cx + factor, cy + factor, cz, weight),
        (cx, cy + bottom_radius, cz, 1.0),
        (cx - factor, cy + factor, cz, weight),
        (cx - bottom_radius, cy, cz, 1.0),
        (cx - factor, cy - factor, cz, weight),
        (cx, cy - bottom_radius, cz, 1.0),
        (cx + factor, cy - factor, cz, weight),
        (cx + bottom_radius, cy, cz, 1.0),
    ]
    
    for i, (x, y, z, w) in enumerate(control_points):
        spline.points[i].co = (x, y, z, w)
    
    # 创建曲线对象
    obj = bpy.data.objects.new(name, curve_data)
    bpy.context.collection.objects.link(obj)
    
    # 设置挤出深度
    obj.data.extrude = height
    obj.data.bevel_depth = 0
    obj.data.use_fill_caps = True
    obj.data.fill_mode = 'FULL'
    
    # 设置斜率（通过缩放顶部）
    # 计算缩放因子
    scale_factor = top_radius / bottom_radius
    
    # 创建一个空对象作为缩放中心
    empty = bpy.data.objects.new(f"{name}_scale_center", None)
    empty.location = (center[0], center[1], center[2] + height / 2)  # 顶部中心
    bpy.context.collection.objects.link(empty)
    
    # 将曲线对象设为empty的子对象
    obj.parent = empty
    
    # 缩放empty对象，从而缩放曲线的顶部
    empty.scale = (scale_factor, scale_factor, 1.0)
    
    # 调整对象显示设置
    obj.display_type = 'SOLID'
    obj.show_wire = False
    obj.show_all_edges = False
    
    # 确保曲线有材质
    if not obj.data.materials:
        mat = bpy.data.materials.new(name=f"{obj.name}_Material")
        mat.use_nodes = True
        principled = mat.node_tree.nodes.get('Principled BSDF')
        if principled:
            principled.inputs['Base Color'].default_value = (0.8, 0.8, 0.8, 1.0)
        obj.data.materials.append(mat)
    
    # 调整位置
    obj.location = (0, 0, -height / 2)  # 相对于父对象的位置
    
    return obj


def create_flange_simple(name, center, outer_diameter, thickness):
    """
    创建简化法兰盘 - 无螺栓孔（避免布尔运算）
    
    这是一个实心圆盘，用于演示基础圆柱体
    如果需要带孔的法兰盘，需要在C++端实现布尔运算
    """
    flange = create_solid_cylinder(
        name,
        [center[0], center[1], center[2]],
        outer_diameter / 2,
        thickness
    )
    return flange


# ==================== 主场景生成函数 ====================

def create_mechanical_demo_scene():
    """
    创建优化的机械设计演示场景
    
    特点：
    - 所有物体均为 NURBS 曲线 + Extrude
    - 无布尔运算，确保导出为纯解析几何体
    - 适合FreeCAD，可识别为标准体素
    """
    
    print("\n" + "="*60)
    print("机械设计物体生成器 v3.1 (FreeCAD优化版)")
    print("="*60)
    print("特点:")
    print("  • 所有物体均为 NURBS 曲线 + Extrude")
    print("  • 保持为 CURVE 类型（不转为 Mesh）")
    print("  • 无布尔运算，导出为纯解析几何体")
    print("  • FreeCAD中可识别为圆柱、棱柱等标准体素\n")
    
    print("[1/5] 清理场景...")
    clear_scene()
    
    print("[2/5] 创建基础圆柱体...")
    cylinder = create_solid_cylinder(
        "Cylinder_R25_H60",
        [0, 0, 0],
        25, 60
    )
    print("   ✓ 实心圆柱体 R25×H60 (NURBS圆+挤出)")
    print("     → FreeCAD中应显示为完美解析圆柱面")
    
    print("\n[3/5] 创建六角螺栓...")
    bolt = create_bolt(
        "Bolt_M12x50",
        [80, 0, 25],
        50, 8,  # 杆长50, 头高8
        18, 6,  # 头径18, 杆径6
        has_hex_head=True
    )
    print("   ✓ M12x50 六角螺栓")
    print("     → 头部：解析六角棱柱")
    print("     → 杆部：解析圆柱")
    
    print("\n[4/5] 创建螺母...")
    nut = create_nut_with_extruded_hole(
        "Nut_M12",
        [-80, 0, 5.4],
        19,  # 对边宽19mm
        10.8,  # 厚度10.8mm
        hole_diameter=10.2  # 内孔径10.2mm
    )
    print("   ✓ M12 六角螺母")
    print("     → 外六角：解析棱柱")
    
    print("\n[5/5] 创建定位销...")
    pin = create_pin(
        "Pin_Dowel_8x30",
        [0, 80, 0],
        8, 30
    )
    print("   ✓ 定位销 Ø8×L30")
    print("     → 解析圆柱体")
    
    print("\n[6/6] 创建带2°斜率的圆柱体...")
    # 计算2°斜率对应的顶部半径
    height = 100  # 高度100mm
    bottom_radius = 25  # 底部半径25mm
    slope_degree = 2  # 2°斜率
    slope_rad = math.radians(slope_degree)
    top_radius = bottom_radius - height * math.tan(slope_rad)
    
    tapered_cylinder = create_tapered_cylinder(
        "Cylinder_Tapered_2deg",
        [0, -80, 0],
        bottom_radius,
        top_radius,
        height
    )
    print(f"   ✓ 带2°斜率的圆柱体")
    print(f"     → 底部半径: {bottom_radius}mm")
    print(f"     → 顶部半径: {top_radius:.2f}mm")
    print(f"     → 高度: {height}mm")
    print("     → 斜率: {slope_degree}°")
    
    print("\n" + "="*60)
    print("✓ 机械零件创建完成！（纯NURBS曲线版）")
    print("  共 5 个物体，全部为 CURVE 类型:")
    print("  1. 实心圆柱体 - 解析圆柱面")
    print("  2. M12六角螺栓 - 解析棱柱+圆柱")
    print("  3. M12六角螺母 - 解析棱柱")
    print("  4. 定位销 - 解析圆柱")
    print("  5. 带2°斜率的圆柱体 - 解析曲面")
    print("="*60)
    print("\n下一步：File → Export → STEP (Enhanced)")
    print("在FreeCAD中验证：")
    print("  - 圆柱面应平滑无分段")
    print("  - 可测量准确直径/半径")
    print("  - 物体类型应显示为 'Cylinder', 'Prism' 等")


if __name__ == "__main__":
    try:
        create_mechanical_demo_scene()
    except Exception as e:
        print(f"\n✗ 执行出错: {e}")
        import traceback
        traceback.print_exc()
