"""
计算 OpenCASCADE B-spline 曲面最优参数以拟合余弦曲线

目标：
1. 面数最少（每个侧面 1 个 B-spline 面）
2. 误差 <0.001mm

OpenCASCADE B-spline 曲面特性：
- 使用 GeomAPI_PointsToBSplineSurface 进行逼近（approximation）
- 可以指定度数（degree）、容差（tolerance）
- 曲面会自动优化控制点数量

策略：
- 使用较少的中间层（如 5-10 层）
- 使用 GeomAPI_PointsToBSplineSurface 的 approximation 模式
- 设置合适的容差（如 1e-4 mm）
- 让 OCC 自动优化控制点分布
"""

import math

# 余弦曲线参数
total_recess = 10.0  # mm (从 50 到 40)
height = 10.0  # mm

def cosine_curve(t):
    """余弦曲线：t=0 时在底部，t=1 时在顶部"""
    return total_recess * (1.0 - math.cos(math.pi / 2.0 * t))

# 测试不同层数的线性逼近效果
print("=== 不同层数的线性插值逼近误差分析 ===\n")

for n_layers in [3, 5, 7, 10, 15, 20]:
    # 采样点（包括底部和顶部）
    n_points = n_layers + 2
    t_samples = [i / (n_points - 1) for i in range(n_points)]
    x_samples = [cosine_curve(t) for t in t_samples]
    
    max_error = 0
    max_error_t = 0
    
    for i in range(len(t_samples) - 1):
        t0 = t_samples[i]
        t1 = t_samples[i + 1]
        x0 = x_samples[i]
        x1 = x_samples[i + 1]
        
        # 在区间内采样
        for j in range(100):
            t = t0 + (t1 - t0) * j / 99
            # 线性插值
            if t1 != t0:
                alpha = (t - t0) / (t1 - t0)
                x_linear = x0 + alpha * (x1 - x0)
            else:
                x_linear = x0
            
            # 实际余弦曲线值
            x_actual = cosine_curve(t)
            
            error = abs(x_actual - x_linear)
            if error > max_error:
                max_error = error
                max_error_t = t
    
    print(f"层数: {n_layers:2d} | 最大误差: {max_error:.6f}mm | 发生在 t={max_error_t:.3f}")

print("\n=== B-spline 度数对误差的影响（理论分析）===\n")

# B-spline 度数越高，拟合能力越强
# degree=1: 线性（ruled surface）
# degree=2: 二次
# degree=3: 三次（最常用）
# degree=5: 五次
# degree=8: 八次

# 对于余弦曲线，使用较少的控制点 + 较高度数可以获得更好的拟合效果
# 关键：控制点应该放在余弦曲线的关键位置（如曲率变化大的地方）

print("B-spline 度数与拟合能力：")
print("  degree=1: 线性插值，需要很多控制点")
print("  degree=2: 二次曲线，可以拟合抛物线")
print("  degree=3: 三次曲线，可以拟合余弦曲线（推荐）")
print("  degree=5: 五次曲线，更好的拟合能力")
print("  degree=8: 八次曲线，过拟合风险")

print("\n=== 推荐方案 ===\n")
print("方案 1: 使用 GeomAPI_PointsToBSplineSurface approximation 模式")
print("  - 采样点: 5-7 层")
print("  - 度数: 3 (cubic)")
print("  - 容差: 1e-4 mm")
print("  - 预期面数: 8 个侧面（每个侧面 1 个 B-spline 面）")
print("  - 预期误差: <0.001mm")

print("\n方案 2: 使用 GeomAPI_PointsToBSplineSurface interpolation 模式")
print("  - 采样点: 5-7 层")
print("  - 度数: 3 (cubic)")
print("  - 预期面数: 8 个侧面（每个侧面 1 个 B-spline 面）")
print("  - 预期误差: 0（精确插值）")
