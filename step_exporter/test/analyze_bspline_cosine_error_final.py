"""
精确计算 test53.step 中 BSpline loft 曲面与理论余弦曲线的误差

根据 C++ 代码分析：
- 使用 BRepOffsetAPI_ThruSections (ruled=false) 创建 BSpline 曲面
- nLayers = 10 (10 个中间层)
- 余弦曲线公式: inset = total_recess * (1 - cos(pi/2 * t))
- 底部 (Z=-5): 100 x 70, cr=20
- 顶部 (Z=10): 80 x 56, cr=20, recess=10
"""
import re
import math
import os

step_file = r'f:\git\blender2step\step_exporter\test53.step'

print("="*80)
print("test53.step - BSpline Loft 与余弦曲线精确误差分析")
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

# ==================== 2. 理论参数 (来自 generate_test53.py) ====================
print("\n" + "="*80)
print("理论参数")
print("="*80)

# 根据 generate_test53.py:
# export_top_shell_filleted_step(..., 100.0, 70.0, 10.0, 2.0, 2.0, 20.0, 1.5, 0.75, 10.0, 3.0, ...)
width = 100.0
depth = 70.0
outer_height = 10.0
top_recess = 10.0
top_offset_y = 3.0

# 在 C++ 代码中，坐标系是以中心为原点
# hh = outer_height / 2.0 = 5.0
# bottom_z = -hh = -5.0
# top_z = hh = 5.0
hh = outer_height / 2.0
bottom_z = -hh
top_z = hh

# 底部尺寸 (完整尺寸)
bot_w = width
bot_d = depth
bot_cr = 20.0
bot_y_offs = top_offset_y  # 底部 Y 偏移

# 顶部尺寸 (缩进后)
top_w = width - 2.0 * top_recess  # 100 - 20 = 80
top_d = depth - 2.0 * top_recess  # 70 - 20 = 50
top_cr = 20.0 - top_recess  # 20 - 10 = 10
top_y_offs = 0.0  # 顶部 Y 偏移为 0

print(f"""
  外部尺寸: {width} x {depth} x {outer_height} mm
  顶部缩进: {top_recess} mm
  Y 轴偏移: {top_offset_y} mm
  
  底部 (Z={bottom_z}):
    尺寸: {bot_w} x {bot_d} mm
    圆角: {bot_cr} mm
    Y 偏移: {bot_y_offs} mm
  
  顶部 (Z={top_z}):
    尺寸: {top_w} x {top_d} mm
    圆角: {top_cr} mm
    Y 偏移: {top_y_offs} mm
""")

# ==================== 3. 计算理论余弦曲线 ====================
print("="*80)
print("计算理论余弦曲线...")
print("="*80)

# 余弦曲线公式
def cosine_inset(t, total_recess):
    """计算 t 时刻的缩进量 (余弦曲线)"""
    return total_recess * (1.0 - math.cos(math.pi / 2.0 * t))

# 计算理论轮廓
def theoretical_profile(t):
    """计算 t 时刻的理论轮廓参数"""
    # t: 0 (bottom) -> 1 (top)
    
    # 线性插值参数
    total_taper_w = bot_w - top_w
    total_taper_d = bot_d - top_d
    total_taper_cr = bot_cr - top_cr
    total_y_offs = top_y_offs - bot_y_offs
    
    # 余弦曲线缩进
    cos_t = 1.0 - math.cos(math.pi / 2.0 * t)
    
    # 插值尺寸
    mid_w = bot_w - total_taper_w * cos_t
    mid_d = bot_d - total_taper_d * cos_t
    mid_cr = bot_cr - total_taper_cr * cos_t
    mid_y_offs = bot_y_offs + total_y_offs * cos_t
    mid_z = bottom_z + (top_z - bottom_z) * t
    
    return {
        't': t,
        'z': mid_z,
        'width': mid_w,
        'depth': mid_d,
        'corner_radius': mid_cr,
        'y_offset': mid_y_offs,
        'half_width': mid_w / 2.0,
        'half_depth': mid_d / 2.0
    }

