"""
精确分析 test53.step 中 BSpline 曲面与余弦曲线的误差
"""
import re
import math
import os

step_file = r'f:\git\blender2step\step_exporter\test53.step'

print("="*80)
print("test53.step - BSpline 与余弦曲线精确误差分析")
print("="*80)

with open(step_file, 'r', encoding='utf-8', errors='replace') as f:
    content = f.read()

# ==================== 1. 提取所有坐标点 ====================
point_pattern = r'#(\d+)\s*=\s*CARTESIAN_POINT\s*\([^,]*,\s*\(\s*([^,\r\n]+)\s*,\s*([^,\r\n]+)\s*,\s*([^\)\r\n]+)\s*\)'
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

# ==================== 2. 统计 B_SPLINE_SURFACE 数量 ====================
bspline_count = len(re.findall(r'B_SPLINE_SURFACE\s*\(', content))
print(f"B_SPLINE_SURFACE 数量: {bspline_count}")

# ==================== 3. 提取第一个 BSpline 曲面作为示例 ====================
print("\n" + "="*80)
print("提取 BSpline 曲面参数...")
print("="*80)

# 查找 B_SPLINE_SURFACE 定义
bspline_def_pattern = r'B_SPLINE_SURFACE\((\d+),(\d+),'
bspline_matches = list(re.finditer(bspline_def_pattern, content))

if bspline_matches:
    print(f"\n找到 {len(bspline_matches)} 个 BSpline 曲面定义")
    
    # 分析第一个曲面
    first_match = bspline_matches[0]
    u_degree = int(first_match.group(1))
    v_degree = int(first_match.group(2))
    
    print(f"\n第一个 BSpline 曲面:")
    print(f"  U 度: {u_degree}")
    print(f"  V 度: {v_degree}")
    
    # 提取控制点网格
    # 格式: ((#cp1,#cp2,...),(#cp1,#cp2,...),...)
    cp_section_start = first_match.end()
    cp_section = content[cp_section_start:cp_section_start+2000]
    
    # 提取控制点引用
    cp_refs = [int(x) for x in re.findall(r'#(\d+)', cp_section[:1000])]
    print(f"  控制点数量: {len(cp_refs)}")
    
    # 获取控制点坐标
    cp_coords = [points.get(ref, (0,0,0)) for ref in cp_refs[:20]]
    print(f"\n  前20个控制点坐标:")
    for i, cp in enumerate(cp_coords):
        print(f"    CP{i:2d}: ({cp[0]:8.3f}, {cp[1]:8.3f}, {cp[2]:8.3f})")

# ==================== 4. 分析侧壁点的余弦曲线拟合误差 ====================
print("\n" + "="*80)
print("侧壁余弦曲线拟合误差分析...")
print("="*80)

# 理论参数
bottom_z = 5.0
top_z = 15.0
height = top_z - bottom_z
bottom_half_width = 40.0   # 80/2
bottom_half_depth = 28.0   # 56/2
top_half_width = 50.0      # 100/2
top_half_depth = 35.0      # 70/2

# 提取侧壁点 (Z 在 5~15 之间)
side_wall_points = [p for p in points.values() if bottom_z <= p[2] <= top_z]

