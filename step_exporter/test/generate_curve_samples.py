import bpy
import math

def clear_scene():
    """清空场景"""
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)

def create_poly_curve(name, points, location=(0,0,0), closed=False):
    """创建POLY曲线（折线）
    
    Args:
        name: 曲线名称
        points: 控制点列表，每个点是一个(x,y,z)元组
        location: 对象位置
        closed: 是否闭合
    """
    # 创建曲线数据
    curve_data = bpy.data.curves.new(name=name, type='CURVE')
    curve_data.dimensions = '3D'
    
    # 创建样条线
    spline = curve_data.splines.new('POLY')
    spline.points.add(len(points) - 1)
    
    for i, point in enumerate(points):
        x, y, z = point
        spline.points[i].co = (x, y, z, 1)
    
    if closed:
        spline.use_cyclic_u = True
    
    # 创建对象
    curve_obj = bpy.data.objects.new(name, curve_data)
    curve_obj.location = location
    bpy.context.scene.collection.objects.link(curve_obj)
    
    return curve_obj

def create_bezier_curve(name, points, location=(0,0,0), closed=False):
    """创建贝塞尔曲线
    
    Args:
        name: 曲线名称
        points: 控制点列表，每个点是一个(x,y,z)元组
        location: 对象位置
        closed: 是否闭合
    """
    curve_data = bpy.data.curves.new(name=name, type='CURVE')
    curve_data.dimensions = '3D'
    
    spline = curve_data.splines.new('BEZIER')
    spline.bezier_points.add(len(points) - 1)
    
    for i, point in enumerate(points):
        x, y, z = point
        spline.bezier_points[i].co = (x, y, z)
        # 对于闭合曲线且控制点数为4的情况，使用圆形手柄计算
        if closed and len(points) == 4:
            # 计算控制点到原点的距离（半径）
            r = math.sqrt(x*x + y*y + z*z)
            if r > 0:
                # 单位切线向量：垂直于半径向量
                tx = -y / r
                ty = x / r
                # 标准贝塞尔圆手柄长度（(4/3)*tan(π/8) ≈ 0.552285）
                offset = 0.552285 * r
                spline.bezier_points[i].handle_left = (x - offset * tx, y - offset * ty, z)
                spline.bezier_points[i].handle_right = (x + offset * tx, y + offset * ty, z)
            else:
                # 原点处，使用默认偏移
                offset = 0.552285
                spline.bezier_points[i].handle_left = (x - offset, y, z)
                spline.bezier_points[i].handle_right = (x + offset, y, z)
        else:
            # 非圆形贝塞尔曲线，使用原始偏移量逻辑
            # 端点使用极小偏移，中间点使用小偏移，保持形状接近原图
            if i == 0 or i == len(points) - 1:
                # 端点：使用极小偏移，保持平滑连接
                offset = 0.05
            else:
                # 中间点：使用小偏移，避免过度扭曲
                offset = 0.1
            spline.bezier_points[i].handle_left = (x - offset, y, z)
            spline.bezier_points[i].handle_right = (x + offset, y, z)
        # 设置手柄类型为自由，确保使用我们设置的手柄位置
        spline.bezier_points[i].handle_left_type = 'FREE'
        spline.bezier_points[i].handle_right_type = 'FREE'
    
    if closed:
        spline.use_cyclic_u = True
    
    curve_obj = bpy.data.objects.new(name, curve_data)
    curve_obj.location = location
    bpy.context.scene.collection.objects.link(curve_obj)
    
    return curve_obj

def create_nurbs_curve(name, points, weights=None, knots_u=None, order=3, location=(0,0,0), closed=False):
    """创建NURBS曲线
    
    Args:
        name: 曲线名称
        points: 控制点列表，每个点是一个(x,y,z)元组
        weights: 权重列表（可选）
        knots_u: 节点向量（可选）
        order: 阶数（默认3）
        location: 对象位置
        closed: 是否闭合
    """
    curve_data = bpy.data.curves.new(name=name, type='CURVE')
    curve_data.dimensions = '3D'
    
    spline = curve_data.splines.new('NURBS')
    spline.points.add(len(points) - 1)
    
    # 设置控制点
    for i, point in enumerate(points):
        x, y, z = point
        spline.points[i].co = (x, y, z, 1)
    
    # 设置权重
    if weights is not None and len(weights) == len(points):
        for i, w in enumerate(weights):
            spline.points[i].weight = w
    
    # 设置阶数
    spline.order_u = order
    
    # 设置节点向量（如果提供）
    if knots_u is not None:
        # Blender会自动生成节点向量，这里不手动设置
        pass
    
    if closed:
        spline.use_cyclic_u = True
        spline.use_endpoint_u = False
    else:
        spline.use_endpoint_u = True
    
    curve_obj = bpy.data.objects.new(name, curve_data)
    curve_obj.location = location
    bpy.context.scene.collection.objects.link(curve_obj)
    
    return curve_obj