# 打印关键层
print(f"\n{'t':<6} {'Z':<8} {'宽度':<10} {'深度':<10} {'半宽':<10} {'半深':<10} {'Y偏移':<10}")
print("-"*70)

for t in [0, 0.25, 0.5, 0.75, 1.0]:
    profile = theoretical_profile(t)
    print(f"{t:<6.2f} {profile['z']:<8.3f} {profile['width']:<10.4f} {profile['depth']:<10.4f} "
          f"{profile['half_width']:<10.4f} {profile['half_depth']:<10.4f} {profile['y_offset']:<10.4f}")

# ==================== 4. 分析 STEP 文件中的实际点 ====================
print("\n" + "="*80)
print("分析 STEP 文件中的实际点...")
print("="*80)

# 提取侧壁点 (排除 Z=0 的原点)
side_wall_points = [p for p in points.values() if abs(p[2]) > 0.1]

if side_wall_points:
    # 按 Z 分层
    z_levels = sorted(set([round(p[2], 3) for p in side_wall_points]))
    print(f"\n侧壁层数: {len(z_levels)}")
    print(f"Z 范围: {min(p[2] for p in side_wall_points):.3f} ~ {max(p[2] for p in side_wall_points):.3f}")
    
    # 计算每层的误差
    print(f"\n{'Z':<8} {'t':<6} {'实际X_max':<12} {'理论X':<10} {'X误差':<10} {'实际Y_max':<12} {'理论Y':<10} {'Y误差':<10}")
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
                
                # 计算理论 t 值
                t = (z - bottom_z) / (top_z - bottom_z)
                
                if 0 <= t <= 1:
                    # 获取理论值
                    theory = theoretical_profile(t)
                    theoretical_x = theory['half_width']
                    theoretical_y = theory['half_depth'] + theory['y_offset']
                    
                    error_x = abs(actual_x - theoretical_x)
                    error_y = abs(actual_y - theoretical_y)
                    
                    max_error_x = max(max_error_x, error_x)
                    max_error_y = max(max_error_y, error_y)
                    all_errors_x.append(error_x)
                    all_errors_y.append(error_y)
                    
                    # 只显示部分层
                    if len(z_levels) <= 30 or z_levels.index(z) % 3 == 0:
                        print(f"{z:<8.3f} {t:<6.3f} {actual_x:<12.4f} {theoretical_x:<10.4f} {error_x:<10.6f} "
                              f"{actual_y:<12.4f} {theoretical_y:<10.4f} {error_y:<10.6f}")
    
    if all_errors_x:
        print("\n" + "="*80)
        print("误差统计汇总:")
        print("="*80)
        
        avg_error_x = sum(all_errors_x) / len(all_errors_x)
        avg_error_y = sum(all_errors_y) / len(all_errors_y)
        max_error = max(max_error_x, max_error_y)
        
        print(f"\n  X 方向 (宽度半轴):")
        print(f"    采样点数: {len(all_errors_x)}")
        print(f"    最大误差: {max_error_x:.6f} mm")
        print(f"    平均误差: {avg_error_x:.6f} mm")
        print(f"    最小误差: {min(all_errors_x):.6f} mm")
        
        print(f"\n  Y 方向 (深度半轴):")
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

# ==================== 5. 总结 ====================
print("\n" + "="*80)
print("总结")
print("="*80)

print(f"""
  Blender 中的侧壁曲线: 余弦曲线 (cosine curve)
    公式: inset = total_recess × (1 - cos(π/2 × t))
  
  STEP 中的表示方式: BSpline 曲面 (ThruSections loft, ruled=false)
    中间层数: 10 层
    曲面类型: B-spline smoothing surface
  
  最大误差: {max_error:.6f} mm
  
  误差来源:
  1. ThruSections loft 的 BSpline 近似 (10 层中间点)
  2. 余弦曲线到 BSpline 控制点的转换
  3. 数值计算舍入误差
  
  建议:
  - 如果误差 < 0.01 mm: 精度优秀，无需优化
  - 如果误差 0.01~0.1 mm: 可接受，但可增加 nLayers
  - 如果误差 > 0.1 mm: 需要优化 BSpline 拟合或增加层数
""")

print("="*80)