if side_wall_points:
    # 按 Z 分层
    z_levels = sorted(set([round(p[2], 3) for p in side_wall_points]))
    print(f"\n侧壁层数: {len(z_levels)}")
    print(f"Z 范围: {min(p[2] for p in side_wall_points):.3f} ~ {max(p[2] for p in side_wall_points):.3f}")
    
    # 计算每层的误差
    print(f"\n{'Z':<8} {'t':<6} {'实际X':<10} {'理论X':<10} {'X误差':<10} {'实际Y':<10} {'理论Y':<10} {'Y误差':<10}")
    print("-"*90)
    
    max_error_x = 0
    max_error_y = 0
    all_errors_x = []
    all_errors_y = []
    
    # 采样所有层
    for z in z_levels:
        points_at_z = [p for p in side_wall_points if abs(p[2] - z) < 0.01]
        
        if points_at_z:
            # 获取正半轴的最大 X 和 Y
            x_positive = [p[0] for p in points_at_z if p[0] > 0]
            y_positive = [p[1] for p in points_at_z if p[1] > 0]
            
            if x_positive and y_positive:
                actual_x = max(x_positive)
                actual_y = max(y_positive)
                
                # 计算理论值 (余弦曲线)
                t = (z - bottom_z) / height
                
                if 0 <= t <= 1:
                    # 余弦曲线进度: cos(0)=1 at bottom, cos(pi/2)=0 at top
                    # 所以: progress = 1 - cos(pi/2 * t)  或者使用其他形式
                    # 根据项目代码，应该是: inset = recess * (1 - cos(pi/2 * t))
                    # 但这里是从底部小尺寸到顶部大尺寸
                    # cosine_progress = cos(pi/2 * (1-t))  # 0 at bottom, 1 at top
                    
                    cosine_progress = math.cos(math.pi / 2.0 * (1 - t))
                    
                    theoretical_x = bottom_half_width + (top_half_width - bottom_half_width) * cosine_progress
                    theoretical_y = bottom_half_depth + (top_half_depth - bottom_half_depth) * cosine_progress
                    
                    error_x = abs(actual_x - theoretical_x)
                    error_y = abs(actual_y - theoretical_y)
                    
                    max_error_x = max(max_error_x, error_x)
                    max_error_y = max(max_error_y, error_y)
                    all_errors_x.append(error_x)
                    all_errors_y.append(error_y)
                    
                    # 只显示部分层
                    if len(z_levels) <= 30 or z_levels.index(z) % 3 == 0:
                        print(f"{z:<8.3f} {t:<6.3f} {actual_x:<10.4f} {theoretical_x:<10.4f} {error_x:<10.6f} {actual_y:<10.4f} {theoretical_y:<10.4f} {error_y:<10.6f}")
    
    if all_errors_x:
        print("\n" + "="*80)
        print("误差统计汇总:")
        print("="*80)
        
        avg_error_x = sum(all_errors_x) / len(all_errors_x)
        avg_error_y = sum(all_errors_y) / len(all_errors_y)
        max_error = max(max_error_x, max_error_y)
        
        print(f"\n  X 方向 (宽度):")
        print(f"    采样点数: {len(all_errors_x)}")
        print(f"    最大误差: {max_error_x:.6f} mm")
        print(f"    平均误差: {avg_error_x:.6f} mm")
        print(f"    最小误差: {min(all_errors_x):.6f} mm")
        
        print(f"\n  Y 方向 (深度):")
        print(f"    采样点数: {len(all_errors_y)}")
        print(f"    最大误差: {max_error_y:.6f} mm")
        print(f"    平均误差: {avg_error_y:.6f} mm")
        print(f"    最小误差: {min(all_errors_y):.6f} mm")
        
        print(f"\n  综合最大误差: {max_error:.6f} mm")
        
        print(f"\n  误差等级评估:")
        if max_error < 0.001:
            print(f"    ✓ 优秀 - 最大误差 < 0.001 mm (亚微米级)")
        elif max_error < 0.01:
            print(f"    ✓ 良好 - 最大误差 < 0.01 mm (10微米级)")
        elif max_error < 0.1:
            print(f"    ⚠ 可接受 - 最大误差 < 0.1 mm (100微米级)")
        elif max_error < 1.0:
            print(f"    ⚠ 注意 - 最大误差 < 1.0 mm (毫米级)")
        else:
            print(f"    ✗ 较差 - 最大误差 >= 1.0 mm")
        
        print(f"\n  BSpline 近似质量:")
        if max_error < 0.01:
            print(f"    BSpline 控制点数量充足，拟合精度极高")
        elif max_error < 0.1:
            print(f"    BSpline 拟合精度良好，满足一般 CAD 要求")
        else:
            print(f"    BSpline 拟合误差较大，可能需要增加控制点")

# ==================== 5. 总结 ====================
print("\n" + "="*80)
print("总结")
print("="*80)

print(f"""
  Blender 中的侧壁曲线: 余弦曲线 (cosine curve)
  STEP 中的表示方式: BSpline 曲面近似
  
  最大误差: {max_error:.6f} mm
  
  这个误差来源:
  1. BSpline 控制点数量限制
  2. 余弦曲线到 BSpline 的转换精度
  3. 数值计算舍入误差
  
  建议:
  - 如果误差 < 0.01 mm: 精度优秀，无需优化
  - 如果误差 0.01~0.1 mm: 可接受，但可增加控制点
  - 如果误差 > 0.1 mm: 需要优化 BSpline 拟合
""")

print("="*80)