def main():
    """生成各种曲线样例"""
    clear_scene()
    
    test_curves = []
    x_offset = 0
    
    # 1. 简单POLY曲线（折线）
    poly_points = [
        (0, 0, 0),
        (1, 2, 0),
        (2, 0, 0),
        (3, 1, 0),
        (4, 0, 0)
    ]
    poly_curve = create_poly_curve("PolyLine", poly_points, location=(x_offset, 0, 0))
    test_curves.append(poly_curve)
    x_offset += 6
    
    # 2. 闭合POLY曲线（多边形）
    polygon_points = [
        (0, 0, 0),
        (1, 0, 0),
        (1, 1, 0),
        (0, 1, 0)
    ]
    polygon = create_poly_curve("Polygon", polygon_points, location=(x_offset, 0, 0), closed=True)
    test_curves.append(polygon)
    x_offset += 6
    
    # 3. 贝塞尔曲线（开放）
    bezier_points = [
        (0, 0, 0),
        (1, 2, 0),
        (2, -1, 0),
        (3, 2, 0),
        (4, 0, 0)
    ]
    bezier = create_bezier_curve("BezierCurve", bezier_points, location=(x_offset, 0, 0))
    test_curves.append(bezier)
    x_offset += 6
    
    # 4. 闭合贝塞尔曲线（贝塞尔环）
    bezier_circle_points = [
        (1, 0, 0),
        (0, 1, 0),
        (-1, 0, 0),
        (0, -1, 0)
    ]
    bezier_circle = create_bezier_curve("BezierCircle", bezier_circle_points, location=(x_offset, 0, 0), closed=True)
    test_curves.append(bezier_circle)
    x_offset += 6
    
    # 5. NURBS曲线（开放，均匀权重）
    nurbs_points = [
        (0, 0, 0),
        (1, 1.5, 0),
        (2, -0.5, 0),
        (3, 1.5, 0),
        (4, 0, 0)
    ]
    nurbs = create_nurbs_curve("NURBS_Uniform", nurbs_points, location=(x_offset, 0, 0))
    test_curves.append(nurbs)
    x_offset += 6
    
    # 6. NURBS曲线（带不同权重）
    weights = [1.0, 0.5, 1.5, 0.8, 1.0]
    nurbs_weighted = create_nurbs_curve("NURBS_Weighted", nurbs_points, weights=weights, location=(x_offset, 0, 0))
    test_curves.append(nurbs_weighted)
    x_offset += 6
    
    # 7. NURBS曲线（高阶，阶数=4）
    nurbs_high_order = create_nurbs_curve("NURBS_Order4", nurbs_points, order=4, location=(x_offset, 0, 0))
    test_curves.append(nurbs_high_order)
    x_offset += 6
    
    # 8. 3D空间曲线（不在同一平面）
    spiral_points = []
    for i in range(10):
        angle = i * math.pi / 2
        x = math.cos(angle) * 2
        y = math.sin(angle) * 2
        z = i * 0.3
        spiral_points.append((x, y, z))
    
    spiral = create_nurbs_curve("Spiral", spiral_points, location=(x_offset, 0, 0))
    test_curves.append(spiral)
    
    # 创建测试集合
    bpy.ops.collection.create(name="Curve_Test_Objects")
    test_collection = bpy.data.collections["Curve_Test_Objects"]
    bpy.context.scene.collection.children.link(test_collection)
    
    # 将所有曲线对象移动到测试集合
    for curve in test_curves:
        for coll in curve.users_collection:
            coll.objects.unlink(curve)
        test_collection.objects.link(curve)
    
    # 设置3D视图
    for area in bpy.context.screen.areas:
        if area.type == 'VIEW_3D':
            for space in area.spaces:
                if space.type == 'VIEW_3D':
                    space.shading.type = 'SOLID'
                    space.shading.light = 'MATCAP'
                    space.shading.show_cavity = True
    
    print(f"已创建 {len(test_curves)} 个曲线样例，用于STEP导出测试。")
    print("曲线类型：POLY、BEZIER、NURBS（均匀权重、不同权重、高阶）、螺旋线")
    print("请使用STEP导出插件测试这些曲线的导出功能。")

if __name__ == "__main__":
    main()