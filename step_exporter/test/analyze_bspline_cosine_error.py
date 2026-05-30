"""
分析 test53.step 中 BSpline 曲面与余弦曲线的误差
"""
import re
import math
import os

step_file = r'f:\git\blender2step\step_exporter\test53.step'

print("="*80)
print("test53.step - BSpline 与余弦曲线误差分析")
print("="*80)

with open(step_file, 'r', encoding='utf-8', errors='replace') as f:
    content = f.read()

# ==================== 1. 提取所有坐标点 ====================
point_pattern = r'#(\d+)\s*=\s*CARTESIAN_POINT\s*\([^,]+,\s*\(\s*([^,\r\n]+)\s*,\s*([^,\r\n]+)\s*,\s*([^\)\r\n]+)\s*\)'
points = {}
for match in re.finditer(point_pattern, content):
    point_id = int(match.group(1))
    try:
        x = float(match.group(2).strip())
        y = float(match.group(3).strip())
        z = float(match.group(4).strip())
        points[point_id] = (x, y, z)
    except ValueError:
        pass

print(f"\n总坐标点数: {len(points)}")

# ==================== 2. 查找 BSpline 曲面定义 ====================
print("\n" + "="*80)
print("查找 BSpline 曲面...")
print("="*80)

# 查找 B_SPLINE_SURFACE_WITH_KNOTS
bspline_pattern = r'#(\d+)\s*=\s*B_SPLINE_SURFACE_WITH_KNOTS\s*\((\d+)\s*,\s*(\d+)\s*,\s*\(\s*\(([^)]+)\)\s*\)\s*,\s*\(\s*\(([^)]+)\)\s*\)\s*,\s*KNOTSPEC'
bsplines = {}

for match in re.finditer(bspline_pattern, content, re.DOTALL):
    surf_id = int(match.group(1))
    u_degree = int(match.group(2))
    v_degree = int(match.group(3))
    cp_data_u = match.group(4)
    cp_data_v = match.group(5)
    
    # 提取控制点引用
    cp_refs = [int(x) for x in re.findall(r'#(\d+)', cp_data_u)]
    
    bsplines[surf_id] = {
        'u_degree': u_degree,
        'v_degree': v_degree,
        'control_points': cp_refs
    }

if bsplines:
    print(f"\n找到 {len(bsplines)} 个 BSpline 曲面")
    for surf_id, info in list(bsplines.items())[:5]:
        print(f"  曲面 #{surf_id}: U度={info['u_degree']}, V度={info['v_degree']}, 控制点={len(info['control_points'])}")
else:
    print("\n未找到 B_SPLINE_SURFACE_WITH_KNOTS")
    print("尝试查找其他 BSpline 格式...")
    
    # 尝试其他格式
    bspline_pattern2 = r'#(\d+)\s*=\s*B_SPLINE_SURFACE\s*\((\d+)\s*,\s*(\d+)'
    bsplines2 = list(re.finditer(bspline_pattern2, content))
    print(f"找到 {len(bsplines2)} 个 B_SPLINE_SURFACE")

# ==================== 3. 查找 RULED_SURFACE (直纹面) ====================
print("\n" + "="*80)
print("查找 RULED_SURFACE (直纹面)...")
print("="*80)

ruled_pattern = r'#(\d+)\s*=\s*RULED_SURFACE\s*\([^,]+,\s*#(\d+)\s*,\s*#(\d+)'
ruled_surfaces = list(re.finditer(ruled_pattern, content))

print(f"找到 {len(ruled_surfaces)} 个 RULED_SURFACE")

# ==================== 4. 分析侧壁几何结构 ====================
print("\n" + "="*80)
print("分析侧壁几何结构...")
print("="*80)

# 提取所有 Z 层数据
z_vals = [p[2] for p in points.values()]
unique_z = sorted(set([round(z, 3) for z in z_vals]))

print(f"\nZ 轴层数: {len(unique_z)}")
print(f"Z 范围: {min(z_vals):.4f} ~ {max(z_vals):.4f}")

# 分析侧壁点 (排除 Z=0 的原点)
side_wall_points = [p for p in points.values() if p[2] > 0.1]

