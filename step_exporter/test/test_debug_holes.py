"""
调试：检查带孔底壳的底面是否有孔
"""
import bpy
import sys
import os
import math

script_dir = os.path.dirname(os.path.abspath(__file__))
step_exporter_dir = os.path.dirname(script_dir)
lib_dir = os.path.join(step_exporter_dir, 'lib')

os.environ['PATH'] = lib_dir + os.pathsep + os.environ.get('PATH', '')
if hasattr(os, 'add_dll_directory'):
    os.add_dll_directory(lib_dir)

# Step 1: 创建底壳
create_script = os.path.join(script_dir, 'create_bottom_shell.py')
with open(create_script, 'r', encoding='utf-8') as f:
    code = f.read()

script_globals = {'__name__': '__main__', '__file__': create_script}
exec(compile(code, create_script, 'exec'), script_globals)
script_globals['create_filleted_bottom_shells_with_holes_scene']()

# Step 2: 检查带孔底壳
obj = bpy.data.objects.get('FilletedShell_WithHoles')
if obj:
    print(f"\n=== Checking {obj.name} ===")
    # 检查面数
    mesh = obj.data
    print(f"  Vertices: {len(mesh.vertices)}")
    print(f"  Faces: {len(mesh.polygons)}")
    
    # 找出最低的 Z 坐标
    min_z = min(v.co.z for v in mesh.vertices)
    max_z = max(v.co.z for v in mesh.vertices)
    print(f"  Z range: {min_z:.3f} to {max_z:.3f}")
    
    # 找出底部面的顶点 (z ≈ min_z)
    bottom_verts = [v for v in mesh.vertices if abs(v.co.z - min_z) < 0.1]
    print(f"  Bottom vertices (z≈{min_z:.3f}): {len(bottom_verts)}")
    
    # 孔预期位置
    hw = 50.0
    hd = 35.0
    hole_ofs_x = 13.0
    hole_ofs_y = 11.0
    hole_r = 1.5
    
    expected_holes = [
        (hw - hole_ofs_x, hd - hole_ofs_y),
        (-(hw - hole_ofs_x), hd - hole_ofs_y),
        (-(hw - hole_ofs_x), -(hd - hole_ofs_y)),
        (hw - hole_ofs_x, -(hd - hole_ofs_y)),
    ]
    
    # 测试射线 - 从下方往上射
    test_positions = [
        (hw * 0.26, hd * 0.31),
        (-hw * 0.26, hd * 0.31),
        (-hw * 0.26, -hd * 0.31),
        (hw * 0.26, -hd * 0.31),
    ]
    
    print(f"\n  Expected hole positions (from center offsets): {expected_holes}")
    print(f"  Test positions (offset from center): {test_positions}")
    
    # 用 depsgraph 获取评估后的对象
    depsgraph = bpy.context.evaluated_depsgraph_get()
    obj_eval = obj.evaluated_get(depsgraph)
    mesh_eval = obj_eval.data
    
    print(f"\n  Evaluated mesh: {len(mesh_eval.vertices)} vertices, {len(mesh_eval.polygons)} faces")
    
    import mathutils
    
    for i, (tx, ty) in enumerate(test_positions):
        exp_hx, exp_hy = expected_holes[i]
        dist_to_hole = math.sqrt((tx - exp_hx)**2 + (ty - exp_hy)**2)
        
        # 射线检测
        ray_start = mathutils.Vector((tx, ty, min_z - 1.0))
        ray_dir = mathutils.Vector((0, 0, 1))
        hit, loc, normal, face_idx = obj_eval.ray_cast(ray_start, ray_dir, distance=20.0)
        
        print(f"\n  Test point {i}: ({tx:.1f}, {ty:.1f})")
        print(f"    Expected hole at: ({exp_hx:.1f}, {exp_hy:.1f}), dist={dist_to_hole:.2f}, hole_r={hole_r}")
        print(f"    Ray from ({tx:.1f}, {ty:.1f}, {min_z-1:.1f}) -> up")
        if hit:
            print(f"    HIT at z={loc.z:.3f} (face #{face_idx})")
        else:
            print(f"    MISS - hole confirmed!")
        
        # 也检查该位置附近是否有顶点
        nearby_verts = [(v.co.x, v.co.y, v.co.z) for v in mesh_eval.vertices 
                        if abs(v.co.z - min_z) < 0.1 
                        and math.sqrt((v.co.x - tx)**2 + (v.co.y - ty)**2) < hole_r + 0.5]
        print(f"    Nearby bottom vertices: {len(nearby_verts)}")
        for v in nearby_verts[:5]:
            print(f"      ({v[0]:.2f}, {v[1]:.2f}, {v[2]:.3f})")

else:
    print("FilletedShell_WithHoles not found!")

# 也检查无孔版本
obj2 = bpy.data.objects.get('FilletedShell_NoHoles')
if obj2:
    print(f"\n=== Checking {obj2.name} ===")
    mesh2 = obj2.data
    min_z2 = min(v.co.z for v in mesh2.vertices)
    
    obj_eval2 = obj2.evaluated_get(depsgraph)
    
    for i, (tx, ty) in enumerate(test_positions):
        ray_start = mathutils.Vector((tx, ty, min_z2 - 1.0))
        ray_dir = mathutils.Vector((0, 0, 1))
        hit, loc, normal, face_idx = obj_eval2.ray_cast(ray_start, ray_dir, distance=20.0)
        if hit:
            print(f"  Test {i} ({tx:.1f},{ty:.1f}): HIT at z={loc.z:.3f}")
        else:
            print(f"  Test {i} ({tx:.1f},{ty:.1f}): MISS")