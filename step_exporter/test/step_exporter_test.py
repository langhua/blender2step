import bpy

# 删除默认立方体
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)

# 创建测试几何体
test_objects = []

# 1. 立方体（基础测试）
bpy.ops.mesh.primitive_cube_add(size=2, location=(0, 0, 0))
cube = bpy.context.active_object
cube.name = "Test_Cube"
test_objects.append(cube)

# 2. 球体（曲面测试）
bpy.ops.mesh.primitive_uv_sphere_add(radius=1, location=(4, 0, 0))
sphere = bpy.context.active_object
sphere.name = "Test_Sphere"
test_objects.append(sphere)

# 3. 圆柱体（圆柱面测试）
bpy.ops.mesh.primitive_cylinder_add(radius=0.8, depth=2, location=(8, 0, 0))
cylinder = bpy.context.active_object
cylinder.name = "Test_Cylinder"
test_objects.append(cylinder)

# 4. 圆锥体（锥面测试）
bpy.ops.mesh.primitive_cone_add(radius1=1, radius2=0, depth=2, location=(12, 0, 0))
cone = bpy.context.active_object
cone.name = "Test_Cone"
test_objects.append(cone)

# 5. 圆环（复杂曲面测试）
bpy.ops.mesh.primitive_torus_add(major_radius=1.5, minor_radius=0.5, location=(16, 0, 0))
torus = bpy.context.active_object
torus.name = "Test_Torus"
test_objects.append(torus)

# 在X=0, Y=4的位置创建变换测试对象
# 6. 缩放测试立方体
bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 4, 0))
scaled_cube = bpy.context.active_object
scaled_cube.name = "Scaled_Cube"
scaled_cube.scale = (2, 0.5, 3)  # 非均匀缩放
test_objects.append(scaled_cube)

# 7. 旋转测试立方体
bpy.ops.mesh.primitive_cube_add(size=1, location=(4, 4, 0))
rotated_cube = bpy.context.active_object
rotated_cube.name = "Rotated_Cube"
rotated_cube.rotation_euler = (0.785, 0.523, 0.262)  # 45°, 30°, 15°
test_objects.append(rotated_cube)

# 8. 位移测试立方体
bpy.ops.mesh.primitive_cube_add(size=1, location=(8, 4, 2))
moved_cube = bpy.context.active_object
moved_cube.name = "Moved_Cube"
test_objects.append(moved_cube)

# 在X=0, Y=8的位置创建修改器测试对象
# 9. 细分曲面测试
bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 8, 0))
subdiv_cube = bpy.context.active_object
subdiv_cube.name = "Subdivision_Cube"
subdiv_mod = subdiv_cube.modifiers.new(name="Subdivision", type='SUBSURF')
subdiv_mod.levels = 2
subdiv_mod.render_levels = 2
test_objects.append(subdiv_cube)

# 10. 布尔运算测试
# 创建基础对象
bpy.ops.mesh.primitive_cube_add(size=1.5, location=(4, 8, 0))
bool_base = bpy.context.active_object
bool_base.name = "Boolean_Base"

# 创建布尔对象
bpy.ops.mesh.primitive_uv_sphere_add(radius=0.8, location=(4, 8, 0))
bool_sphere = bpy.context.active_object
bool_sphere.name = "Boolean_Sphere"

# 添加布尔修改器
bool_mod = bool_base.modifiers.new(name="Boolean", type='BOOLEAN')
bool_mod.operation = 'DIFFERENCE'
bool_mod.object = bool_sphere
test_objects.append(bool_base)

# 注意：布尔对象本身不需要导出
bool_sphere.hide_render = True
bool_sphere.hide_viewport = True

# 11. 复杂网格（猴头）
bpy.ops.mesh.primitive_monkey_add(size=1.5, location=(8, 8, 0))
monkey = bpy.context.active_object
monkey.name = "Suzanne"
test_objects.append(monkey)

# 12. 网格编辑测试
bpy.ops.mesh.primitive_grid_add(x_subdivisions=10, y_subdivisions=10, size=2, location=(12, 8, 0))
grid = bpy.context.active_object
grid.name = "Edited_Grid"

# 进入编辑模式进行简单编辑
bpy.ops.object.mode_set(mode='EDIT')
bpy.ops.mesh.select_all(action='SELECT')
bpy.ops.transform.translate(value=(0, 0, 0.5), orient_type='GLOBAL')
bpy.ops.object.mode_set(mode='OBJECT')
test_objects.append(grid)

# 创建集合进行组织
bpy.ops.collection.create(name="STEP_Test_Objects")
test_collection = bpy.data.collections["STEP_Test_Objects"]
bpy.context.scene.collection.children.link(test_collection)

# 将所有测试对象移动到测试集合
for obj in test_objects:
    # 从原集合中移除
    for coll in obj.users_collection:
        coll.objects.unlink(obj)
    # 添加到测试集合
    test_collection.objects.link(obj)

# 设置3D视图，便于查看
for area in bpy.context.screen.areas:
    if area.type == 'VIEW_3D':
        for space in area.spaces:
            if space.type == 'VIEW_3D':
                space.shading.type = 'SOLID'
                space.shading.light = 'MATCAP'
                space.shading.show_cavity = True

print("测试场景已创建，包含多种几何体和变换，准备进行STEP导出测试。")