if side_wall_points:
    side_z = sorted(set([round(p[2], 3) for p in side_wall_points]))
    print(f"侧壁层数: {len(side_z)}")
    
    # 理论参数
    bottom_width = 80.0   # 底部宽度 (100 - 2*10)
    bottom_depth = 56.0   # 底部深度 (70 - 2*7)
    top_width = 100.0
    top_depth = 70.0
    height = 10.0
    bottom_z = 5.0
    top_z = 15.0
    
    print(f"\n理论参数:")
    print(f"  底部 (Z={bottom_z}): {bottom_width} x {bottom_depth}")
    print(f"  顶部 (Z={top_z}): {top_width} x {top_depth}")
    print(f"  高度: {height}")
    
    # 计算每个 Z 层的误差
    print(f"\n{'Z':<8} {'实际X':<10} {'理论X':<10} {'X误差':<10} {'实际Y':<10} {'理论Y':<10} {'Y误差':<10}")
    print("-"*80)
    
    max_error_x = 0
    max_error_y = 0
    all_errors = []
    
    for z in side_z[::3]:  # 每3层采样一次
        points_at_z = [p for p in side_wall_points if abs(p[2] - z) < 0.01]
        
        if points_at_z:
            # 获取实际 X/Y 范围 (取正半轴)
            x_positive = [p[0] for p in points_at_z if p[0] > 0]
            y_positive = [p[1] for p in points_at_z if p[1] > 0]
            
            if x_positive and y_positive:
                actual_x = max(x_positive)
                actual_y = max(y_positive)
                
                # 计算理论值 (余弦曲线)
                t = (z - bottom_z) / (top_z - bottom_z)
                if 0 <= t <= 1:
                    # 余弦曲线: inset = total_recess * (1 - cos(pi/2 * t))
                    # 但这里是从底部到顶部，所以是: size = bottom_size + (top_size - bottom_size) * cosine_progress
                    cosine_progress = math.cos(math.pi / 2.0 * (1 - t))  # 0 at bottom, 1 at top
                    
                    theoretical_x = bottom_width / 2 + (top_width / 2 - bottom_width / 2) * cosine_progress
                    theoretical_y = bottom_depth / 2 + (top_depth / 2 - bottom_depth / 2) * cosine_progress
                    
                    error_x = abs(actual_x - theoretical_x)
                    error_y = abs(actual_y - theoretical_y)
                    
                    max_error_x = max(max_error_x, error_x)
                    max_error_y = max(max_error_y, error_y)
                    all_errors.append((error_x, error_y))
                    
                    print(f"{z:<8.3f} {actual_x:<10.4f} {theoretical_x:<10.4f} {error_x:<10.6f} {actual_y:<10.4f} {theoretical_y:<10.4f} {error_y:<10.6f}")
    
    if all_errors:
        avg_error_x = sum(e[0] for e in all_errors) / len(all_errors)
        avg_error_y = sum(e[1] for e in all_errors) / len(all_errors)
        max_error = max(max_error_x, max_error_y)
        
        print("\n" + "="*80)
        print("误差统计:")
        print("="*80)
        print(f"  X 方向:")
        print(f"    最大误差: {max_error_x:.6f} mm")
        print(f"    平均误差: {avg_error_x:.6f} mm")
        print(f"  Y 方向:")
        print(f"    最大误差: {max_error_y:.6f} mm")
        print(f"    平均误差: {avg_error_y:.6f} mm")
        print(f"\n  综合最大误差: {max_error:.6f} mm")
        
        if max_error < 0.001:
            print(f"\n  误差等级: ✓ 优秀 (< 0.001 mm)")
        elif max_error < 0.01:
            print(f"  误差等级: ✓ 良好 (< 0.01 mm)")
        elif max_error < 0.1:
            print(f"  误差等级: ⚠ 可接受 (< 0.1 mm)")
        else:
            print(f"  误差等级: ✗ 较差 (>= 0.1 mm)")

# ==================== 5. 检查实际使用的曲面表示方式 ====================
print("\n" + "="*80)
print("曲面表示方式分析:")
print("="*80)

# 统计所有曲面类型
surface_counts = {
    'PLANE': len(re.findall(r'(?<!\w)PLANE\s*\(', content)),
    'CYLINDRICAL_SURFACE': len(re.findall(r'CYLINDRICAL_SURFACE\s*\(', content)),
    'CONICAL_SURFACE': len(re.findall(r'CONICAL_SURFACE\s*\(', content)),
    'TOROIDAL_SURFACE': len(re.findall(r'TOROIDAL_SURFACE\s*\(', content)),
    'BSPLINE_SURFACE': len(re.findall(r'BSPLINE_SURFACE', content)),
    'RULED_SURFACE': len(re.findall(r'RULED_SURFACE\s*\(', content)),
}

print()
for surf_type, count in surface_counts.items():
    if count > 0:
        print(f"  {surf_type}: {count}")

total = sum(surface_counts.values())
print(f"\n  总计: {total}")

if surface_counts['BSPLINE_SURFACE'] == 0:
    print("\n  ⚠ 注意: test53.step 中未使用 BSpline 曲面!")
    print("  侧壁可能使用:")
    print("    - 多层离散点表示 (BRep 网格)")
    print("    - 直纹面 (RULED_SURFACE)")
    print("    - 或其他解析曲面")

print("\n" + "="*80)
