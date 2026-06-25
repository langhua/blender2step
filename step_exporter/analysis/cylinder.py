"""Cylinder shape analysis."""
import sys, math
import bmesh
from mathutils import Vector
from ..core.utils import log_to_file
from ..core import _globals as _g

def _analyze_cylinder_from_mesh(obj, context, scale):
    """
    从 mesh 分析识别是否为圆柱/圆锥/空心圆柱类型，并测量所有参数
    
    === 单位约定 (Unit Convention) ===
    内部计算: 米 (Blender 原生单位)
    对象自定义属性 (Custom Properties): 毫米 (mm) — 存储时 ×1000
    分析结果 (返回 dict): 毫米 (mm) — 调用 ×S (S=1000) 缩放
    C++ 导出函数: 毫米 (mm)
    STEP 文件输出: 毫米 (mm)
    
    返回:
        dict: 包含圆柱参数的字典，如果不是圆柱则返回 None
        {
            'type': 'cylinder' | 'cone' | 'hollow_cylinder' | 'hollow_cone',
            'radius': float,          # 圆柱体半径
            'height': float,          # 高度
            'bottom_radius': float,   # 圆锥底部半径
            'top_radius': float,      # 圆锥顶部半径
            'outer_radius': float,    # 空心圆柱外半径
            'inner_radius': float,    # 空心圆柱内半径
            'pos_x': float,
            'pos_y': float,
            'pos_z': float,
        }
    """
    if obj.type != 'MESH':
        return None
    
    import bmesh
    import math
    from collections import defaultdict
    
    log_to_file(f"[STEP Exporter] Analyzing mesh for cylinder: {obj.name}")

    inner_z_data = {}  # 内孔 Z→半径 映射，后续台阶孔检测使用

    depsgraph = context.evaluated_depsgraph_get()
    eval_obj = obj.evaluated_get(depsgraph)
    mesh_data = eval_obj.data
    
    bm = bmesh.new()
    bm.from_mesh(mesh_data)
    bm.verts.ensure_lookup_table()
    
    vertices = bm.verts
    if len(vertices) < 20:
        log_to_file(f"[STEP Exporter] Too few vertices ({len(vertices)}), not a cylinder")
        bm.free()
        return None
    
    # 收集所有顶点的原始坐标
    all_verts = [(v.co.x, v.co.y, v.co.z) for v in vertices]
    
    # 按 Z 坐标分组
    z_layers = defaultdict(list)
    for x, y, z in all_verts:
        z_key = round(z / 0.0001) * 0.0001
        z_layers[z_key].append((x, y))
    
    sorted_z = sorted(z_layers.keys())
    if len(sorted_z) < 2:
        log_to_file(f"[STEP Exporter] Not enough z-levels ({len(sorted_z)}), not a cylinder")
        bm.free()
        return None
    
    # 过滤掉包含顶点数过少的层（如中心点）
    filtered_sorted_z = [zl for zl in sorted_z if len(z_layers[zl]) >= 4]
    if len(filtered_sorted_z) < 2:
        log_to_file(f"[STEP Exporter] Not enough rich z-levels ({len(filtered_sorted_z)}), not a cylinder")
        bm.free()
        return None
    
    sorted_z = filtered_sorted_z
    
    min_z = sorted_z[0]
    max_z = sorted_z[-1]
    height = max_z - min_z
    
    # 计算中心轴 - 使用底层（最干净的切面）来计算中心
    # 这样即使顶部有倒角/圆角也不影响中心计算
    bottom_z = sorted_z[0]
    top_z = sorted_z[-1]
    
    bottom_pts = z_layers[bottom_z]
    center_x = sum(p[0] for p in bottom_pts) / len(bottom_pts)
    center_y = sum(p[1] for p in bottom_pts) / len(bottom_pts)
    
    # 分析每层的半径分布
    
    def compute_radii(layer_pts):
        """计算层内各点到中心的距离"""
        return [math.sqrt((p[0] - center_x)**2 + (p[1] - center_y)**2) for p in layer_pts]
    
    bottom_radii = compute_radii(z_layers[bottom_z])
    top_radii = compute_radii(z_layers[top_z])
    
    if len(bottom_radii) < 4 or len(top_radii) < 4:
        log_to_file(f"[STEP Exporter] Too few points at bottom/top")
        bm.free()
        return None
    
    # 使用中位数作为半径估计（比均值更抗噪）
    bottom_radii_sorted = sorted(bottom_radii)
    top_radii_sorted = sorted(top_radii)
    
    mid_idx_b = len(bottom_radii_sorted) // 2
    mid_idx_t = len(top_radii_sorted) // 2
    
    bottom_radius = bottom_radii_sorted[mid_idx_b]
    top_radius = top_radii_sorted[mid_idx_t]
    
    # 提前检测是否为空心结构（两圈顶点：外圈+内圈）
    # 如果半径分布有两簇，说明是空心圆柱
    def has_two_clusters(radii_sorted):
        n = len(radii_sorted)
        if n < 16:
            return False, radii_sorted
        # 检查最大值和最小值之间是否有明显 gap
        min_r = radii_sorted[0]
        max_r = radii_sorted[-1]
        if max_r - min_r < max_r * 0.15:
            return False, radii_sorted
        # 找最佳分割点：在半径排序序列中找最大 gap
        best_gap = 0
        best_split = n // 2
        for i in range(n // 4, 3 * n // 4):
            gap = radii_sorted[i] - radii_sorted[i - 1]
            if gap > best_gap:
                best_gap = gap
                best_split = i
        if best_gap > max_r * 0.08:
            return True, radii_sorted[best_split:]  # 返回外圈（较大的值）
        return False, radii_sorted
    
    bottom_is_hollow, bottom_outer_radii = has_two_clusters(bottom_radii_sorted)
    top_is_hollow, top_outer_radii = has_two_clusters(top_radii_sorted)
    might_be_hollow = bottom_is_hollow or top_is_hollow
    
    # 修复：当顶部有孔洞（如标准圆柱顶部打孔）时，has_two_clusters可能因
    # 三角面片中间顶点过多而无法检测到两簇。此时用简单阈值法提取外圈半径。
    if not top_is_hollow and not might_be_hollow:
        top_min_r = top_radii_sorted[0]
        top_max_r = top_radii_sorted[-1]
        if top_max_r - top_min_r > top_max_r * 0.15 and top_min_r > top_max_r * 0.1:
            mid_r = (top_min_r + top_max_r) / 2.0
            top_outer = [r for r in top_radii_sorted if r > mid_r]
            if len(top_outer) >= 4:
                top_is_hollow = True
                might_be_hollow = True
                top_outer_radii = sorted(top_outer)
                log_to_file(f"[STEP Exporter] Detected ring at top via threshold: outer_r={top_outer_radii[len(top_outer_radii)//2]:.3f}")
    
    # 如果是空心结构，用外圈半径重新计算
    if might_be_hollow:
        bo_sorted = sorted(bottom_outer_radii)
        to_sorted = sorted(top_outer_radii)
        bottom_radius = bo_sorted[len(bo_sorted) // 2]
        top_radius = to_sorted[len(to_sorted) // 2]
    
    # 修复：当底部有清晰两簇但顶部因地貌/倒角失去了簇结构时，
    # 从顶部向下扫描，找到最靠近bevel的两簇层来修正top_radius
    # （向下扫描找到的第一个两簇层最接近bevel底部，半径最准）
    if bottom_is_hollow and not top_is_hollow:
        for scan_idx in range(len(sorted_z) - 2, len(sorted_z) // 3, -1):
            scan_zl = sorted_z[scan_idx]
            scan_radii = sorted(compute_radii(z_layers[scan_zl]))
            scan_is_cluster, scan_outer = has_two_clusters(scan_radii)
            if scan_is_cluster:
                so_sorted = sorted(scan_outer)
                top_radius = so_sorted[len(so_sorted) // 2]
                top_outer_radii = scan_outer  # 同时更新用于后续STD检查
                top_is_hollow = True  # 标记为已找到簇，避免STD检查用错数据
                log_to_file(f"[STEP Exporter] Corrected top_radius via cluster scan at z={scan_zl:.2f}: {top_radius:.3f}")
                break
    
    # 半径标准差判断是否为规则圆形
    def radius_std(radii):
        mean_r = sum(radii) / len(radii)
        variance = sum((r - mean_r)**2 for r in radii) / len(radii)
        return math.sqrt(variance)
    
    # 用外圈半径计算标准差（如果空心）
    std_b = radius_std(bottom_outer_radii if might_be_hollow else bottom_radii)
    std_t = radius_std(top_outer_radii if might_be_hollow else top_radii)
    
    # 修复：底部有圆倒角/孔洞时，底部Z层混合了倒角+孔洞+外壁顶点导致半径方差高。
    # 此时顶部通常是干净的单层圆。若顶部方差低，用顶部半径作为圆柱体半径。
    # 不能简单向上扫描找"干净层"——靠近底部的干净层可能是内孔壁（半径偏小），
    # 会被误判为锥体底部。
    if std_b > bottom_radius * 0.15 and std_t <= top_radius * 0.15:
        # 顶部干净，底部混乱 → 恒定半径圆柱，用顶部数据替代底部
        bottom_radius = top_radius
        bottom_outer_radii = top_outer_radii if might_be_hollow else top_radii
        std_b = std_t
        # 标记为可能空心：后续中间层检测需要提取外圈簇，避免内孔壁污染半径范围检查
        if not might_be_hollow:
            might_be_hollow = True
        log_to_file(f"[STEP Exporter] Bottom variance high (std_b={std_b:.4f}), top is clean (r={top_radius:.4f}), using top radius for cylinder body")
    
    # 标准差不大于平均半径的 15% 才认为是规则圆柱
    # 有存储属性（孔/倒角）时放宽：这些特征会导致Z层混合，方差偏高
    has_stored_features = (obj.get('hole_type') or obj.get('hole_position') or obj.get('chamfer_type')) if hasattr(obj, 'get') else False
    if has_stored_features:
        # 放宽到 50%，允许倒角+孔洞导致的顶点混合
        if std_b > bottom_radius * 0.5 and std_t > top_radius * 0.5:
            log_to_file(f"[STEP Exporter] Radius variance too high even with stored features: std_b={std_b:.3f} std_t={std_t:.3f}")
            bm.free()
            return None
    elif std_b > bottom_radius * 0.15 or std_t > top_radius * 0.15:
        log_to_file(f"[STEP Exporter] Radius variance too high: std_b={std_b:.3f} std_t={std_t:.3f}")
        bm.free()
        return None
    
    # 半径不能太小
    if bottom_radius < 0.001 or top_radius < 0.001:
        log_to_file(f"[STEP Exporter] Radius too small: b={bottom_radius:.3f} t={top_radius:.3f}")
        bm.free()
        return None
    
    # 高度不能太小
    if height < 0.0005:
        log_to_file(f"[STEP Exporter] Height too small: {height:.3f}")
        bm.free()
        return None
    
    # 检查中间区域是否存在非圆形特征（排除被凹槽/切割/布尔运算修改过的圆柱）
    # 策略: 合并中间高度范围内所有顶点的半径（无论每层顶点多少），
    #        避免因凹槽产生的稀疏层（每层 <4 顶点）被过滤掉
    z_mid_low = min_z + height * 0.20
    z_mid_high = max_z - height * 0.20
    
    # 如果有凹槽定制属性，提前提取凹槽参数（不依赖中间层检测结果）
    has_groove_custom = (obj.get('step_groove_depth', 0) or 0) > 0
    groove_params = {}
    if has_groove_custom:
        groove_params = {
            'groove_depth': obj['step_groove_depth'],
            'groove_bottom_width': obj.get('step_groove_bottom_width', 0),
            'groove_top_width': obj.get('step_groove_top_width', 0),
            'groove_extrusion_length': obj.get('step_groove_extrusion_length', 0),
        }
    
    # 阶梯孔检测
    has_stepped_hole = obj.get('hole_is_stepped', False)
    stepped_hole_params = {}
    if has_stepped_hole:
        stepped_hole_params = {
            'stepped_large_r': obj.get('hole_stepped_large_r', 0),
            'stepped_large_h': obj.get('hole_stepped_large_h', 0),
            'stepped_small_r': obj.get('hole_stepped_small_r', 0),
        }

    mid_all_radii = []
    for zl_key in z_layers:
        if z_mid_low <= zl_key <= z_mid_high and len(z_layers[zl_key]) >= 1:
            mid_all_radii.extend(compute_radii(z_layers[zl_key]))
    
    if len(mid_all_radii) >= 16:
        mid_sorted = sorted(mid_all_radii)
        # 检测中间区域是否有内外两簇（如双端盲孔圆柱的外壁+内孔壁）
        mid_is_cluster, mid_outer_radii = has_two_clusters(mid_sorted)
        if mid_is_cluster and len(mid_outer_radii) >= 8:
            # 使用外簇（更大半径的那簇）进行圆度检测
            mid_sorted = mid_outer_radii
        # 空心结构: 外圈递归检测子簇（凹槽底面 vs 圆柱表面）
        if might_be_hollow:
            is_cluster, outer_radii = has_two_clusters(mid_sorted)
            if is_cluster and len(outer_radii) >= 8:
                outer_sorted = sorted(outer_radii)
                sub_cluster, _ = has_two_clusters(outer_sorted)
                if sub_cluster:
                    if has_groove_custom:
                        log_to_file(f"[STEP Exporter] Middle region has sub-clusters (groove), "
                                    f"using custom groove parameters for parametric export")
                    else:
                        stored_hole_pos2 = obj.get('hole_position') if hasattr(obj, 'get') else None
                        if stored_hole_pos2:
                            log_to_file(f"[STEP Exporter] Middle region has sub-clusters but has stored holes, continuing")
                        else:
                            log_to_file(f"[STEP Exporter] Middle region outer ring has sub-clusters, "
                                        f"mesh has cuts/grooves")
                            bm.free()
                            return None
                mid_sorted = outer_radii
        mean_r = sum(mid_sorted) / len(mid_sorted)
        range_r = max(mid_sorted) - min(mid_sorted)
        if range_r > mean_r * 0.08:
            if has_groove_custom:
                log_to_file(f"[STEP Exporter] Middle region not cleanly circular (groove detected), "
                            f"using custom groove parameters for parametric export")
            else:
                # 检查是否有孔洞存储属性——双端盲孔会破坏中段圆形检测
                stored_hole_pos = obj.get('hole_position') if hasattr(obj, 'get') else None
                if stored_hole_pos:
                    log_to_file(f"[STEP Exporter] Middle region not cleanly circular but has stored hole_position={stored_hole_pos}, continuing")
                else:
                    log_to_file(f"[STEP Exporter] Middle region not cleanly circular "
                                f"(range={range_r:.3f} > {mean_r*0.08:.3f}), mesh has cuts/grooves")
                    bm.free()
                    return None
    
    log_to_file(f"[STEP Exporter] Detected: center=({center_x:.3f},{center_y:.3f}), "
                f"bottom_r={bottom_radius:.3f} top_r={top_radius:.3f}, height={height:.3f}")
    
    # 判断圆柱类型
    radius_ratio = top_radius / bottom_radius if bottom_radius > 0 else 1.0
    
    # 检查是否为空心（在内壁也有顶点层）
    is_hollow = False
    inner_radius = 0.0
    inner_top_radius = 0.0
    
    # 预先计算中段层的范围（两个分支都要用）
    hmid_start = max(0, len(sorted_z) // 4)
    hmid_end = min(len(sorted_z), 3 * len(sorted_z) // 4)
    if hmid_end - hmid_start < 2:
        hmid_start = 0
        hmid_end = len(sorted_z)
    
    # 如果底部或顶部已检测到两簇结构，直接确认空心
    if might_be_hollow or bottom_is_hollow or top_is_hollow:
        # 从底层和顶层分别提取内外半径
        def layer_inner_outer_radii(zl):
            pts = z_layers[zl]
            radii = sorted(compute_radii(pts))
            is_cluster, outer = has_two_clusters(radii)
            if is_cluster:
                n = len(radii)
                inner = radii[:n - len(outer)]
                inner_r = sorted(inner)[len(inner)//2] if inner else 0
                outer_r = sorted(outer)[len(outer)//2] if outer else 0
                return inner_r, outer_r
            else:
                return 0.0, sorted(radii)[len(radii)//2]
        
        # 底部内外半径
        inner_b, outer_b = layer_inner_outer_radii(sorted_z[0])
        # 顶部内外半径
        inner_t, outer_t = layer_inner_outer_radii(sorted_z[-1])
        
        if inner_b > 0.01 and inner_t > 0.01:
            inner_radius = inner_b
            inner_top_radius = inner_t
            outer_radius = max(outer_b, outer_t)
            is_hollow = True
            log_to_file(f"[STEP Exporter] Hollow detected: inner_r(bottom)={inner_b:.3f} inner_r(top)={inner_t:.3f} outer_r={outer_radius:.3f}")
        elif inner_b > 0.01 and bottom_is_hollow:
            # 底部有清晰两簇，但顶部没有（因倒角/圆角破坏了顶部簇结构）
            # 从顶部向下扫描，找到最靠近bevel的两簇层
            for scan_idx in range(len(sorted_z) - 2, len(sorted_z) // 3, -1):
                scan_zl = sorted_z[scan_idx]
                scan_radii = sorted(compute_radii(z_layers[scan_zl]))
                scan_is_cluster, scan_outer = has_two_clusters(scan_radii)
                if scan_is_cluster:
                    n_sc = len(scan_radii)
                    scan_inner = scan_radii[:n_sc - len(scan_outer)]
                    inner_t = sorted(scan_inner)[len(scan_inner)//2] if scan_inner else 0.0
                    outer_t = sorted(scan_outer)[len(scan_outer)//2] if scan_outer else 0.0
                    if inner_t > 0.01:
                        inner_radius = inner_b
                        inner_top_radius = inner_t
                        outer_radius = max(outer_b, outer_t)
                        is_hollow = True
                        log_to_file(f"[STEP Exporter] Hollow detected (scan near wall): inner_r(bottom)={inner_b:.3f} inner_r(top)={inner_t:.3f} outer_r={outer_radius:.3f} at z={scan_zl:.2f}")
                        break
    else:
        # 外层检测未发现两簇，再检查中间层
        hollow_evidence = 0
        
        for i in range(hmid_start, hmid_end):
            zl = sorted_z[i]
            pts = z_layers[zl]
            if len(pts) < 8:
                continue
            all_radii = sorted(compute_radii(pts))
            min_r = all_radii[0]
            max_r = all_radii[-1]
            if max_r - min_r > max_r * 0.2 and max_r > 3.0:
                hollow_evidence += 1
        
        if hollow_evidence >= 2:
            all_mid_radii = []
            for i in range(hmid_start, hmid_end):
                all_mid_radii.extend(compute_radii(z_layers[sorted_z[i]]))
            all_mid_radii_sorted = sorted(all_mid_radii)
            
            gap_idx = len(all_mid_radii_sorted) // 2
            inner_vals = all_mid_radii_sorted[:gap_idx]
            outer_vals = all_mid_radii_sorted[gap_idx:]
            
            inner_radius = sorted(inner_vals)[len(inner_vals)//2]
            outer_radius = sorted(outer_vals)[len(outer_vals)//2]
            inner_top_radius = inner_radius * radius_ratio if (radius_ratio < 0.99 or radius_ratio > 1.01) else inner_radius
            is_hollow = True
            log_to_file(f"[STEP Exporter] Hollow detected (mid-layer): inner_r={inner_radius:.3f} outer_r={outer_radius:.3f}")
    
    # ==== Chamfer/Fillet 过渡检测 ====
    # 策略：
    #   Blender标准圆柱体仅有顶部/底部顶点，中间无分层。
    #   关键判断: 该物体是圆柱本体(大面积恒定半径)还是圆锥本体？
    #     - 圆柱本体: >60%的高度内半径恒定 → 查找顶部/底部过渡
    #     - 圆锥本体: 半径线性变化 → 不检测过渡(锥形就是其本体形状)
    #   过渡区至少2层才分析(chamfer: 过渡起点+终点, fillet: 多种半径层)
    top_feature = None
    top_feature_size = 0.0
    bottom_feature = None
    bottom_feature_size = 0.0
    body_radius = bottom_radius
    
    def _layer_outer_radius(pts):
        radii = sorted(compute_radii(pts))
        n = len(radii)
        if n < 4:
            return None
        if n >= 16:
            is_cluster, outer_vals = has_two_clusters(radii)
            if is_cluster:
                return sorted(outer_vals)[len(outer_vals)//2]
        return sum(radii[n - n//4:]) / max(1, n//4)
    
    # 逐层计算半径
    z_radius_data = {}
    z_max_radius = {}  # 每层最大半径（用于检测外壁是否存在）
    for zl in sorted_z:
        r = _layer_outer_radius(z_layers[zl])
        if r is not None:
            z_radius_data[zl] = r
        # 计算该层最大半径
        all_r = compute_radii(z_layers[zl])
        if len(all_r) > 0:
            z_max_radius[zl] = max(all_r)
    
    # DEBUG: 输出 z-level 和半径数据
    log_to_file(f"[STEP Exporter]   detect: {len(sorted_z)} z-levels, {len(z_radius_data)} with radius data")
    for zl in sorted_z:
        r = z_radius_data.get(zl)
        max_r = z_max_radius.get(zl, 0)
        if r is not None:
            log_to_file(f"[STEP Exporter]     z={zl:.6f} r={r:.6f} max_r={max_r:.6f}")
    log_to_file(f"[STEP Exporter]   detect: bottom_r={bottom_radius:.6f} top_r={top_radius:.6f} height={height:.6f}")
    
    # 底部孔洞修正：如果底部因盲孔/通孔干扰被错误设为顶部半径，用max_r恢复真实锥体底部半径
    early_stored_pos = obj.get('hole_position') if hasattr(obj, 'get') else None
    early_stored_type = obj.get('hole_type') if hasattr(obj, 'get') else None
    has_hole = early_stored_pos in ('bottom', 'both', 'top') or early_stored_type == 'through'
    if has_hole and len(sorted_z) > 0:
        bottom_max_r = z_max_radius.get(sorted_z[0], 0)
        top_max_r = z_max_radius.get(sorted_z[-1], 0)
        # Check if max_r at either end differs from current radius (indicating hole interference)
        btm_changed = bottom_max_r > 0 and abs(bottom_max_r - bottom_radius) / max(bottom_radius, 0.001) > 0.15
        top_changed = top_max_r > 0 and abs(top_max_r - top_radius) / max(top_radius, 0.001) > 0.15
        if btm_changed or top_changed:
            old_b = bottom_radius; old_t = top_radius
            if btm_changed: bottom_radius = bottom_max_r
            if top_changed: top_radius = top_max_r
            log_to_file(f"[STEP Exporter]   Hole max_r correction: b={old_b:.4f}->{bottom_radius:.4f} t={old_t:.4f}->{top_radius:.4f} (ratio={top_radius/bottom_radius:.3f})")
    
    # 1. 从底部向上找恒定半径区域 → 判断是否为圆柱本体
    body_end_z = sorted_z[0]
    for zl in sorted_z:
        r = z_radius_data.get(zl)
        if r is None:
            continue
        if abs(r - bottom_radius) / max(bottom_radius, 0.01) < 0.01:
            body_end_z = zl
        else:
            break
    
    body_portion = (body_end_z - sorted_z[0]) / height if height > 0 else 0
    cylindrical_body = body_portion > 0.6
    # Grooved cylinders have non-circular mid-region but are still cylindrical
    if has_groove_custom:
        cylindrical_body = True
        # Also run top-down body detection to find correct body boundaries
        # (bottom-up may stop early due to fillet/chamfer at the bottom end)
        body_start_z = sorted_z[-1]
        for zl in reversed(sorted_z):
            r = z_radius_data.get(zl)
            if r is None:
                continue
            if abs(r - top_radius) / max(top_radius, 0.01) < 0.01:
                body_start_z = zl
            else:
                break
        top_body_portion = (sorted_z[-1] - body_start_z) / height if height > 0 else 0
        if top_body_portion > 0.3:  # looser threshold for grooved cylinders
            body_radius = top_radius
            body_end_z = body_start_z
    
    # 同时也检查顶部向下是否有恒定半径区域
    if not cylindrical_body:
        body_start_z = sorted_z[-1]
        for zl in reversed(sorted_z):
            r = z_radius_data.get(zl)
            if r is None:
                continue
            if abs(r - top_radius) / max(top_radius, 0.01) < 0.01:
                body_start_z = zl
            else:
                break
        top_body_portion = (sorted_z[-1] - body_start_z) / height if height > 0 else 0
        if top_body_portion > 0.6:
            cylindrical_body = True
            body_radius = top_radius
            # swap direction: body is at top, transition at bottom
            body_end_z = body_start_z
    
    # 修复：圆柱顶部打孔时，孔洞表面顶点半径远小于本体半径，
    # 导致cylindrical_body=False（"本体"区域只有底部1层）。
    # 检测这种模式：底部半径大、上方第一层半径骤降>40% → 圆柱带孔洞，非锥体/倒角
    hole_pattern_detected = False
    hole_position = 'top'  # 默认顶部盲孔，底部盲孔时检测为 'bottom'
    hole_radius = 0.0
    hole_depth = 0.0
    hole_depth_top = 0.0  # 双端孔时顶部孔深
    
    # 通孔/盲孔检测：检查对象上存储的自定义属性
    # 注意: 自定义属性以毫米 (mm) 存储，需 ×0.001 转换为米进行内部分析
    stored_hole_type = obj.get('hole_type') if hasattr(obj, 'get') else None
    stored_pos = obj.get('hole_position') if hasattr(obj, 'get') else None
    log_to_file(f"[STEP Exporter]   Stored props: hole_type={stored_hole_type}, hole_position={stored_pos}, is_tapered={obj.get('hole_is_tapered') if hasattr(obj,'get') else None}")
    if stored_hole_type in ('through', 'through_inv') or stored_pos == 'through':
        hole_pattern_detected = True
        hole_position = 'through'
        stored_hr = obj.get('hole_radius') if hasattr(obj, 'get') else None
        hole_radius = stored_hr * 0.001 if stored_hr else body_radius * 0.35
        hole_depth = height
        log_to_file(f"[STEP Exporter]   Through-hole detected from stored property, r={hole_radius:.4f}")
    elif stored_pos in ('top', 'bottom', 'both'):
        hole_pattern_detected = True
        hole_position = stored_pos
        stored_hr = obj.get('hole_radius') if hasattr(obj, 'get') else None
        stored_hd = obj.get('hole_depth') if hasattr(obj, 'get') else None
        hole_radius = stored_hr * 0.001 if stored_hr else body_radius * 0.35
        hole_depth = stored_hd * 0.001 if stored_hd else height * 0.5
        if stored_pos == 'both':
            hole_depth_top = hole_depth
        log_to_file(f"[STEP Exporter]   Blind hole from stored property: pos={stored_pos} r={hole_radius:.4f} d={hole_depth:.4f}")
    elif stored_pos in ('stepped', 'tapered_stepped'):
        hole_pattern_detected = True
        hole_position = stored_pos  # 'stepped' or 'tapered_stepped'
        log_to_file(f"[STEP Exporter]   Stepped/tapered-stepped hole from stored property: type={stored_pos}")
    
    # 强制圆柱体判断：两端半径接近且顶部干净时，即使中间z层缺少外壁顶点
    # （如盲孔圆柱的外壁仅有顶部/底部顶点），也认定为恒定半径圆柱。
    # 同时检测底部盲孔：底部顶点数>>顶部顶点数 → 孔在底部。
    # 注意：如果已检测到通孔，跳过盲孔分析
    if hole_position != 'through' and not cylindrical_body and abs(bottom_radius - top_radius) / max(bottom_radius, 0.01) < 0.02 and std_t <= top_radius * 0.05:
        cylindrical_body = True
        body_radius = (bottom_radius + top_radius) / 2.0
        body_end_z = sorted_z[-1]
        log_to_file(f"[STEP Exporter]   Forced cylindrical body: ends same radius (b={bottom_radius:.3f} t={top_radius:.3f}), top clean")
        
        # 底部盲孔检测：强制圆柱体意味着底部有孔洞特征
        b_radii = sorted(compute_radii(z_layers[sorted_z[0]]))
        inner_n = max(4, len(b_radii) // 8)
        inner_r = sorted(b_radii[:inner_n])[inner_n//2]
        
        # 优先使用对象上存储的精确孔半径（避免 z-level 分析的 inner_r 偏差）
        stored_hr = obj.get('hole_radius') if hasattr(obj, 'get') else None
        stored_pos2 = obj.get('hole_position') if hasattr(obj, 'get') else None
        if stored_hr is not None and stored_pos2 in ('top', 'bottom', 'both') and stored_hr > 0.5:
            inner_r = stored_hr * 0.001
            log_to_file(f"[STEP Exporter]   Using stored hole_radius={inner_r:.4f} from object property")
        
        # 从底部向上扫描找内孔结束位置（用max半径判断外壁是否存在）
        hole_end_bottom = sorted_z[0]
        for zl in sorted_z[1:]:
            r = z_radius_data.get(zl)
            max_r = z_max_radius.get(zl, 0)
            # 内孔z层：外半径小 且 没有外壁顶点
            if r is not None and r < body_radius * 0.7 and max_r < body_radius * 0.85:
                hole_end_bottom = zl
        
        # 从顶部向下扫描找内孔开始位置
        hole_start_top = sorted_z[-1]
        for zl in reversed(sorted_z[:-1]):
            r = z_radius_data.get(zl)
            max_r = z_max_radius.get(zl, 0)
            if r is not None and r < body_radius * 0.7 and max_r < body_radius * 0.85:
                hole_start_top = zl
        
        bottom_hole_d = hole_end_bottom - sorted_z[0]
        top_hole_d = sorted_z[-1] - hole_start_top
        
        # 判断两端是否有孔
        btm_has_hole = inner_r > 0.0005 and bottom_hole_d > height * 0.05
        top_has_hole = inner_r > 0.0005 and top_hole_d > height * 0.05
        
        if btm_has_hole and top_has_hole:
            # 两端都有孔：可能重叠（贯通/相交）也可能不重叠（中间有实体段）
            if hole_end_bottom >= hole_start_top:
                # 孔范围交叉/重叠：用max半径重新扫描找实际孔底
                btm_end = sorted_z[0]
                for zl in sorted_z[1:]:
                    r = z_radius_data.get(zl)
                    max_r = z_max_radius.get(zl, 0)
                    if r is not None and r < body_radius * 0.7 and max_r < body_radius * 0.85:
                        btm_end = zl
                    else:
                        break
                top_start = sorted_z[-1]
                for zl in reversed(sorted_z[:-1]):
                    r = z_radius_data.get(zl)
                    max_r = z_max_radius.get(zl, 0)
                    if r is not None and r < body_radius * 0.7 and max_r < body_radius * 0.85:
                        top_start = zl
                    else:
                        break
                # 如果扫描到对端（无外壁z层），用max半径找外壁首现位置作为分界
                if btm_end >= sorted_z[-1] * 0.99 or top_start <= sorted_z[0] * 1.01:
                    # 找中间区域第一个有外壁的z层
                    mid_z = (sorted_z[0] + sorted_z[-1]) / 2
                    outer_zls = [zl for zl in sorted_z[1:-1]
                                 if z_max_radius.get(zl, 0) > body_radius * 0.85]
                    if outer_zls:
                        # 用最靠近中点的外壁z层作为分界
                        boundary_z = min(outer_zls, key=lambda zl: abs(zl - mid_z))
                        btm_end = boundary_z
                        top_start = boundary_z
                        log_to_file(f"[STEP Exporter]   Both scans reached opposite ends, using max-radius boundary z={boundary_z:.4f}")
                    else:
                        # 完全没有外壁z层：回退到中点
                        btm_end = mid_z
                        top_start = mid_z
                        log_to_file(f"[STEP Exporter]   No outer-wall z-levels found, using midpoint z={mid_z:.4f}")
                bottom_hole_d = btm_end - sorted_z[0]
                top_hole_d = sorted_z[-1] - top_start
            # else: 不重叠，bottom_hole_d 和 top_hole_d 已在上方扫描中获得
            
            if bottom_hole_d > height * 0.05 and top_hole_d > height * 0.05:
                # 优先使用存储的 hole_position（避免误判为双端孔）
                stored_pos3 = obj.get('hole_position') if hasattr(obj, 'get') else None
                # CRITICAL: Use stored hole_depth when available. z-level scanning can be
                # misled by inner hole walls (e.g., top blind hole detected as dual-hole).
                stored_hd3 = obj.get('hole_depth') if hasattr(obj, 'get') else None
                if stored_pos3 == 'top':
                    hole_pattern_detected = True
                    hole_position = 'top'
                    hole_radius = inner_r  # already in meters (converted at forced-cyl-body section)
                    hole_depth = stored_hd3 * 0.001 if stored_hd3 else top_hole_d
                    log_to_file(f"[STEP Exporter]   Using stored hole_position=top, overriding dual-blind detection")
                elif stored_pos3 == 'bottom':
                    hole_pattern_detected = True
                    hole_position = 'bottom'
                    hole_radius = inner_r  # already in meters
                    hole_depth = stored_hd3 * 0.001 if stored_hd3 else bottom_hole_d
                    log_to_file(f"[STEP Exporter]   Using stored hole_position=bottom, overriding dual-blind detection")
                elif stored_pos3 in ('stepped', 'tapered_stepped'):
                    hole_pattern_detected = True
                    hole_position = stored_pos3  # keep 'stepped' or 'tapered_stepped'
                    log_to_file(f"[STEP Exporter]   Using stored hole_position={stored_pos3}, overriding dual-blind detection")
                else:
                    hole_pattern_detected = True
                    hole_position = 'both'
                    hole_radius = inner_r  # already in meters
                    stored_depth = obj.get('hole_depth') if hasattr(obj, 'get') else None
                    if stored_depth is not None:
                        hole_depth = stored_depth * 0.001  # mm → m
                        hole_depth_top = stored_depth * 0.001  # mm → m
                        log_to_file(f"[STEP Exporter]   Using stored hole_depth={stored_depth:.4f} from object property")
                    else:
                        hole_depth = bottom_hole_d
                        hole_depth_top = top_hole_d
                    log_to_file(f"[STEP Exporter]   Dual blind holes: inner_r={inner_r:.4f} btm_d={hole_depth:.4f} ({hole_depth/height*100:.0f}%) top_d={hole_depth_top:.4f} ({hole_depth_top/height*100:.0f}%)")
            else:
                log_to_file(f"[STEP Exporter]   Hole spans cylinder but depths too small — exporting as solid cylinder")
        elif btm_has_hole:
            hole_pattern_detected = True
            hole_position = 'bottom'
            hole_radius = inner_r  # already in meters
            # Prefer stored hole_depth over z-level scan
            stored_hd_btm = obj.get('hole_depth') if hasattr(obj, 'get') else None
            hole_depth = stored_hd_btm * 0.001 if stored_hd_btm else bottom_hole_d
            log_to_file(f"[STEP Exporter]   Bottom blind hole: inner_r={inner_r:.4f} hole_depth={hole_depth:.4f} ({hole_depth/height*100:.0f}%)")
        elif top_has_hole:
            hole_pattern_detected = True
            hole_position = 'top'
            hole_radius = inner_r  # already in meters
            # Prefer stored hole_depth over z-level scan
            stored_hd_top = obj.get('hole_depth') if hasattr(obj, 'get') else None
            hole_depth = stored_hd_top * 0.001 if stored_hd_top else top_hole_d
            log_to_file(f"[STEP Exporter]   Top blind hole: inner_r={inner_r:.4f} hole_depth={hole_depth:.4f} ({hole_depth/height*100:.0f}%)")
        else:
            log_to_file(f"[STEP Exporter]   Blind hole check: inner_r={inner_r:.6f} btm_d={bottom_hole_d:.6f} top_d={top_hole_d:.6f} — not detected")
    
    if not cylindrical_body and bottom_radius > 0.01:
        above_zls = [zl for zl in sorted_z if zl > body_end_z and zl in z_radius_data]
        if above_zls:
            above_r_first = z_radius_data[above_zls[0]]
            if above_r_first < bottom_radius * 0.6:
                # Check if this is a cone (radius changes significantly) vs blind hole
                # Bidirectional: cone can narrow upward OR widen upward
                ratio_down = top_radius / bottom_radius if bottom_radius > 0 else 1.0
                if ratio_down < 0.85 or ratio_down > 1.0 / 0.85:
                    log_to_file(f"[STEP Exporter]   Cone detected (bR={bottom_radius:.3f} tR={top_radius:.3f} ratio={ratio_down:.3f}), not blind hole")
                    if hole_pattern_detected:
                        log_to_file(f"[STEP Exporter]   Cone+hole detected, using cone_blind_hole path")
                        _is_cone_body = True  # flag for result construction
                else:
                    log_to_file(f"[STEP Exporter]   Hole pattern detected: bottom_r={bottom_radius:.3f} above_r={above_r_first:.3f}, treating as cylinder")
                    cylindrical_body = True
                    body_radius = max(bottom_radius, top_radius)
                    top_radius = body_radius
                    bottom_radius = body_radius
                    hole_pattern_detected = True
    
    # 底部盲孔检测：顶部恒定半径为本体，底部参数骤降为孔洞
    if not hole_pattern_detected and cylindrical_body and top_radius > 0.01:
        below_zls_bottom = [zl for zl in sorted_z if zl < body_end_z and zl in z_radius_data]
        if below_zls_bottom:
            below_r_first = z_radius_data[below_zls_bottom[0]]  # 紧邻本体的孔洞层
            if below_r_first < body_radius * 0.6:
                log_to_file(f"[STEP Exporter]   Bottom hole pattern detected: body_r={body_radius:.3f} below_r={below_r_first:.3f}")
                hole_pattern_detected = True
                hole_position = 'bottom'
    
    # 底部盲孔检测（顶点数比值法）：当底部顶点数远多于顶部（>3x），
    # 且顶部是干净的单层圆时，孔洞在底部。适用于外壁无中间层顶点的情况。
    # 不依赖 has_two_clusters（圆倒角导致底部层难以聚类）。
    if not hole_pattern_detected and cylindrical_body:
        bot_vcount = len(z_layers[sorted_z[0]])
        top_vcount = len(z_layers[sorted_z[-1]])
        if bot_vcount > top_vcount * 3:
            # 孔在底部：从底部层半径分布中找最小半径簇作为内孔半径
            b_radii = sorted(compute_radii(z_layers[sorted_z[0]]))
            # 取底部最小的10%顶点半径的中位数（排除外壁和倒角顶点）
            inner_count = max(4, len(b_radii) // 10)
            inner_r = sorted(b_radii[:inner_count])[inner_count//2]
            
            # 孔深：找底部以上顶点数最多的Z层（通常是孔底平面），
            # 孔底以上顶点数应骤降（内孔壁结束，仅剩外壁）
            best_z = sorted_z[0]
            best_vc = 0
            for zl in sorted_z[1:-1]:  # 跳过底部和顶部
                vc = len(z_layers[zl])
                if vc > best_vc:
                    best_vc = vc
                    best_z = zl
            # 孔底以上第一层顶点数应显著下降
            if best_vc > top_vcount * 2:
                hole_end_z = best_z
            else:
                hole_end_z = sorted_z[0]  # 无法确定，保守使用底部
            
            hole_depth = hole_end_z - sorted_z[0]
            if inner_r > 0.001 and hole_depth > height * 0.1:
                hole_radius = inner_r
                hole_pattern_detected = True
                hole_position = 'bottom'
                log_to_file(f"[STEP Exporter]   Bottom blind hole via vcount ratio: bot_v={bot_vcount} top_v={top_vcount} inner_r={inner_r:.4f} hole_depth={hole_depth:.4f} ({hole_depth/height*100:.0f}%) best_z={best_z:.4f} best_vc={best_vc}")
    
    # 底部盲孔检测（空心簇法）：底部有两簇（外壁+内孔），但顶部无两簇（实心顶）
    if not hole_pattern_detected and cylindrical_body and bottom_is_hollow and not top_is_hollow:
        # 确认中间层也有两簇（内孔壁存在），顶部层无两簇（内孔未贯穿）
        mid_has_hole = False
        for zl in sorted_z[1:-1]:  # 检查中间层（排除底部和顶部）
            if len(z_layers[zl]) >= 16:
                mid_radii = sorted(compute_radii(z_layers[zl]))
                mid_cluster, _ = has_two_clusters(mid_radii)
                if mid_cluster:
                    mid_has_hole = True
                    break
        if mid_has_hole:
            # 计算孔洞深度：从底部向上找到内孔消失的Z层
            # hole_end_z = 最后一个有两簇的Z层（内孔壁终点）
            hole_end_z = sorted_z[0]  # 默认仅在底部
            for zl in sorted_z[1:]:
                if len(z_layers[zl]) >= 16:
                    zl_radii = sorted(compute_radii(z_layers[zl]))
                    zl_cluster, _ = has_two_clusters(zl_radii)
                    if zl_cluster:
                        hole_end_z = zl  # 更新为最后一个有两簇的层
                    else:
                        break  # 内孔在此层之上消失
            # 获取孔半径：从底部层内部簇中提取
            inner_b, _ = layer_inner_outer_radii(sorted_z[0]) if 'layer_inner_outer_radii' in dir() else (0, 0)
            if inner_b == 0:
                # inline compute
                b_radii = sorted(compute_radii(z_layers[sorted_z[0]]))
                b_cluster, b_outer = has_two_clusters(b_radii)
                if b_cluster:
                    n_b = len(b_radii)
                    b_inner = b_radii[:n_b - len(b_outer)]
                    inner_b = sorted(b_inner)[len(b_inner)//2] if b_inner else 0
            
            hole_depth = hole_end_z - sorted_z[0]
            if inner_b > 0.001 and hole_depth > height * 0.15:
                hole_radius = inner_b
                hole_pattern_detected = True
                hole_position = 'bottom'
                log_to_file(f"[STEP Exporter]   Bottom blind hole detected via cluster: inner_r={inner_b:.4f} hole_depth={hole_depth:.4f} ({hole_depth/height*100:.0f}%)")
    
    if cylindrical_body:
        body_radius = sorted([z_radius_data.get(zl, body_radius) for zl in sorted_z 
                               if abs(z_radius_data.get(zl, body_radius) - body_radius) / max(body_radius, 0.01) < 0.01
                               and zl in z_radius_data]) or [body_radius]
        body_radius = body_radius[len(body_radius)//2] if isinstance(body_radius, list) else body_radius
        
        # 顶部过渡：body_end_z 以上的所有层
        top_transition_zls = [zl for zl in sorted_z if zl > body_end_z and zl in z_radius_data]
        
        # 孔洞模式：孔洞表面的顶点不应被检测为倒角/圆角过渡
        if hole_pattern_detected:
            top_transition_zls = []
        
        # 如果过渡层不足2层但顶部半径明显偏离，添加上一个本体层作为过渡起点
        if len(top_transition_zls) < 2 and not hole_pattern_detected:
            top_r = z_radius_data.get(sorted_z[-1])
            if top_r is not None and abs(top_r - body_radius) / max(body_radius, 0.01) > 0.01:
                # 找到本体与过渡的分界层
                for i in range(len(sorted_z) - 2, -1, -1):
                    zl = sorted_z[i]
                    if zl not in z_radius_data:
                        continue
                    if abs(z_radius_data[zl] - body_radius) / max(body_radius, 0.01) <= 0.01:
                        top_transition_zls = [sorted_z[j] for j in range(i, len(sorted_z)) if sorted_z[j] in z_radius_data]
                        break
        
        # 底部过渡：body_end_z 以下的层（如果有底部倒角）
        if len(sorted_z) >= 2 and sorted_z[0] < body_end_z:
            bottom_transition_zls = [zl for zl in sorted_z if sorted_z[0] <= zl <= body_end_z and zl in z_radius_data]
        else:
            bottom_transition_zls = []
    else:
        # 圆锥本体：用线性拟合检测过渡
        top_transition_zls = []
        bottom_transition_zls = []
        
        # === 稀疏层级的倒角/圆角快速检测（3层模式） ===
        valid_zls = [zl for zl in sorted_z if zl in z_radius_data]
        if len(valid_zls) == 3:
            r0 = z_radius_data[valid_zls[0]]
            r1 = z_radius_data[valid_zls[1]]
            r2 = z_radius_data[valid_zls[2]]
            ratio_01 = abs(r0 - r1) / max(abs(r0), 0.001)
            ratio_12 = abs(r1 - r2) / max(abs(r1), 0.001)
            if ratio_01 > 0.01 and ratio_12 < 0.01:
                # r0 != r1 == r2 → one end has edge feature, the other is full body
                # Determine which end is chamfered: r0 > r1 means top chamfer (r0 full), r0 < r1 means bottom chamfer
                if r0 > r1:
                    # r0 > r1 == r2 → 顶部倒角，r0 是完整半径（圆柱体）
                    body_radius = r0
                    bottom_radius = r0
                    top_radius = r0  # 让后续比例检查通过，确保返回 cylinder 而非 cone
                    top_feature = 'chamfer'
                    top_feature_size = r0 - r2
                    top_transition_zls = [valid_zls[0], valid_zls[1]]
                    cylindrical_body = True
                    body_end_z = valid_zls[2]
                else:
                    # r0 < r1 == r2 → 底部倒角（圆柱体），r0 是倒角后的小半径
                    body_radius = r1
                    bottom_radius = r1
                    top_radius = r1
                    bottom_feature = 'chamfer'
                    bottom_feature_size = r1 - r0
                    bottom_transition_zls = [valid_zls[0], valid_zls[1]]
                    cylindrical_body = True
                    body_end_z = valid_zls[1]  # chamfer ends here, body starts
            elif ratio_01 < 0.01 and ratio_12 > 0.01:
                # r0 == r1 != r2 → 顶部特征（圆柱体），r0=r1 是完整半径，r2 是特征端
                body_radius = r0
                bottom_radius = r0
                top_radius = r0
                top_feature = 'chamfer'
                top_feature_size = r0 - r2
                top_transition_zls = [valid_zls[1], valid_zls[2]]
                cylindrical_body = True
                body_end_z = valid_zls[0]
            elif ratio_01 > 0.01 and ratio_12 > 0.01:
                # 两端都有半径变化 → 可能是锥体+倒角
                # 需要通过 z 间距判断倒角在顶部还是底部
                # 倒角过渡区较短，锥体本体较长
                gap_bottom = valid_zls[1] - valid_zls[0]  # 底部过渡区高度
                gap_top = valid_zls[2] - valid_zls[1]      # 顶部过渡区高度
                if gap_bottom < gap_top * 0.5:
                    # 底部过渡区很短 → 底部倒角 on 锥体
                    # r0: chamfer后的底面半径, r1: 锥体底部全半径, r2: 锥体顶部半径
                    body_radius = r1
                    bottom_feature = 'chamfer'
                    bottom_feature_size = r1 - r0
                    bottom_transition_zls = [valid_zls[0], valid_zls[1]]
                    log_to_file(f"[STEP Exporter]   detect: 3-layer cone with bottom chamfer (r0={r0:.4f}<r1={r1:.4f}>r2={r2:.4f}, gap_bot={gap_bottom:.4f}<gap_top={gap_top:.4f})")
                elif gap_top < gap_bottom * 0.5:
                    # 顶部过渡区很短 → 顶部倒角 on 锥体（锥体上宽下窄）
                    # r0: 锥体底部半径, r1: 锥体顶部全半径, r2: chamfer后的顶面半径
                    body_radius = r1
                    top_feature = 'chamfer'
                    top_feature_size = r1 - r2
                    top_transition_zls = [valid_zls[1], valid_zls[2]]
                    log_to_file(f"[STEP Exporter]   detect: 3-layer cone with top chamfer (r0={r0:.4f}<r1={r1:.4f}>r2={r2:.4f}, gap_top={gap_top:.4f}<gap_bot={gap_bottom:.4f})")
                elif r0 < r1:
                    # 无法通过间距判断，退化为按半径关系判断：r0<r1 → 底部倒角
                    body_radius = r1
                    bottom_feature = 'chamfer'
                    bottom_feature_size = r1 - r0
                    bottom_transition_zls = [valid_zls[0], valid_zls[1]]
                    log_to_file(f"[STEP Exporter]   detect: 3-layer cone with bottom chamfer (fallback, r0={r0:.4f}<r1={r1:.4f})")
                elif r0 > r1:
                    # r0 > r1 > r2 → 顶部倒角 on 锥体
                    body_radius = r1
                    top_feature = 'chamfer'
                    top_feature_size = r1 - r2
                    top_transition_zls = [valid_zls[1], valid_zls[2]]
                    log_to_file(f"[STEP Exporter]   detect: 3-layer cone with top chamfer (r0={r0:.4f}>r1={r1:.4f}>r2={r2:.4f})")
        
        fit_zls = None  # will be set if mid-zone fitting is applicable
        valid_zls = [zl for zl in sorted_z if zl in z_radius_data]
        if len(valid_zls) >= 4:
            height = sorted_z[-1] - sorted_z[0]
            # 按高度分区：底15%，中70%，顶15%
            cut_bot = sorted_z[0] + height * 0.15
            cut_top = sorted_z[-1] - height * 0.15
            
            bot_zls = [zl for zl in valid_zls if zl < cut_bot]
            mid_zls = [zl for zl in valid_zls if cut_bot <= zl <= cut_top]
            top_zls = [zl for zl in valid_zls if zl > cut_top]
            
            # 判断：中间足够多层 → 正常锥体；否则 → 只有过渡区有层
            fit_done = False
            if len(mid_zls) >= 3:
                # 正常锥体：用中间层拟合，检测两端偏离
                fit_zls = mid_zls
            elif len(bot_zls) >= 1 and len(top_zls) >= 1:
                # 只有过渡区有层：取底部最上层和顶部最下层作为本体端点
                body_bot_z = bot_zls[-1]  # chamfer顶部
                body_top_z = top_zls[0]   # fillet底部
                body_bot_r = z_radius_data[body_bot_z]
                body_top_r = z_radius_data[body_top_z]
                
                # 本体线性：r = a*z + b
                dz = body_top_z - body_bot_z
                if dz > 0.01:
                    a = (body_top_r - body_bot_r) / dz
                    b = body_bot_r - a * body_bot_z
                    
                    deviation_thresh = max(abs(a) * height * 0.02 + 0.1, 0.15)
                    
                    # 底部过渡检测：只收集偏离拟合线的层级
                    deviating_bot = []
                    for zl in bot_zls:
                        expected_r = a * zl + b
                        actual_r = z_radius_data[zl]
                        if abs(actual_r - expected_r) > deviation_thresh:
                            deviating_bot.append(zl)
                    
                    if deviating_bot:
                        bottom_transition_zls = deviating_bot
                    elif len(bot_zls) >= 2:
                        bot_slope = (z_radius_data[bot_zls[-1]] - z_radius_data[bot_zls[0]]) / (bot_zls[-1] - bot_zls[0])
                        if abs(bot_slope - a) > max(abs(a) * 0.3, 0.05):
                            bottom_transition_zls = bot_zls
                    
                    # 顶部过渡检测：只收集偏离拟合线的层级
                    deviating_top = []
                    for zl in top_zls:
                        expected_r = a * zl + b
                        actual_r = z_radius_data[zl]
                        if abs(actual_r - expected_r) > deviation_thresh:
                            deviating_top.append(zl)
                    
                    if deviating_top:
                        top_transition_zls = deviating_top
                    elif len(top_zls) >= 2:
                        top_slope = (z_radius_data[top_zls[-1]] - z_radius_data[top_zls[0]]) / (top_zls[-1] - top_zls[0])
                        if abs(top_slope - a) > max(abs(a) * 0.3, 0.05):
                            top_transition_zls = top_zls
                fit_done = True
            else:
                # 中间有层但不足3层：仍用中间层拟合（如果有的话）
                if len(mid_zls) >= 1:
                    fit_zls = mid_zls
                
            if not fit_done and fit_zls is not None and len(fit_zls) >= 3:
                # Linear regression r = a*z + b on fit_zls
                sum_z = sum(zl for zl in fit_zls)
                sum_r = sum(z_radius_data[zl] for zl in fit_zls)
                sz = sum_z / len(fit_zls)
                sr = sum_r / len(fit_zls)
                s_zz = sum((zl - sz) * (zl - sz) for zl in fit_zls)
                s_zr = sum((zl - sz) * (z_radius_data[zl] - sr) for zl in fit_zls)
                
                if s_zz > 0.0001:
                    a = s_zr / s_zz
                    b = sr - a * sz
                    deviation_thresh = max(abs(a) * height * 0.02 + 0.1, 0.15)
                    
                    deviating_top = []
                    deviating_bot = []
                    for zl in valid_zls:
                        expected_r = a * zl + b
                        actual_r = z_radius_data[zl]
                        dev = abs(actual_r - expected_r)
                        if dev > deviation_thresh:
                            if zl > fit_zls[-1]:
                                deviating_top.append(zl)
                            elif zl < fit_zls[0]:
                                deviating_bot.append(zl)
                    
                    top_transition_zls = deviating_top or top_transition_zls
                    bottom_transition_zls = deviating_bot or bottom_transition_zls
    
    # === 倒角+圆角组合检测：圆柱本体无中间顶点时的回退 ===
    # 当圆柱本体无内部顶点，两端过渡区都只有少量层级时，
    # 顶部2+层同半径→倒角，底部2+层渐变半径→圆角
    if not cylindrical_body and not top_transition_zls and not bottom_transition_zls:
        valid_zls_mod = [zl for zl in sorted_z if zl in z_radius_data]
        if len(valid_zls_mod) >= 4:
            # 底部检测：检查底部半径是否单调递减/递增（圆角特征）
            # 取前5层检查趋势，然后扩展整个过渡区
            probe_count = min(5, len(valid_zls_mod) // 2)
            if probe_count >= 3:
                bot_radii_probe = [z_radius_data[valid_zls_mod[i]] for i in range(probe_count)]
                dr_total = bot_radii_probe[-1] - bot_radii_probe[0]
                if abs(dr_total) > 0.00005:
                    # 单调性检查
                    monotonically = True
                    direction = 1 if dr_total > 0 else -1
                    for i in range(1, probe_count):
                        if (bot_radii_probe[i] - bot_radii_probe[i-1]) * direction < 0:
                            monotonically = False
                            break
                    if monotonically:
                        # 扩展到所有跟随同一趋势的层（不跨越 >1mm 的空隙）
                        bottom_transition_zls = []
                        for i in range(len(valid_zls_mod)):
                            if i == 0:
                                bottom_transition_zls.append(valid_zls_mod[i])
                                continue
                            # 空隙检查：相邻层 z 差 > 0.001（1mm）说明离开了过渡区
                            z_gap = valid_zls_mod[i] - valid_zls_mod[i-1]
                            if z_gap > 0.001:
                                break
                            d = z_radius_data[valid_zls_mod[i]] - z_radius_data[valid_zls_mod[i-1]]
                            if abs(d) < 0.000005:
                                break  # 半径变化太小，停止扩展
                            if d * direction < 0:
                                break  # 方向反转，停止扩展
                            bottom_transition_zls.append(valid_zls_mod[i])
                        
                        if len(bottom_transition_zls) >= 3:
                            # 过渡区跨度检查：不超过总高度的30%（排除锥体误判）
                            total_height_mod = sorted_z[-1] - sorted_z[0]
                            transition_span = bottom_transition_zls[-1] - bottom_transition_zls[0]
                            if total_height_mod > 0 and transition_span / total_height_mod > 0.3:
                                bottom_transition_zls = []  # 跨度太大，不是过渡特征
                            else:
                                bottom_feature = 'fillet'
                                bottom_zs = transition_span
                                bottom_dr = abs(z_radius_data[bottom_transition_zls[-1]] - z_radius_data[bottom_transition_zls[0]])
                                bottom_feature_size = max(bottom_zs, bottom_dr)
                                body_radius = z_radius_data[bottom_transition_zls[0]]
                                bottom_radius = body_radius
                                top_radius = body_radius
                                cylindrical_body = True
            
            # 顶部检测：检查最高2层是否半径相同（倒角特征）
            if len(valid_zls_mod) >= 4:
                top_zls_mod = valid_zls_mod[-2:]  # 取顶部2层
                if len(top_zls_mod) >= 2:
                    top_radii = [z_radius_data[zl] for zl in top_zls_mod]
                    if abs(top_radii[-1] - top_radii[-2]) / max(abs(top_radii[-1]), 0.001) < 0.01:
                        # 顶部两层半径相同 → 倒角
                        if not body_radius:
                            # 从第三层推断体半径
                            if len(valid_zls_mod) >= 3:
                                body_radius = z_radius_data[valid_zls_mod[-3]]
                            else:
                                body_radius = top_radii[-1]
                            bottom_radius = body_radius
                            top_radius = body_radius
                        top_feature = 'chamfer'
                        top_feature_size = body_radius - top_radii[-1] if body_radius > top_radii[-1] else 0
                        top_transition_zls = top_zls_mod
                        cylindrical_body = True
    
    # 2. 分析过渡区类型
    def _classify_transition(transition_zls):
        if len(transition_zls) < 2:
            return None, 0.0
        _radii = [(zl, z_radius_data[zl]) for zl in transition_zls if z_radius_data.get(zl) is not None]
        if len(_radii) < 2:
            return None, 0.0
        
        dr = _radii[-1][1] - _radii[0][1]
        threshold = max(body_radius * 0.01, 0.0001)
        if abs(dr) < threshold:
            return None, 0.0
        
        slopes = []
        for j in range(1, len(_radii)):
            dz = _radii[j][0] - _radii[j-1][0]
            ds = _radii[j][1] - _radii[j-1][1]
            if dz > 0.0001:
                slopes.append(ds / dz)
        
        if len(slopes) < 1:
            return None, 0.0
        
        avg_slope = abs(sum(slopes) / len(slopes))
        if avg_slope < 0.005:
            return None, 0.0
        
        if len(slopes) >= 2:
            accels = [slopes[j] - slopes[j-1] for j in range(1, len(slopes))]
            avg_accel = sum(abs(a) for a in accels) / len(accels)
            if avg_accel < max(avg_slope * 0.12, 0.02):
                feature_type = 'chamfer'
                feature_size = abs(dr)
            else:
                feature_type = 'fillet'
                # Fillet radius: Z-span captures the tangent-to-tangent range but may
                # underestimate when bottom portion deviates less than threshold.
                # Use max(Z-span, |dr|) as robust estimate (both should equal R for 90°
                # fillets on cylinders; on tapered cones they converge to same value).
                z_span = (transition_zls[-1] - transition_zls[0]) * 1.0
                feature_size = max(z_span, abs(dr))
        else:
            # 单斜率过渡 → 倒角（线性过渡），用 |dr| 作为倒角尺寸
            feature_type = 'chamfer'
            feature_size = abs(dr)
        
        return feature_type, feature_size
    
    # 扩展单层过渡：当过渡区只有1层时，加入相邻的本体端点层
    # 例如双倒角圆柱：sorted_z = [-0.02(chamfer rim), -0.017(chamfer face), 0.017(chamfer face), 0.02(chamfer rim)]
    # 过渡区只有 chamfer rim 一层，需要包含 chamfer face 才能正确分类
    if top_transition_zls and len(top_transition_zls) == 1:
        valid_zls = [zl for zl in sorted_z if zl in z_radius_data]
        idx = valid_zls.index(top_transition_zls[0])
        if idx > 0:
            top_transition_zls = [valid_zls[idx - 1], valid_zls[idx]]
    if bottom_transition_zls and len(bottom_transition_zls) == 1:
        valid_zls = [zl for zl in sorted_z if zl in z_radius_data]
        idx = valid_zls.index(bottom_transition_zls[0])
        if idx + 1 < len(valid_zls):
            bottom_transition_zls = [valid_zls[idx], valid_zls[idx + 1]]
    
    if top_transition_zls and not top_feature:
        top_feature, top_feature_size = _classify_transition(top_transition_zls)
    if bottom_transition_zls and not bottom_feature:
        bottom_feature, bottom_feature_size = _classify_transition(bottom_transition_zls)
    
    # 锥体倒角/圆角修正：过渡区边缘半径 = 锥体本体半径（非倒角面半径）
    # 顶部过渡层升序排列，第一个是本体边界（最高完整锥体半径）
    if not cylindrical_body and top_feature and top_transition_zls:
        body_top_r = z_radius_data.get(top_transition_zls[0], None)
        if body_top_r is not None and body_top_r > top_radius * 1.02:
            log_to_file(f"[STEP Exporter]   Cone top radius corrected via chamfer: {top_radius:.4f} -> {body_top_r:.4f}")
            top_radius = body_top_r
    # 底部过渡层升序排列，最后一个是本体边界
    if not cylindrical_body and bottom_feature and bottom_transition_zls:
        body_bot_r = z_radius_data.get(bottom_transition_zls[-1], None)
        if body_bot_r is not None and body_bot_r > bottom_radius * 1.02:
            log_to_file(f"[STEP Exporter]   Cone bottom radius corrected via chamfer: {bottom_radius:.4f} -> {body_bot_r:.4f}")
            bottom_radius = body_bot_r
    
    # 兜底修正：当 stored_ctype 指示顶部特征（倒角/圆角）但 mesh 因孔洞干扰未能检测时，
    # 在顶部区域扫描外壁峰值半径来修正 top_radius
    if not cylindrical_body and top_radius < bottom_radius * 0.85:
        stored_ctype_fb = obj.get('chamfer_type') if hasattr(obj, 'get') else None
        # 排除仅底部特征的类型，其余皆有顶部特征（chamfer/fillet/both/chamfer_fillet）
        has_top_feature = (stored_ctype_fb and 
                          stored_ctype_fb not in ('bottom_chamfer', 'bottom_fillet'))
        if has_top_feature:
            valid_zls = [zl for zl in sorted_z if zl in z_radius_data]
            if len(valid_zls) >= 3:
                height_z = sorted_z[-1] - sorted_z[0]
                top_cut = sorted_z[-1] - height_z * 0.15
                # 收集顶部15%区域内的z-level（排除顶面本身）
                top_region = [(zl, z_radius_data[zl]) for zl in valid_zls
                              if zl > top_cut and zl < sorted_z[-1] * 0.99]
                if top_region:
                    peak_z, peak_r = max(top_region, key=lambda x: x[1])
                    if peak_r > top_radius * 1.02:
                        log_to_file(f"[STEP Exporter]   Cone top radius corrected via stored edge feature (hole interference): {top_radius:.4f} -> {peak_r:.4f} (z={peak_z:.4f})")
                        top_radius = peak_r
    
    # 兜底修正：当 stored_ctype 指示底部特征（倒角/圆角）但 mesh 因孔洞干扰未能检测时，
    # 在底部区域扫描外壁峰值半径来修正 bottom_radius
    if not cylindrical_body and bottom_radius < top_radius * 0.85:
        stored_ctype_fb3 = obj.get('chamfer_type') if hasattr(obj, 'get') else None
        # 仅当存在底部特征时触发（bottom_chamfer, bottom_fillet, chamfer_both, fillet_both, chamfer_fillet）
        has_bottom_feature = (stored_ctype_fb3 and 
                             stored_ctype_fb3 in ('bottom_chamfer', 'bottom_fillet', 'chamfer_both', 'fillet_both', 'chamfer_fillet'))
        if has_bottom_feature:
            valid_zls = [zl for zl in sorted_z if zl in z_radius_data]
            if len(valid_zls) >= 3:
                height_z = sorted_z[-1] - sorted_z[0]
                bot_cut = sorted_z[0] + height_z * 0.15
                # 收集底部15%区域内的z-level（排除底面本身）
                bot_region = [(zl, z_radius_data[zl]) for zl in valid_zls
                              if zl < bot_cut and zl > sorted_z[0] * 1.01]
                if bot_region:
                    peak_z, peak_r = max(bot_region, key=lambda x: x[1])
                    if peak_r > bottom_radius * 1.02:
                        log_to_file(f"[STEP Exporter]   Cone bottom radius corrected via stored edge feature (hole interference): {bottom_radius:.4f} -> {peak_r:.4f} (z={peak_z:.4f})")
                        bottom_radius = peak_r
    
    # 对于圆柱本体有过渡 → 修正 radius 为 body_radius
    if cylindrical_body and (top_feature or bottom_feature) and not has_groove_custom:
        # 单侧过渡：用无过渡侧的极端Z层半径作为本体半径
        # 避免 body_radius 因过渡区边界顶点混入导致轻微偏差
        if top_feature and not bottom_feature:
            body_radius = bottom_radius  # 底部是无过渡侧，用底部极端半径
        elif bottom_feature and not top_feature:
            body_radius = top_radius  # 顶部是无过渡侧，用顶部极端半径
        bottom_radius = body_radius
        top_radius = body_radius
    
    # 回退检测：锥体分析检测到两端过渡特征，但 cylindrical_body 仍为 False
    # 当两端过渡区边缘半径接近时（差距<5%），推断为圆柱本体（非锥体）
    # 注意：已检测到孔洞时跳过，避免将孔洞开口误判为倒角/圆角过渡
    if not cylindrical_body and not hole_pattern_detected and top_feature and bottom_feature:
        if top_transition_zls and bottom_transition_zls:
            # 过渡区z层级为升序排列
            # 顶部过渡：升序，第一个是本体边界，最后一个是极端
            # 底部过渡：升序，第一个是极端，最后一个是本体边界
            top_body_r = z_radius_data.get(top_transition_zls[0], None)
            bot_body_r = z_radius_data.get(bottom_transition_zls[-1], None)
            if top_body_r is not None and bot_body_r is not None and top_body_r > 0.001:
                if abs(top_body_r - bot_body_r) / top_body_r < 0.05:
                    body_radius = (top_body_r + bot_body_r) / 2.0
                    bottom_radius = body_radius
                    top_radius = body_radius
                    cylindrical_body = True
                    log_to_file(f"[STEP Exporter] Recovered cylindrical body from transition edges: r={body_radius:.4f}")
    
    bm.free()
    
    # DEBUG: 输出特征检测结果
    log_to_file(f"[STEP Exporter]   detect: cylindrical_body={cylindrical_body} top_feature={top_feature} top_feature_size={top_feature_size:.4f} bottom_feature={bottom_feature} bottom_feature_size={bottom_feature_size:.4f}")
    log_to_file(f"[STEP Exporter]   detect: top_transition_zls={len(top_transition_zls)} bottom_transition_zls={len(bottom_transition_zls)}")
    
    pos_x = obj.location.x
    pos_y = obj.location.y
    pos_z = obj.location.z
    
    # 检测对象旋转：如果世界矩阵翻转了 Z 轴（绕 X 或 Y 旋转 180°），
    # 则交换 top_feature 和 bottom_feature（局部坐标中 chamfer 在顶部，
    # 但世界坐标中应该在底部），同时交换 top_radius/bottom_radius
    world_mat = obj.matrix_world
    if world_mat[2][2] < 0:
        if top_feature or bottom_feature:
            log_to_file(f"[STEP Exporter] Z-axis flipped by rotation, swapping top/bottom features")
            top_feature, bottom_feature = bottom_feature, top_feature
            top_feature_size, bottom_feature_size = bottom_feature_size, top_feature_size
        # 交换上下半径（对于锥体/空心锥体，上下半径不同，旋转180°后需要对应交换）
        if abs(bottom_radius - top_radius) > 0.0001:
            top_radius, bottom_radius = bottom_radius, top_radius
            if is_hollow:
                inner_radius, inner_top_radius = inner_top_radius, inner_radius
            log_to_file(f"[STEP Exporter] Z-axis flipped by rotation, swapping top/bottom radii")
    
    # ===== Mesh-based Stepped Hole Detection for Hollow Cones =====
    # Detects stepped inner holes: constant-radius straight section at top,
    # tapered section below. Signature: inner radius near-constant in top portion
    # while outer continues to taper, with a jump at the step transition.
    stepped_hole_params = {}
    if is_hollow and not (bottom_radius * 0.98 <= top_radius <= bottom_radius * 1.02):
        inner_z_data = {}
        for zl in sorted_z:
            pts = z_layers[zl]
            if len(pts) < 16:
                continue
            radii = sorted(compute_radii(pts))
            is_cluster, outer = has_two_clusters(radii)
            if not is_cluster:
                continue
            n = len(radii)
            inner_vals = radii[:n - len(outer)]
            if len(inner_vals) >= 4:
                inner_z_data[zl] = sorted(inner_vals)[len(inner_vals) // 2]
        
        if len(inner_z_data) >= 3:
            inner_z_sorted = sorted(inner_z_data.keys())
            top_z = inner_z_sorted[-1]
            
            # Look at top 35%: inner radius should be nearly constant (straight hole section)
            top_cut = top_z - height * 0.35
            top_zls = [zl for zl in inner_z_sorted if zl >= top_cut]
            bot_zls = [zl for zl in inner_z_sorted if zl < top_cut]
            
            # Accept 3-level meshes: 2 in top section + 1 in bottom
            # Accept 4+ level meshes: >=2 in each
            usable = (len(top_zls) >= 2 and len(bot_zls) >= 2) or \
                     (len(inner_z_data) == 3 and len(top_zls) == 2 and len(bot_zls) == 1)
            
            if usable:
                top_inner = [inner_z_data[zl] for zl in top_zls]
                bot_inner = [inner_z_data[zl] for zl in bot_zls]
                top_range = max(top_inner) - min(top_inner)
                top_mean = sum(top_inner) / len(top_inner)
                bot_range = max(bot_inner) - min(bot_inner)
                bot_min = min(bot_inner)
                
                # Criteria for stepped hole:
                # - Top section nearly constant radius (straight hole)
                # - Bottom inner radius significantly larger than top (gap > 30% of top, or > 0.15 absolute for small holes)
                # - For 4+ levels: bottom section has significant taper
                # - For 3 levels: accept by gap between bottom and top inner
                if len(inner_z_data) >= 4:
                    is_stepped = (top_range < max(top_mean * 0.05, 0.10) and
                                  (bot_range > max(top_mean * 0.08, 0.15) or
                                   bot_min > top_mean * 1.3) and
                                  top_mean < inner_radius * 0.85)
                else:
                    # 3-level mesh: check top flat + bottom significantly larger
                    is_stepped = (top_range < max(top_mean * 0.05, 0.10) and
                                  bot_min > top_mean * 1.3 and
                                  top_mean < inner_radius * 0.85)
                
                if is_stepped:
                    # Find step Z: maximum inner-radius gap between adjacent layers
                    best_gap = 0.0
                    step_z = top_cut
                    for i in range(len(inner_z_sorted) - 1):
                        r1 = inner_z_data[inner_z_sorted[i]]
                        r2 = inner_z_data[inner_z_sorted[i + 1]]
                        gap = abs(r2 - r1)
                        if gap > best_gap:
                            best_gap = gap
                            # Step is at the higher Z (smaller radius is above the step)
                            step_z = inner_z_sorted[i + 1]
                    
                    small_h = top_z - step_z
                    # 锥体台阶孔：straight_h 可以是 0.3x~0.9x height（适应圆锥变体）
                    if 0.3 * height <= small_h <= height * 0.9:
                        # inner_top_radius (large hole radius at step) computed from
                        # bottom inner_radius and 2° taper (same as outer cone).
                        # This avoids mesh artifacts at the coincident step face.
                        inner_top_r = inner_radius - (height - small_h) * math.tan(math.radians(2))
                        stepped_hole_params = {
                            'small_hole_radius': top_mean,
                            'small_hole_height': small_h,
                            'inner_bottom_radius': inner_radius,
                            'inner_top_radius': max(inner_top_r, top_mean + 0.1),
                        }
                        log_to_file(f"[STEP Exporter] Detected stepped inner hole from mesh: "
                                    f"straight_r={top_mean:.3f} straight_h={small_h:.2f} "
                                    f"inner_bot_r={inner_radius:.3f} inner_top_r={inner_top_r:.3f} "
                                    f"step_gap={best_gap:.3f}")
    
    # 锥体台阶孔补充检测：当 mesh 检测未触发时，从 inner_z_data 直接推导
    if not stepped_hole_params and is_hollow and abs(bottom_radius - top_radius) > max(bottom_radius, top_radius) * 0.05:
        # 使用 primary detection 已提取的内孔数据（inner_z_data）
        # 若 inner_z_data 不足，尝试放宽条件重新提取
        if len(inner_z_data) < 3:
            log_to_file(f"[STEP Exporter]   cone stepped fallback: inner_z_data={len(inner_z_data)} entries, re-extracting...")
            # 重新提取：对锥体，使用更宽松的两聚类检测
            inner_z_data2 = {}
            for zl in sorted(z_layers.keys()):
                pts = z_layers[zl]
                if len(pts) < 8:
                    continue
                radii = sorted(compute_radii(pts))
                is_cluster, outer = has_two_clusters(radii)
                if is_cluster:
                    n = len(radii)
                    inner_vals = radii[:n - len(outer)]
                    if len(inner_vals) >= 3:
                        inner_z_data2[zl] = sorted(inner_vals)[len(inner_vals) // 2]
                else:
                    # 宽松检测：取半径分布的下半部分作为内孔候选
                    mid = len(radii) // 2
                    # 若中位数远小于最大半径，可能存在内孔
                    if len(radii) >= 6 and radii[mid] < radii[-1] * 0.7:
                        inner_z_data2[zl] = radii[mid]
            if len(inner_z_data2) >= 3:
                inner_z_data = inner_z_data2
        
        if len(inner_z_data) >= 3:
            inner_z_sorted = sorted(inner_z_data.keys())
            inner_vals = [(zl, inner_z_data[zl]) for zl in inner_z_sorted]
            # 找最大间距（台阶位置）
            best_gap = 0.0
            step_idx = 0
            for i in range(len(inner_vals) - 1):
                gap = abs(inner_vals[i+1][1] - inner_vals[i][1])
                if gap > best_gap:
                    best_gap = gap
                    step_idx = i
            if best_gap > 0.02:
                step_z_pos = inner_vals[step_idx + 1][0]  # 台阶上方 z
                step_lo_r = inner_vals[step_idx][1]       # 台阶下方半径
                step_hi_r = inner_vals[step_idx + 1][1]   # 台阶上方半径
                bottom_z = inner_vals[0][0]
                top_z = inner_vals[-1][0]
                
                # 判断直孔位置：半径较小且变化平缓的一侧为直孔
                # 比较台阶两侧的 Z 范围
                lo_count = step_idx + 1                     # 下侧 z-level 数
                hi_count = len(inner_vals) - step_idx - 1   # 上侧 z-level 数
                
                # 计算两侧半径变化范围
                lo_radii = [inner_vals[i][1] for i in range(step_idx + 1)]
                hi_radii = [inner_vals[i][1] for i in range(step_idx + 1, len(inner_vals))]
                lo_range = max(lo_radii) - min(lo_radii) if len(lo_radii) >= 2 else 0
                hi_range = max(hi_radii) - min(hi_radii) if len(hi_radii) >= 2 else 0
                
                # 直孔侧：半径变化小（< 5% of mean 或 < 0.03 absolute）
                lo_is_straight = (lo_range < max(sum(lo_radii) / len(lo_radii) * 0.05, 0.03)) if lo_radii else False
                hi_is_straight = (hi_range < max(sum(hi_radii) / len(hi_radii) * 0.05, 0.03)) if hi_radii else False
                
                # 若只有一侧平缓，它就是直孔
                # 若两侧都平缓，半径较小的为直孔
                # 若两侧都变化大，半径变化较小 + 范围较小的为直孔
                if lo_is_straight and not hi_is_straight:
                    small_at_bottom = True
                elif hi_is_straight and not lo_is_straight:
                    small_at_bottom = False
                elif lo_is_straight and hi_is_straight:
                    small_at_bottom = (sum(lo_radii) / len(lo_radii) < sum(hi_radii) / len(hi_radii))
                else:
                    # 都不平缓：比较半径变化率和值
                    lo_ratio = lo_range / (sum(lo_radii) / len(lo_radii)) if lo_radii else 1
                    hi_ratio = hi_range / (sum(hi_radii) / len(hi_radii)) if hi_radii else 1
                    if lo_ratio < hi_ratio * 0.5:
                        small_at_bottom = True
                    elif hi_ratio < lo_ratio * 0.5:
                        small_at_bottom = False
                    else:
                        small_at_bottom = (sum(lo_radii) / len(lo_radii) < sum(hi_radii) / len(hi_radii))
                
                if small_at_bottom:
                    # 直孔在底部，锥孔在顶部
                    small_h = step_z_pos - bottom_z
                    small_r = sum(lo_radii) / len(lo_radii)  # 直孔平均半径
                    inner_btm = step_hi_r  # 锥孔起点（台阶上方，较大半径）
                    inner_top = inner_vals[-1][1]  # 锥孔顶部半径
                else:
                    # 直孔在顶部，锥孔在底部
                    small_h = top_z - step_z_pos
                    small_r = sum(hi_radii) / len(hi_radii)  # 直孔平均半径
                    inner_btm = inner_vals[0][1]  # 锥孔底部半径
                    inner_top = step_lo_r  # 锥孔顶部（台阶下方，较大半径）
                
                if 0.1 * height <= small_h <= height * 0.95:
                    stepped_hole_params = {
                        'small_hole_radius': small_r,
                        'small_hole_height': small_h,
                        'inner_bottom_radius': inner_btm,
                        'inner_top_radius': inner_top,
                    }
                    log_to_file(f"[STEP Exporter]   cone stepped hole from inner_z_data (fallback): "
                                f"small_r={small_r:.3f} small_h={small_h:.2f} "
                                f"inner_btm={inner_btm:.3f} inner_top={inner_top:.3f} gap={best_gap:.3f}"
                                f" ({'bottom-straight' if small_at_bottom else 'top-straight'})")
    
    # 锥体台阶孔最终兜底：从存储属性直接推导（inner_z_data 不足时）
    if not stepped_hole_params and is_hollow and abs(bottom_radius - top_radius) > max(bottom_radius, top_radius) * 0.05:
        # 从 stored properties 读取 taper/stepped 参数（mm → m）
        taper_top_r = (obj.get('hole_taper_top_r', 0) if hasattr(obj, 'get') else 0) * 0.001
        taper_step_r = (obj.get('hole_taper_step_r', 0) if hasattr(obj, 'get') else 0) * 0.001
        stepped_small_r = (obj.get('hole_stepped_small_r', 0) if hasattr(obj, 'get') else 0) * 0.001
        stepped_large_h = (obj.get('hole_stepped_large_h', 0) if hasattr(obj, 'get') else 0) * 0.001
        if taper_top_r > 0.001 and taper_step_r > 0.001 and stepped_small_r > 0.001:
            # 锥孔在底部（大端），直孔在顶部（小端）
            # inner_bottom = 锥孔大端半径, inner_top = 锥孔台阶处半径
            stepped_hole_params = {
                'small_hole_radius': stepped_small_r,
                'small_hole_height': height - stepped_large_h,
                'inner_bottom_radius': taper_top_r,
                'inner_top_radius': taper_step_r,
            }
            log_to_file(f"[STEP Exporter]   cone stepped hole from stored props (final fallback): "
                        f"small_r={stepped_small_r:.3f} small_h={height - stepped_large_h:.2f} "
                        f"inner_btm={taper_top_r:.3f} inner_top={taper_step_r:.3f}")
        else:
            # stored props 不可用 → 从 z_radius_data + hollow 检测推算
            outer_min = min(bottom_radius, top_radius)
            inner_z_filtered = {}
            for zl in sorted(z_radius_data.keys()):
                r = z_radius_data[zl]
                # 过滤外壁点：内孔半径 < 外壁较小端 × 90%
                if r < outer_min * 0.9:
                    inner_z_filtered[zl] = r
            if len(inner_z_filtered) >= 6:
                inner_z_sorted = sorted(inner_z_filtered.keys())
                inner_vals = [(zl, inner_z_filtered[zl]) for zl in inner_z_sorted]
                # 找最大间距（台阶位置）— 限制在相邻紧密 z-level 之间（Δz < 2% height）
                best_gap = 0.0
                step_idx = 0
                max_dz = height * 0.02  # 只考虑连续采样点
                for i in range(len(inner_vals) - 1):
                    dz = abs(inner_vals[i+1][0] - inner_vals[i][0])
                    if dz > max_dz:
                        continue  # 跳过稀疏采样间隙
                    gap = abs(inner_vals[i+1][1] - inner_vals[i][1])
                    if gap > best_gap:
                        best_gap = gap
                        step_idx = i
                if best_gap > 0.01:
                    step_z = inner_vals[step_idx + 1][0]
                    bot_z = inner_vals[0][0]
                    top_z = inner_vals[-1][0]
                    # 台阶两侧半径
                    lo_r = inner_vals[step_idx][1]
                    hi_r = inner_vals[step_idx + 1][1]
                    # 直孔在底部（较小半径侧），锥孔在顶部（较大半径侧）
                    small_h = step_z - bot_z  # 直孔段高度（底部）
                    # C++ 参数:
                    #   inner_bottom = 锥孔段底部半径（= 台阶处，锥孔侧，较大半径）
                    #   inner_top = 锥孔段顶部半径（= 锥体顶部，锥孔出口）
                    #   inner_bottom < inner_top → tapered at top, straight at bottom
                    stepped_hole_params = {
                        'small_hole_radius': min(lo_r, hi_r),     # 直孔半径（较小侧）
                        'small_hole_height': small_h,              # 直孔高度
                        'inner_bottom_radius': max(lo_r, hi_r),   # 锥孔台阶处半径（gap 较大侧）
                        'inner_top_radius': inner_vals[-1][1],     # 锥体顶部内孔半径（锥孔出口）
                    }
                    log_to_file(f"[STEP Exporter]   cone stepped hole from z_radius_data (final fallback): "
                                f"small_r={min(lo_r, hi_r):.3f} small_h={small_h:.3f} "
                                f"inner_btm={max(lo_r, hi_r):.3f} inner_top={inner_vals[-1][1]:.3f} "
                                f"gap={best_gap:.3f} step_z={step_z:.3f} n={len(inner_vals)}")
    
    # 构建返回参数
    # 应用单位缩放：所有尺寸参数 × scale（mm=1000, m=1）
    S = scale if scale > 0 else 1.0
    
    # 检测到孔洞模式（顶部/底部盲孔）：返回盲孔圆柱体类型
    # 使用 OpenCASCADE 布尔减操作创建参数化盲孔
    if hole_pattern_detected:
        if hole_position == 'through':
            # 通孔：使用空心圆柱体（直孔或锥形孔）
            body_radius_for_export = max(bottom_radius, top_radius)
            
            # 锥体通孔：如果上下半径不同，使用空心锥体
            # But first: check if radius difference is from an edge feature (chamfer/fillet)
            stored_ctype_cone = obj.get('chamfer_type') if hasattr(obj, 'get') else None
            radius_diff_from_edge = False
            if stored_ctype_cone and abs(bottom_radius - top_radius) / max(bottom_radius, 0.01) > 0.05:
                # 检查半径差是否完全可由边缘特征解释
                # 如果半径差 > 边缘特征大小的1.2倍，则边缘特征叠加在锥体上
                stored_csz_m = (obj.get('chamfer_size', 0) if hasattr(obj, 'get') else 0) * 0.001
                stored_fr_m = (obj.get('fillet_radius_edge', 0) if hasattr(obj, 'get') else 0) * 0.001
                max_edge_sz = max(stored_csz_m, stored_fr_m)
                if (stored_ctype_cone in ('chamfer', 'fillet', 'chamfer_both', 'fillet_both',
                                          'bottom_chamfer', 'bottom_fillet', 'chamfer_fillet')
                        and abs(bottom_radius - top_radius) < max_edge_sz * 1.2):
                    radius_diff_from_edge = True  # 边缘特征能完全解释半径差 → 圆柱
            is_cone_body = (abs(bottom_radius - top_radius) / max(bottom_radius, 0.01) > 0.05
                            and not radius_diff_from_edge)
            if is_cone_body:
                hole_fillet_r = obj.get('hole_fillet_radius', 0.0) if hasattr(obj, 'get') else 0.0
                # 收集倒角/圆角参数
                # 优先使用存储的倒角类型，其次用 mesh 检测
                # C++ 层通过边缘半径过滤，孔口假倒角不会被误施加到外壁
                top_ch = 0.0; top_fr = 0.0; btm_ch = 0.0; btm_fr = 0.0
                stored_ctype = obj.get('chamfer_type') if hasattr(obj, 'get') else None
                if stored_ctype in ('chamfer', 'chamfer_both', 'chamfer_fillet'):
                    top_ch = (obj.get('chamfer_size', 0) if hasattr(obj, 'get') else 0) * 0.001
                elif stored_ctype in ('fillet', 'fillet_both'):
                    top_fr = (obj.get('fillet_radius_edge', 0) if hasattr(obj, 'get') else 0) * 0.001
                if stored_ctype in ('chamfer_both',):
                    btm_ch = top_ch
                elif stored_ctype in ('bottom_chamfer',):
                    btm_ch = (obj.get('chamfer_size', 0) if hasattr(obj, 'get') else 0) * 0.001
                elif stored_ctype in ('fillet_both',):
                    btm_fr = top_fr
                elif stored_ctype in ('bottom_fillet',):
                    btm_fr = (obj.get('fillet_radius_edge', 0) if hasattr(obj, 'get') else 0) * 0.001
                elif stored_ctype == 'chamfer_fillet':
                    btm_fr = (obj.get('fillet_radius_edge', 0) if hasattr(obj, 'get') else 0) * 0.001
                # Mesh fallback: only for features NOT from stored properties
                # Through-holes: skip mesh fallback entirely (hole openings mimic chamfers)
                if not stored_ctype and hole_position != 'through':
                    if top_feature == 'chamfer': top_ch = top_feature_size
                    elif top_feature == 'fillet': top_fr = top_feature_size
                    if bottom_feature == 'chamfer': btm_ch = bottom_feature_size
                    elif bottom_feature == 'fillet': btm_fr = bottom_feature_size
                log_to_file(f"[STEP Exporter]   -> hollow_cone! bR={bottom_radius:.3f} tR={top_radius:.3f} h={height:.3f} inner_r={hole_radius:.3f} top_ch={top_ch:.4f} top_fr={top_fr:.4f} btm_ch={btm_ch:.4f} btm_fr={btm_fr:.4f}")
                # Tapered through-hole: use stored opening/end radii
                hole_is_tapered_thru = obj.get('hole_is_tapered', False) if hasattr(obj, 'get') else False
                inner_bot_r = hole_radius * S
                inner_top_r = hole_radius * S
                if hole_is_tapered_thru:
                    # Stored properties are already in mm; hole_radius is in meters
                    opening_r = (obj.get('hole_opening_radius', hole_radius * S) if hasattr(obj, 'get') else hole_radius * S)
                    end_r = (obj.get('hole_end_radius', hole_radius * S) if hasattr(obj, 'get') else hole_radius * S)
                    # For through_inv: opening is at top, end is at bottom
                    if stored_hole_type == 'through_inv':
                        inner_bot_r = end_r
                        inner_top_r = opening_r
                    else:
                        inner_bot_r = opening_r
                        inner_top_r = end_r
                    # C++ create_cone_solid_parametric handles R1<R2 by axis flip
                    log_to_file(f"[STEP Exporter]   tapered through-hole: inner_top={inner_top_r:.3f} inner_bot={inner_bot_r:.3f}")
                result = {
                    'obj_type': 'hollow_cone',
                    'outer_bottom_radius': bottom_radius * S,
                    'outer_top_radius': top_radius * S,
                    'inner_bottom_radius': inner_bot_r,
                    'inner_top_radius': inner_top_r,
                    'height': height * S,
                    'hole_fillet_radius': hole_fillet_r,
                    'top_chamfer': top_ch * S,
                    'top_fillet': top_fr * S,
                    'bottom_chamfer': btm_ch * S,
                    'bottom_fillet': btm_fr * S,
                    'pos_x': pos_x * S,
                    'pos_y': pos_y * S,
                    'pos_z': pos_z * S,
                }
                # 通孔锥体+梯形槽：合并 groove 参数
                if groove_params:
                    result['obj_type'] = 'hollow_cone_grooved'
                    result.update(groove_params)
                    log_to_file(f"[STEP Exporter]   -> hollow_cone_grooved! groove_depth={groove_params.get('groove_depth', 0):.4f}")
                return result
            
            hole_fillet_r = obj.get('hole_fillet_radius', 0.0) if hasattr(obj, 'get') else 0.0
            hole_is_tapered_thru = obj.get('hole_is_tapered', False) if hasattr(obj, 'get') else False
            # Stored properties are in mm; hole_radius is in meters → normalize both to mm
            opening_r = obj.get('hole_opening_radius', hole_radius * S) if hasattr(obj, 'get') else hole_radius * S
            end_r = obj.get('hole_end_radius', hole_radius * S) if hasattr(obj, 'get') else hole_radius * S
            
            if hole_is_tapered_thru and abs(opening_r - end_r) > 0.0001:
                # 读取存储的倒角/圆角参数（mesh 分析可能受通孔干扰）
                stored_chamfer_type = obj.get('chamfer_type') if hasattr(obj, 'get') else None
                stored_chamfer_sz = obj.get('chamfer_size', 0) if hasattr(obj, 'get') else 0
                stored_fillet_r = obj.get('fillet_radius_edge', 0) if hasattr(obj, 'get') else 0
                stored_orig_r = obj.get('cylinder_original_radius', 0) if hasattr(obj, 'get') else 0
                if stored_orig_r > 0:
                    body_radius_for_export = stored_orig_r * 0.001  # mm -> m
                if stored_chamfer_type == 'chamfer':
                    top_feature = 'chamfer'; top_feature_size = stored_chamfer_sz * 0.001
                elif stored_chamfer_type == 'fillet':
                    top_feature = 'fillet'; top_feature_size = stored_fillet_r * 0.001
                elif stored_chamfer_type == 'bottom_chamfer':
                    bottom_feature = 'chamfer'; bottom_feature_size = stored_chamfer_sz * 0.001
                elif stored_chamfer_type == 'bottom_fillet':
                    bottom_feature = 'fillet'; bottom_feature_size = stored_fillet_r * 0.001
                elif stored_chamfer_type == 'chamfer_both':
                    top_feature = 'chamfer'; top_feature_size = stored_chamfer_sz * 0.001
                    bottom_feature = 'chamfer'; bottom_feature_size = stored_chamfer_sz * 0.001
                elif stored_chamfer_type == 'fillet_both':
                    top_feature = 'fillet'; top_feature_size = stored_fillet_r * 0.001
                    bottom_feature = 'fillet'; bottom_feature_size = stored_fillet_r * 0.001
                elif stored_chamfer_type == 'chamfer_fillet':
                    top_feature = 'chamfer'; top_feature_size = stored_chamfer_sz * 0.001
                    bottom_feature = 'fillet'; bottom_feature_size = stored_fillet_r * 0.001
                log_to_file(f"[STEP Exporter]   -> hollow_cylinder_tapered! r={body_radius_for_export:.3f} h={height:.3f} opening_r={opening_r:.3f} end_r={end_r:.3f} chamfer={top_feature} chamfer_sz={top_feature_size}")
                # 区分 through 和 through_inv 的锥度方向
                # through: opening在底部宽, end在顶部窄 → bottom=wide, top=narrow
                # through_inv: opening在顶部宽, end在底部窄 → bottom=narrow, top=wide
                if stored_hole_type == 'through_inv':
                    inner_t = opening_r; inner_b = end_r
                else:
                    inner_t = end_r; inner_b = opening_r
                result = {
                    'obj_type': 'hollow_cylinder_tapered',
                    'outer_radius': body_radius_for_export * S,
                    'inner_radius_top': inner_t,
                    'inner_radius_bottom': inner_b,
                    'height': height * S,
                    'hole_fillet_radius': hole_fillet_r,
                    'top_feature': top_feature,
                    'top_feature_size': top_feature_size * S,
                    'bottom_feature': bottom_feature,
                    'bottom_feature_size': bottom_feature_size * S,
                    'pos_x': pos_x * S,
                    'pos_y': pos_y * S,
                    'pos_z': pos_z * S,
                }
                if groove_params:
                    result['obj_type'] = 'hollow_cylinder_grooved'
                    result['outer_bottom_radius'] = result['outer_radius']
                    result['outer_top_radius'] = result['outer_radius']
                    result['inner_bottom_radius'] = result['inner_radius_bottom']
                    result['inner_top_radius'] = result['inner_radius_top']
                    result.update(groove_params)
                    log_to_file(f"[STEP Exporter]   -> hollow_cylinder_grooved (tapered)! groove_depth={groove_params.get('groove_depth', 0):.4f}")
                return result
            
            log_to_file(f"[STEP Exporter]   -> hollow_cylinder (through-hole)! r={body_radius_for_export:.3f} h={height:.3f} inner_r={hole_radius:.3f}")
            # 读取存储的倒角/圆角参数
            stored_chamfer_type = obj.get('chamfer_type') if hasattr(obj, 'get') else None
            stored_chamfer_sz = obj.get('chamfer_size', 0) if hasattr(obj, 'get') else 0
            stored_fillet_r = obj.get('fillet_radius_edge', 0) if hasattr(obj, 'get') else 0
            stored_orig_r = obj.get('cylinder_original_radius', 0) if hasattr(obj, 'get') else 0
            top_feat = 'none'; top_sz = 0.0; bot_feat = 'none'; bot_sz = 0.0
            if stored_orig_r > 0:
                body_radius_for_export = stored_orig_r * 0.001  # mm -> m
            if stored_chamfer_type == 'chamfer':
                top_feat = 'chamfer'; top_sz = stored_chamfer_sz * 0.001
            elif stored_chamfer_type == 'fillet':
                top_feat = 'fillet'; top_sz = stored_fillet_r * 0.001
            elif stored_chamfer_type == 'bottom_chamfer':
                bot_feat = 'chamfer'; bot_sz = stored_chamfer_sz * 0.001
            elif stored_chamfer_type == 'bottom_fillet':
                bot_feat = 'fillet'; bot_sz = stored_fillet_r * 0.001
            elif stored_chamfer_type == 'chamfer_both':
                top_feat = 'chamfer'; top_sz = stored_chamfer_sz * 0.001
                bot_feat = 'chamfer'; bot_sz = stored_chamfer_sz * 0.001
            elif stored_chamfer_type == 'fillet_both':
                top_feat = 'fillet'; top_sz = stored_fillet_r * 0.001
                bot_feat = 'fillet'; bot_sz = stored_fillet_r * 0.001
            elif stored_chamfer_type == 'chamfer_fillet':
                top_feat = 'chamfer'; top_sz = stored_chamfer_sz * 0.001
                bot_feat = 'fillet'; bot_sz = stored_fillet_r * 0.001
            log_to_file(f"[STEP Exporter]   outer feature: type={stored_chamfer_type} top={top_feat}/{top_sz:.4f} bot={bot_feat}/{bot_sz:.4f}")
            has_outer_feature = (stored_chamfer_type in ('chamfer','fillet','chamfer_both','chamfer_fillet','fillet_both','bottom_chamfer','bottom_fillet'))
            obj_type_out = 'hollow_cylinder_tapered'  # Always use tapered -- handles both straight & tapered
            result = {
                'obj_type': obj_type_out,
                'outer_radius': body_radius_for_export * S,
                'inner_radius_top': hole_radius * S,
                'inner_radius_bottom': hole_radius * S,
                'height': height * S,
                'hole_fillet_radius': hole_fillet_r,
                'pos_x': pos_x * S,
                'pos_y': pos_y * S,
                'pos_z': pos_z * S,
                'top_feature': top_feat,
                'top_feature_size': top_sz * S,
                'bottom_feature': bot_feat,
                'bottom_feature_size': bot_sz * S,
            }
            # 通孔圆柱+梯形槽：使用 hollow_cylinder_grooved 路径
            if groove_params:
                result['obj_type'] = 'hollow_cylinder_grooved'
                result['outer_bottom_radius'] = result['outer_radius']
                result['outer_top_radius'] = result['outer_radius']
                result['inner_bottom_radius'] = result['inner_radius_bottom']
                result['inner_top_radius'] = result['inner_radius_top']
                result.update(groove_params)
                log_to_file(f"[STEP Exporter]   -> hollow_cylinder_grooved! groove_depth={groove_params.get('groove_depth', 0):.4f}")
                return result
            if hole_fillet_r > 0 and not has_outer_feature:
                result['top_feature'] = 'fillet'
                result['top_feature_size'] = hole_fillet_r
                result['bottom_feature'] = 'fillet'
                result['bottom_feature_size'] = hole_fillet_r
                result['obj_type'] = 'hollow_cylinder_tapered'
            return result
        if hole_position in ('stepped', 'tapered_stepped'):
            # Stepped through hole or tapered stepped through hole
            is_tpr = (hole_position == 'tapered_stepped')
            # 检测是否为锥体：底面/顶面半径差 > 5%（无视 cylindrical_body 误判）
            is_cone_body = abs(bottom_radius - top_radius) > max(bottom_radius, top_radius) * 0.05
            # 从 stepped_hole_params 或 mesh 数据获取台阶孔参数
            shp = stepped_hole_params if stepped_hole_params else {}
            # 非锥台阶孔：内外径应一致，优先用存储属性避免 mesh 误检导致 taper_at_top 误判
            if hole_position == 'stepped':
                stored_large_r = (obj.get('hole_stepped_large_r', 0) if hasattr(obj, 'get') else 0) * 0.001  # mm→m
                if stored_large_r > 0:
                    inner_btm = stored_large_r
                    inner_top = stored_large_r  # 台阶孔大孔段为等径直孔
                else:
                    inner_btm = shp.get('inner_bottom_radius', inner_radius if is_hollow else 0)
                    inner_top = shp.get('inner_top_radius', inner_top_radius if is_hollow else 0)
            else:
                inner_btm = shp.get('inner_bottom_radius', inner_radius if is_hollow else 0)
                inner_top = shp.get('inner_top_radius', inner_top_radius if is_hollow else 0)
            small_r = shp.get('small_hole_radius', 0)
            small_h = shp.get('small_hole_height', 0)
            # 锥体锥形台阶孔 mesh 检测失败时，从存储属性回退
            if is_cone_body and is_tpr and (small_r <= 0 or small_h <= 0):
                stored_opening = (obj.get('hole_opening_radius', 0) if hasattr(obj, 'get') else 0) * 0.001  # mm→m
                stored_end = (obj.get('hole_end_radius', 0) if hasattr(obj, 'get') else 0) * 0.001
                stored_small = (obj.get('hole_stepped_small_r', 0) if hasattr(obj, 'get') else 0) * 0.001
                stored_large_h = (obj.get('hole_stepped_large_h', 0) if hasattr(obj, 'get') else 0) * 0.001  # mm→m
                log_to_file(f"[STEP Exporter]   tapered_stepped fallback: opening={stored_opening:.3f} end={stored_end:.3f} small={stored_small:.3f} large_h={stored_large_h:.3f}")
                if stored_opening > 0 and stored_end > 0:
                    inner_btm = stored_end
                    inner_top = stored_opening
                    if stored_small > 0:
                        small_r = stored_small
                    if stored_large_h > 0:
                        small_h = height - stored_large_h  # 直孔高度 = 总高 - 大孔高
                    log_to_file(f"[STEP Exporter]   tapered_stepped fallback result: small_r={small_r:.3f} small_h={small_h:.3f} inner_btm={inner_btm:.3f} inner_top={inner_top:.3f}")
            # 锥体台阶孔 → 使用 cone_stepped_hole 类型
            if is_cone_body and inner_btm > 0 and inner_top > 0 and small_r > 0 and small_h > 0:
                hole_fr = (obj.get('hole_fillet_radius', 0) if hasattr(obj, 'get') else 0)  # 已经是 mm
                # 读取存储的边特征（比 mesh 检测更可靠）
                stored_ct = obj.get('chamfer_type') if hasattr(obj, 'get') else None
                stored_fr = obj.get('fillet_radius_edge', 0) if hasattr(obj, 'get') else 0  # mm
                stored_csz = obj.get('chamfer_size', 0) if hasattr(obj, 'get') else 0  # mm
                # 优先使用存储属性，避免 mesh 误检
                if stored_ct in ('chamfer', 'chamfer_both', 'chamfer_fillet'):
                    top_feature = 'chamfer'; top_feature_size = stored_csz * 0.001
                elif stored_ct in ('fillet', 'fillet_both'):
                    top_feature = 'fillet'; top_feature_size = stored_fr * 0.001
                elif stored_ct in ('bottom_chamfer',):
                    top_feature = None; top_feature_size = 0
                    bottom_feature = 'chamfer'; bottom_feature_size = stored_csz * 0.001
                elif stored_ct in ('bottom_fillet',):
                    top_feature = None; top_feature_size = 0
                    bottom_feature = 'fillet'; bottom_feature_size = stored_fr * 0.001
                elif stored_ct is None:
                    # 无存储属性 = 无边缘特征，忽略 mesh 检测
                    top_feature = None; top_feature_size = 0
                    bottom_feature = None; bottom_feature_size = 0
                # 锥体台阶孔 C++ 已支持 chamfer + fillet 分层处理
                result = {
                    'obj_type': 'cone_stepped_hole_groove' if (has_groove_custom and groove_params and groove_params.get('groove_depth', 0) > 0) else 'cone_stepped_hole',
                    'outer_bottom_radius': max(bottom_radius, top_radius) * S,
                    'outer_top_radius': min(bottom_radius, top_radius) * S,
                    'height': height * S,
                    'small_hole_radius': small_r * S,
                    'small_hole_height': small_h * S,
                    'inner_bottom_radius': inner_btm * S,
                    'inner_top_radius': inner_top * S,
                    'hole_fillet_radius': hole_fr,
                    'top_feature': top_feature,
                    'top_feature_size': (top_feature_size if top_feature else 0) * S,
                    'bottom_feature': bottom_feature,
                    'bottom_feature_size': (bottom_feature_size if bottom_feature else 0) * S,
                    'pos_x': pos_x * S,
                    'pos_y': pos_y * S,
                    'pos_z': pos_z * S,
                    'groove_depth': groove_params.get('groove_depth', 0) if groove_params else 0,
                    'groove_bottom_width': groove_params.get('groove_bottom_width', 0) if groove_params else 0,
                    'groove_top_width': groove_params.get('groove_top_width', 0) if groove_params else 0,
                    'groove_extrusion_length': groove_params.get('groove_extrusion_length', 0) if groove_params else 0,
                }
                # 当外边缘有 chamfer/fillet 时，缩小锥孔口径以留出孔圆角空间
                # 外边缘特征会削减顶部面半径，OCC Build 失败当 wall < hole_fillet*1.1
                outer_t = result['outer_top_radius']
                outer_b = result['outer_bottom_radius']
                outer_top_sz = (top_feature_size * S) if top_feature in ('chamfer', 'fillet') and top_feature_size > 0 else 0
                outer_btm_sz = (bottom_feature_size * S) if bottom_feature in ('chamfer', 'fillet') and bottom_feature_size > 0 else 0
                if outer_top_sz > 0:
                    need_wall = outer_top_sz + hole_fr * 1.2
                    if outer_t - result['inner_top_radius'] < need_wall:
                        new_it = max(outer_t - need_wall, small_r * S + 1.0)
                        log_to_file(f"[STEP Exporter]   Top edge {outer_top_sz:.0f}: shrinking inner_top {result['inner_top_radius']:.0f}→{new_it:.0f} (need wall {need_wall:.0f})")
                        result['inner_top_radius'] = new_it
                        if result['inner_bottom_radius'] > result['inner_top_radius']:
                            result['inner_bottom_radius'] = result['inner_top_radius']
                if outer_btm_sz > 0:
                    need_wall = outer_btm_sz + hole_fr * 1.2
                    if outer_b - result['inner_bottom_radius'] < need_wall:
                        new_ib = max(outer_b - need_wall, small_r * S + 1.0)
                        log_to_file(f"[STEP Exporter]   Bottom edge {outer_btm_sz:.0f}: shrinking inner_bottom {result['inner_bottom_radius']:.0f}→{new_ib:.0f} (need wall {need_wall:.0f})")
                        result['inner_bottom_radius'] = new_ib
                log_to_file(f"[STEP Exporter]   -> cone_stepped_hole! bR={result['outer_bottom_radius']:.1f} tR={result['outer_top_radius']:.1f} h={result['height']:.1f}")
                return result
            # Use stored edge feature properties (more reliable than mesh for stepped holes)
            stored_ct = obj.get('chamfer_type') if hasattr(obj, 'get') else None
            stored_csz = (obj.get('chamfer_size', 0) if hasattr(obj, 'get') else 0) * 0.001  # mm → m
            stored_fr = (obj.get('fillet_radius_edge', 0) if hasattr(obj, 'get') else 0) * 0.001  # mm → m
            if stored_ct == 'chamfer':
                top_ch = stored_csz; top_fr = 0; btm_ch = 0; btm_fr = 0
            elif stored_ct == 'fillet':
                top_ch = 0; top_fr = stored_fr; btm_ch = 0; btm_fr = 0
            elif stored_ct == 'bottom_chamfer':
                top_ch = 0; top_fr = 0; btm_ch = stored_csz; btm_fr = 0
            elif stored_ct == 'bottom_fillet':
                top_ch = 0; top_fr = 0; btm_ch = 0; btm_fr = stored_fr
            elif stored_ct == 'chamfer_both':
                top_ch = stored_csz; top_fr = 0; btm_ch = stored_csz; btm_fr = 0
            elif stored_ct == 'fillet_both':
                top_ch = 0; top_fr = stored_fr; btm_ch = 0; btm_fr = stored_fr
            elif stored_ct == 'chamfer_fillet':
                top_ch = stored_csz; top_fr = 0; btm_ch = 0; btm_fr = stored_fr
            else:
                # Fallback to mesh detection
                top_ch = top_feature_size if top_feature == 'chamfer' else 0
                top_fr = top_feature_size if top_feature == 'fillet' else 0
                btm_ch = bottom_feature_size if bottom_feature == 'chamfer' else 0
                btm_fr = bottom_feature_size if bottom_feature == 'fillet' else 0
            if is_tpr:
                result = {
                    'obj_type': 'cylinder_tapered_stepped_hole',
                    'radius': (max(z_radius_data.values()) if stored_ct in ('chamfer_both', 'fillet_both', 'chamfer_fillet')
                               else max(bottom_radius, top_radius)) * S,
                    'height': height * S,
                    'stepped_large_h': (obj.get('hole_stepped_large_h', 0) if hasattr(obj, 'get') else 0),
                    'taper_top_r': (obj.get('hole_taper_top_r', 0) if hasattr(obj, 'get') else 0),
                    'taper_step_r': (obj.get('hole_taper_step_r', 0) if hasattr(obj, 'get') else 0),
                    'stepped_small_r': (obj.get('hole_stepped_small_r', 0) if hasattr(obj, 'get') else 0),
                    'hole_fillet_radius': (obj.get('hole_fillet_radius', 0) if hasattr(obj, 'get') else 0),
                    'top_chamfer': top_ch * S,
                    'top_fillet': top_fr * S,
                    'bottom_chamfer': btm_ch * S,
                    'bottom_fillet': btm_fr * S,
                    'pos_x': pos_x * S,
                    'pos_y': pos_y * S,
                    'pos_z': pos_z * S,
                    'groove_depth': groove_params.get('groove_depth', 0) if groove_params else 0,
                    'groove_bottom_width': groove_params.get('groove_bottom_width', 0) if groove_params else 0,
                    'groove_top_width': groove_params.get('groove_top_width', 0) if groove_params else 0,
                    'groove_extrusion_length': groove_params.get('groove_extrusion_length', 0) if groove_params else 0,
                }
            else:
                result = {
                    'obj_type': 'cylinder_stepped_hole',
                    'radius': (max(z_radius_data.values()) if stored_ct in ('chamfer_both', 'fillet_both', 'chamfer_fillet')
                               else max(bottom_radius, top_radius)) * S,
                    'height': height * S,
                    'stepped_large_r': (obj.get('hole_stepped_large_r', 0) if hasattr(obj, 'get') else 0),
                    'stepped_large_h': (obj.get('hole_stepped_large_h', 0) if hasattr(obj, 'get') else 0),
                    'stepped_small_r': (obj.get('hole_stepped_small_r', 0) if hasattr(obj, 'get') else 0),
                    'hole_fillet_radius': (obj.get('hole_fillet_radius', 0) if hasattr(obj, 'get') else 0),
                    'top_chamfer': top_ch * S,
                    'top_fillet': top_fr * S,
                    'bottom_chamfer': btm_ch * S,
                    'bottom_fillet': btm_fr * S,
                    'pos_x': pos_x * S,
                    'pos_y': pos_y * S,
                    'pos_z': pos_z * S,
                    'groove_depth': groove_params.get('groove_depth', 0) if groove_params else 0,
                    'groove_bottom_width': groove_params.get('groove_bottom_width', 0) if groove_params else 0,
                    'groove_top_width': groove_params.get('groove_top_width', 0) if groove_params else 0,
                    'groove_extrusion_length': groove_params.get('groove_extrusion_length', 0) if groove_params else 0,
                }
            log_to_file(f"[STEP Exporter]   -> {result['obj_type']}! r={result['radius']} h={result['height']}")
            return result
        if hole_position == 'bottom':
            # 底部盲孔：如果 hole_radius/hole_depth 已在检测阶段设置，直接使用
            if hole_radius > 0 and hole_depth > 0:
                log_to_file(f"[STEP Exporter]   Using pre-computed blind hole params: hole_r={hole_radius:.4f} hole_d={hole_depth:.4f}")
            else:
                # 优先通过中间层内孔簇计算孔半径和深度
                hole_radius_from_cluster = False
                # 尝试在任何有两簇的层提取内孔半径（不限于底部层）
                for zl in sorted_z[:-1]:  # 检查所有非顶层
                    if len(z_layers[zl]) >= 16:
                        zl_radii = sorted(compute_radii(z_layers[zl]))
                        zl_cluster, zl_outer = has_two_clusters(zl_radii)
                        if zl_cluster:
                            n_z = len(zl_radii)
                            zl_inner = zl_radii[:n_z - len(zl_outer)]
                            inner_r = sorted(zl_inner)[len(zl_inner)//2] if zl_inner else 0
                            # 找内孔消失Z层
                            hole_end_z = zl
                            for zl2 in sorted_z[sorted_z.index(zl)+1:]:
                                if len(z_layers[zl2]) >= 16:
                                    zl2_radii = sorted(compute_radii(z_layers[zl2]))
                                    zl2_cluster, _ = has_two_clusters(zl2_radii)
                                    if zl2_cluster:
                                        hole_end_z = zl2
                                    else:
                                        break
                            hole_depth = hole_end_z - sorted_z[0]
                            if inner_r > 0.001 and hole_depth > height * 0.1:
                                hole_radius = inner_r
                                hole_radius_from_cluster = True
                                log_to_file(f"[STEP Exporter]   Bottom blind hole via cluster at z={zl:.4f}: inner_r={inner_r:.4f} hole_depth={hole_depth:.4f}")
                                break
                if not hole_radius_from_cluster:
                    # 回退：用顶点数比值法估算孔参数
                    bot_vc = len(z_layers[sorted_z[0]])
                    top_vc = len(z_layers[sorted_z[-1]])
                    if bot_vc > top_vc * 3:
                        b_radii = sorted(compute_radii(z_layers[sorted_z[0]]))
                        inner_count = max(4, len(b_radii) // 10)
                        hole_radius = sorted(b_radii[:inner_count])[inner_count//2]
                        # 孔深：底部以上顶点数最多的Z层（孔底平面）
                        best_z = sorted_z[0]
                        best_vc = 0
                        for zl in sorted_z[1:-1]:
                            vc = len(z_layers[zl])
                            if vc > best_vc:
                                best_vc = vc
                                best_z = zl
                        hole_end_z = best_z if best_vc > top_vc * 2 else sorted_z[0]
                        hole_depth = hole_end_z - sorted_z[0]
                        log_to_file(f"[STEP Exporter]   Bottom blind hole via vcount fallback: inner_r={hole_radius:.4f} hole_depth={hole_depth:.4f}")
                    else:
                        below_zls = [zl for zl in sorted_z if zl < body_end_z and zl in z_radius_data]
                        if below_zls:
                            hole_depth = body_end_z - sorted_z[0]
                            hole_wall_r = sorted([z_radius_data[zl] for zl in below_zls])
                            hole_radius = hole_wall_r[len(hole_wall_r)//2]
                        else:
                            hole_depth = height * 0.5
                            hole_radius = body_radius * 0.5
            body_radius_for_export = top_radius
        elif hole_position == 'both':
            # 双端盲孔：检测阶段已设置 hole_radius, hole_depth (底部), hole_depth_top (顶部)
            body_radius_for_export = top_radius
            log_to_file(f"[STEP Exporter]   Dual blind holes: using pre-computed params btm_d={hole_depth:.4f} top_d={hole_depth_top:.4f}")
        else:
            # 顶部盲孔
            # 优先使用检测阶段预计算的 hole_radius/hole_depth（来自存储属性覆盖时）
            if hole_radius > 0 and hole_depth > 0:
                log_to_file(f"[STEP Exporter]   Using pre-computed top blind hole params: hole_r={hole_radius:.4f} hole_d={hole_depth:.4f}")
            else:
                above_zls = [zl for zl in sorted_z if zl > body_end_z and zl in z_radius_data]
                if above_zls:
                    z_hole_bottom = above_zls[0]
                    hole_depth = sorted_z[-1] - z_hole_bottom
                    hole_wall_zls = [zl for zl in above_zls if zl < sorted_z[-1] * 0.99]
                    if hole_wall_zls:
                        hole_wall_r = sorted([z_radius_data[zl] for zl in hole_wall_zls])
                        hole_radius = hole_wall_r[len(hole_wall_r)//2]
                    else:
                        hole_radius = z_radius_data[above_zls[0]]
                else:
                    hole_depth = height * 0.5
                    hole_radius = body_radius * 0.5
            body_radius_for_export = bottom_radius
        
        log_to_file(f"[STEP Exporter]   -> cylinder_blind_hole! r={body_radius_for_export:.3f} h={height:.3f} hole_r={hole_radius:.3f} hole_d={hole_depth:.3f} pos={hole_position}")
        hole_fillet_r = obj.get('hole_fillet_radius', 0.0) if hasattr(obj, 'get') else 0.0
        hole_is_tapered = obj.get('hole_is_tapered', False) if hasattr(obj, 'get') else False
        hole_r_opening_stored = obj.get('hole_opening_radius', 0.0) if hasattr(obj, 'get') else 0.0
        hole_r_end_stored = obj.get('hole_end_radius', 0.0) if hasattr(obj, 'get') else 0.0
        if hole_fillet_r > 0:
            log_to_file(f"[STEP Exporter]   hole fillet: r={hole_fillet_r:.3f}")
        if hole_is_tapered:
            # 使用存储的精确半径覆盖 mesh 扫描值
            # hole_opening_radius=开口半径(较大), hole_end_radius=孔底半径(较小)
            # Stored properties are in mm; hole_radius is in meters
            if hole_r_opening_stored > 0:
                hole_radius = hole_r_opening_stored * 0.001  # mm → m
            hole_r_bottom = hole_r_end_stored * 0.001  # mm → m
            log_to_file(f"[STEP Exporter]   tapered hole: opening_r={hole_radius:.3f} end_r={hole_r_bottom:.3f}")
        # 读取存储的倒角/圆角参数（用于外缘）
        stored_ctype = obj.get('chamfer_type') if hasattr(obj, 'get') else None
        stored_csz = obj.get('chamfer_size', 0) if hasattr(obj, 'get') else 0
        stored_fr = obj.get('fillet_radius_edge', 0) if hasattr(obj, 'get') else 0
        stored_orig_r = obj.get('cylinder_original_radius', 0) if hasattr(obj, 'get') else 0
        top_ch = 0.0; top_fr = 0.0; btm_ch = 0.0; btm_fr = 0.0
        if stored_ctype == 'chamfer':
            top_ch = stored_csz * 0.001
        elif stored_ctype == 'fillet':
            top_fr = stored_fr * 0.001
        elif stored_ctype == 'bottom_chamfer':
            btm_ch = stored_csz * 0.001
        elif stored_ctype == 'bottom_fillet':
            btm_fr = stored_fr * 0.001
        elif stored_ctype == 'chamfer_both':
            top_ch = stored_csz * 0.001; btm_ch = stored_csz * 0.001
        elif stored_ctype == 'fillet_both':
            top_fr = stored_fr * 0.001; btm_fr = stored_fr * 0.001
        elif stored_ctype == 'chamfer_fillet':
            top_ch = stored_csz * 0.001; btm_fr = stored_fr * 0.001
        # NOTE: mesh-detected chamfer/fillet are unreliable near hole openings.
        # stored_ctype from gallery creation fully specifies all edge features.
        # No fallback to mesh-detected values.
        if stored_orig_r > 0:
            body_radius_for_export = stored_orig_r * 0.001  # use original radius

        # Check if cone body + blind hole (use cone_blind_hole C++ path)
        # Bidirectional: cone can narrow upward or widen upward
        radius_ratio = top_radius / bottom_radius if bottom_radius > 0 else 1.0
        is_cone_like = (radius_ratio < 0.85 or radius_ratio > 1.0 / 0.85)
        # If stored edge feature explains the radius difference, it's a cylinder not cone
        if is_cone_like and stored_ctype:
            # 边缘特征（倒角/圆角）可部分解释半径差，但不能解释大幅差异
            # 只有当倒角大小能覆盖整个半径差时，才认为是圆柱+倒角
            stored_csz_m = stored_csz * 0.001  # mm → m
            stored_fr_m = stored_fr * 0.001
            max_feature = max(stored_csz_m, stored_fr_m)
            if abs(bottom_radius - top_radius) < max_feature * 1.2:
                is_cone_like = False  # 边缘特征能完全解释半径差 → 圆柱
            # 否则保留锥体判断（边缘特征叠加在锥体上）
        if is_cone_like:
            result = {
                'obj_type': 'cone_blind_hole_groove' if (has_groove_custom and groove_params and groove_params.get('groove_depth', 0) > 0) else 'cone_blind_hole',
                'bottom_radius': bottom_radius * S,
                'bottom_radius': bottom_radius * S,
                'top_radius': top_radius * S,
                'height': height * S,
                'hole_radius': hole_radius * S,
                'hole_depth': hole_depth * S,
                'hole_fillet_radius': hole_fillet_r,
                'hole_position': hole_position,
                'top_chamfer': top_ch * S,
                'top_fillet': top_fr * S,
                'bottom_chamfer': btm_ch * S,
                'bottom_fillet': btm_fr * S,
                'pos_x': pos_x * S,
                'pos_y': pos_y * S,
                'pos_z': pos_z * S,
                'groove_depth': groove_params.get('groove_depth', 0) if groove_params else 0,
                'groove_bottom_width': groove_params.get('groove_bottom_width', 0) if groove_params else 0,
                'groove_top_width': groove_params.get('groove_top_width', 0) if groove_params else 0,
                'groove_extrusion_length': groove_params.get('groove_extrusion_length', 0) if groove_params else 0,
            }
            if hole_position == 'both':
                result['hole_depth_top'] = hole_depth_top * S
            if hole_is_tapered and hole_r_bottom > 0:
                result['hole_radius_bottom'] = hole_r_bottom * S
            return result

        result = {
            'obj_type': 'cylinder_blind_hole',
            'radius': body_radius_for_export * S,
            'height': height * S,
            'hole_radius': hole_radius * S,
            'hole_depth': hole_depth * S,
            'hole_fillet_radius': hole_fillet_r,
            'hole_position': hole_position,
            'top_chamfer': top_ch * S,
            'top_fillet': top_fr * S,
            'bottom_chamfer': btm_ch * S,
            'bottom_fillet': btm_fr * S,
            'pos_x': pos_x * S,
            'pos_y': pos_y * S,
            'pos_z': pos_z * S,
            'groove_depth': groove_params.get('groove_depth', 0) if groove_params else 0,
            'groove_bottom_width': groove_params.get('groove_bottom_width', 0) if groove_params else 0,
            'groove_top_width': groove_params.get('groove_top_width', 0) if groove_params else 0,
            'groove_extrusion_length': groove_params.get('groove_extrusion_length', 0) if groove_params else 0,
        }
        if hole_position == 'both':
            result['hole_depth_top'] = hole_depth_top * S
        if hole_is_tapered and hole_r_bottom > 0:
            result['hole_radius_bottom'] = hole_r_bottom * S
        return result
    
    bottom_radius *= S; top_radius *= S; height *= S
    pos_x *= S; pos_y *= S; pos_z *= S
    body_radius *= S
    if is_hollow: inner_radius *= S; inner_top_radius *= S
    if top_feature: top_feature_size *= S
    if bottom_feature: bottom_feature_size *= S
    if groove_params:
        # Groove custom properties are already in display units (mm), matching
        # the post-scaling mesh values. Do NOT multiply by S again.
        pass
    if stepped_hole_params:
        for k in ('small_hole_radius', 'small_hole_height', 'inner_bottom_radius', 'inner_top_radius'):
            if k in stepped_hole_params: stepped_hole_params[k] *= S

    # Grooved external wall: return early with groove result before other classification
    if has_groove_custom:
        is_cone = abs(bottom_radius - top_radius) > max(bottom_radius, top_radius) * 0.01
        # Edge features (chamfer/fillet) make mesh radii differ even for cylinders.
        # If there's an edge feature, the body is cylindrical, not conical.
        # Stored properties always override mesh detection for grooved cylinders
        # because mesh detection is unreliable when the groove disrupts the surface.
        stored_ct = obj.get('chamfer_type') if hasattr(obj, 'get') else None
        stored_csz = obj.get('chamfer_size', 0) if hasattr(obj, 'get') else 0
        stored_fr = obj.get('fillet_radius_edge', 0) if hasattr(obj, 'get') else 0
        log_to_file(f"[STEP Exporter]   [GROOVE:v4] stored_ct={stored_ct} stored_csz={stored_csz} "
                    f"is_cone={is_cone} bR={bottom_radius:.1f} tR={top_radius:.1f} "
                    f"mesh_tf={top_feature} mesh_tfs={top_feature_size if top_feature else 'N/A'}")
        if stored_ct in ('chamfer', 'fillet', 'chamfer_both', 'fillet_both',
                         'bottom_chamfer', 'bottom_fillet', 'chamfer_fillet'):
            has_edge_feature = True
            # Reset mesh-detected features; use stored properties only
            top_feature = None; top_feature_size = 0.0
            bottom_feature = None; bottom_feature_size = 0.0
            if stored_ct in ('chamfer', 'chamfer_both', 'chamfer_fillet'):
                top_feature = 'chamfer'; top_feature_size = stored_csz  # already mm
            if stored_ct in ('fillet', 'fillet_both'):
                top_feature = 'fillet'; top_feature_size = stored_fr
            if stored_ct in ('bottom_chamfer',):
                bottom_feature = 'chamfer'; bottom_feature_size = stored_csz
            if stored_ct in ('bottom_fillet',):
                bottom_feature = 'fillet'; bottom_feature_size = stored_fr
            if stored_ct in ('chamfer_both',):
                bottom_feature = 'chamfer'; bottom_feature_size = stored_csz
            if stored_ct in ('fillet_both',):
                bottom_feature = 'fillet'; bottom_feature_size = stored_fr
            if stored_ct in ('chamfer_fillet',):
                bottom_feature = 'fillet'; bottom_feature_size = stored_fr
        else:
            # No stored properties: use mesh-detected features
            # Filter out false chamfer/fillet detections caused by groove artifacts:
            # a chamfer size equal to the cone taper or >= radius is invalid
            log_to_file(f"[STEP Exporter]   [FILTER:v4] before: tf={top_feature} tfs={top_feature_size:.4f} "
                        f"bf={bottom_feature} bfs={bottom_feature_size:.4f} "
                        f"bR={bottom_radius:.1f} tR={top_radius:.1f} diff={abs(bottom_radius-top_radius):.1f}")
            if top_feature == 'chamfer' and top_feature_size > 0:
                if abs(bottom_radius - top_radius) > 0.001:  # cone shape
                    if top_feature_size >= abs(bottom_radius - top_radius) * 0.95:
                        log_to_file(f"[STEP Exporter]   [FILTER:v4] Clearing top chamfer: "
                                    f"{top_feature_size:.1f} >= {abs(bottom_radius-top_radius)*0.95:.1f} (95% of taper)")
                        top_feature = None; top_feature_size = 0.0
                if top_feature and top_feature_size >= top_radius * 0.9:
                    log_to_file(f"[STEP Exporter]   [FILTER:v4] Clearing top chamfer: "
                                f"{top_feature_size:.1f} >= {top_radius*0.9:.1f} (90% of top_r)")
                    top_feature = None; top_feature_size = 0.0
            if bottom_feature == 'chamfer' and bottom_feature_size > 0:
                if abs(bottom_radius - top_radius) > 0.001:
                    if bottom_feature_size >= abs(bottom_radius - top_radius) * 0.95:
                        bottom_feature = None; bottom_feature_size = 0.0
                if bottom_feature_size >= bottom_radius * 0.9:
                    bottom_feature = None; bottom_feature_size = 0.0
            has_edge_feature = ((top_feature and top_feature != 'none' and top_feature_size > 0.0001) or
                                (bottom_feature and bottom_feature != 'none' and bottom_feature_size > 0.0001))
            log_to_file(f"[STEP Exporter]   [FILTER:v4] after: tf={top_feature} tfs={top_feature_size:.4f} "
                        f"is_cone={is_cone} has_edge={has_edge_feature}")
        if is_cone and has_edge_feature:
            is_cone = False  # Treat as grooved cylinder with edge feature, not cone
        if is_cone:
            result = {
                'obj_type': 'cone_groove',
                'bottom_radius': bottom_radius,
                'top_radius': top_radius,
                'height': height,
                'pos_x': pos_x, 'pos_y': pos_y, 'pos_z': pos_z,
                'top_chamfer': top_feature_size if top_feature == 'chamfer' else 0,
                'top_fillet': top_feature_size if top_feature == 'fillet' else 0,
                'bottom_chamfer': bottom_feature_size if bottom_feature == 'chamfer' else 0,
                'bottom_fillet': bottom_feature_size if bottom_feature == 'fillet' else 0,
            }
        else:
            result = {
                'obj_type': 'grooved_cylinder',
                'radius': (max(z_radius_data.values()) * S if stored_ct in ('chamfer_both', 'fillet_both', 'chamfer_fillet')
                           else max(bottom_radius, top_radius)),
                'height': height,
                'pos_x': pos_x, 'pos_y': pos_y, 'pos_z': pos_z,
                'top_chamfer': top_feature_size if top_feature == 'chamfer' else 0,
                'top_fillet': top_feature_size if top_feature == 'fillet' else 0,
                'bottom_chamfer': bottom_feature_size if bottom_feature == 'chamfer' else 0,
                'bottom_fillet': bottom_feature_size if bottom_feature == 'fillet' else 0,
            }
        result.update(groove_params)
        log_to_file(f"[STEP Exporter]   -> {result['obj_type']}! r={result.get('radius', result.get('bottom_radius','?'))} h={result['height']} "
                    f"top_ch={result.get('top_chamfer',0):.1f} top_fr={result.get('top_fillet',0):.1f} "
                    f"btm_ch={result.get('bottom_chamfer',0):.1f} btm_fr={result.get('bottom_fillet',0):.1f}")
        bm.free()
        return result

    if is_hollow:
        if bottom_radius * 0.98 <= top_radius <= bottom_radius * 1.02:
            # 检查锥形通孔
            hole_is_tapered_thru = obj.get('hole_is_tapered', False) if hasattr(obj, 'get') else False
            # At this point inner_radius is already ×S (mm). Stored properties are also in mm.
            # Use stored values directly, or fall back to mesh-detected inner_radius (also mm).
            inner_end_r = obj.get('hole_end_radius', inner_radius) if hasattr(obj, 'get') else inner_radius
            inner_opening_r = obj.get('hole_opening_radius', inner_radius) if hasattr(obj, 'get') else inner_radius
            
            if hole_is_tapered_thru and abs(inner_opening_r - inner_end_r) > 0.0001:
                obj_type = 'hollow_cylinder_tapered'
                fillet_r = obj.get('hole_fillet_radius', 0.0) if hasattr(obj, 'get') else 0.0
                log_to_file(f"[STEP Exporter]   Tapered through-hole: opening_r={inner_opening_r:.3f} end_r={inner_end_r:.3f}")
                _stored_ct_hol = obj.get('chamfer_type') if hasattr(obj, 'get') else None
                return {
                    'obj_type': obj_type,
                    'outer_radius': (max(z_radius_data.values()) * S if _stored_ct_hol in ('chamfer_both', 'fillet_both', 'chamfer_fillet')
                                     else max(bottom_radius, top_radius)),
                    'inner_radius_top': inner_opening_r,
                    'inner_radius_bottom': inner_end_r,
                    'height': height,
                    'hole_fillet_radius': fillet_r,
                    'pos_x': pos_x,
                    'pos_y': pos_y,
                    'pos_z': pos_z,
                }
            
            # 实心圆柱阶梯孔检测（优先于空心圆柱——台阶孔内壁会被检测为空心）
            if has_stepped_hole:
                _stored_ct_hol2 = obj.get('chamfer_type') if hasattr(obj, 'get') else None
                if hasattr(obj, 'get') and obj.get('hole_is_tapered', False):
                    return {
                        'obj_type': 'cylinder_tapered_stepped_hole',
                        'radius': (max(z_radius_data.values()) * S if _stored_ct_hol2 in ('chamfer_both', 'fillet_both', 'chamfer_fillet')
                                   else max(bottom_radius, top_radius)),
                        'height': height,
                        'stepped_large_h': obj.get('hole_stepped_large_h', 0),
                        'taper_top_r': obj.get('hole_taper_top_r', 0),
                        'taper_step_r': obj.get('hole_taper_step_r', 0),
                        'stepped_small_r': obj.get('hole_stepped_small_r', 0),
                        'hole_fillet_radius': obj.get('hole_fillet_radius', 0),
                        'top_chamfer': top_feature_size if top_feature == 'chamfer' else 0,
                        'top_fillet': top_feature_size if top_feature == 'fillet' else 0,
                        'bottom_chamfer': bottom_feature_size if bottom_feature == 'chamfer' else 0,
                        'bottom_fillet': bottom_feature_size if bottom_feature == 'fillet' else 0,
                        'pos_x': pos_x, 'pos_y': pos_y, 'pos_z': pos_z,
                        'groove_depth': groove_params.get('groove_depth', 0) if groove_params else 0,
                        'groove_bottom_width': groove_params.get('groove_bottom_width', 0) if groove_params else 0,
                        'groove_top_width': groove_params.get('groove_top_width', 0) if groove_params else 0,
                        'groove_extrusion_length': groove_params.get('groove_extrusion_length', 0) if groove_params else 0,
                    }
                return {
                    'obj_type': 'cylinder_stepped_hole',
                    'radius': (max(z_radius_data.values()) * S if _stored_ct_hol2 in ('chamfer_both', 'fillet_both', 'chamfer_fillet')
                               else max(bottom_radius, top_radius)),
                    'height': height,
                    'stepped_large_r': obj.get('hole_stepped_large_r', 0) if hasattr(obj, 'get') else 0,
                    'stepped_large_h': obj.get('hole_stepped_large_h', 0) if hasattr(obj, 'get') else 0,
                    'stepped_small_r': obj.get('hole_stepped_small_r', 0) if hasattr(obj, 'get') else 0,
                    'hole_fillet_radius': obj.get('hole_fillet_radius', 0) if hasattr(obj, 'get') else 0,
                    'top_chamfer': top_feature_size if top_feature == 'chamfer' else 0,
                    'top_fillet': top_feature_size if top_feature == 'fillet' else 0,
                    'bottom_chamfer': bottom_feature_size if bottom_feature == 'chamfer' else 0,
                    'bottom_fillet': bottom_feature_size if bottom_feature == 'fillet' else 0,
                    'pos_x': pos_x, 'pos_y': pos_y, 'pos_z': pos_z,
                    'groove_depth': groove_params.get('groove_depth', 0) if groove_params else 0,
                    'groove_bottom_width': groove_params.get('groove_bottom_width', 0) if groove_params else 0,
                    'groove_top_width': groove_params.get('groove_top_width', 0) if groove_params else 0,
                    'groove_extrusion_length': groove_params.get('groove_extrusion_length', 0) if groove_params else 0,
                    'pos_x': pos_x, 'pos_y': pos_y, 'pos_z': pos_z,
                }

            obj_type = 'hollow_cylinder'
            if top_feature == 'fillet':
                obj_type = 'hollow_cylinder_fillet'
            _stored_ct_hol3 = obj.get('chamfer_type') if hasattr(obj, 'get') else None
            return {
                'obj_type': obj_type,
                'outer_radius': (max(z_radius_data.values()) * S if _stored_ct_hol3 in ('chamfer_both', 'fillet_both', 'chamfer_fillet')
                                 else max(bottom_radius, top_radius)),
                'inner_radius': inner_radius,
                'height': height,
                'pos_x': pos_x,
                'pos_y': pos_y,
                'pos_z': pos_z,
                'top_feature': top_feature,
                'top_feature_size': top_feature_size,
                'bottom_feature': bottom_feature,
                'bottom_feature_size': bottom_feature_size,
            }
        else:
            obj_type = 'hollow_cone'
            if top_feature == 'fillet':
                obj_type = 'hollow_cone_fillet'
            if groove_params:
                obj_type = 'hollow_cone_fillet_grooved'
            if stepped_hole_params:
                obj_type = 'cone_stepped_hole'
            result = {
                'obj_type': obj_type,
                'outer_bottom_radius': bottom_radius,
                'outer_top_radius': top_radius,
                'inner_bottom_radius': inner_radius,
                'inner_top_radius': inner_top_radius,
                'height': height,
                'pos_x': pos_x,
                'pos_y': pos_y,
                'pos_z': pos_z,
                'top_feature': top_feature,
                'top_feature_size': top_feature_size,
                'bottom_feature': bottom_feature,
                'bottom_feature_size': bottom_feature_size,
            }
            if groove_params:
                result.update(groove_params)
            if stepped_hole_params:
                result.update(stepped_hole_params)
                result['inner_bottom_radius'] = stepped_hole_params['inner_bottom_radius']
                result['inner_top_radius'] = stepped_hole_params['inner_top_radius']
            return result
    else:
        # 实心圆柱阶梯孔检测（优先）
        if has_stepped_hole:
            _stored_ct2 = obj.get('chamfer_type') if hasattr(obj, 'get') else None
            if hasattr(obj, 'get') and obj.get('hole_is_tapered', False):
                return {
                    'obj_type': 'cylinder_tapered_stepped_hole',
                    'radius': (max(z_radius_data.values()) * S if _stored_ct2 in ('chamfer_both', 'fillet_both', 'chamfer_fillet')
                               else max(bottom_radius, top_radius)),
                    'height': height,
                    'stepped_large_h': obj.get('hole_stepped_large_h', 0),
                    'taper_top_r': obj.get('hole_taper_top_r', 0),
                    'taper_step_r': obj.get('hole_taper_step_r', 0),
                    'stepped_small_r': obj.get('hole_stepped_small_r', 0),
                    'hole_fillet_radius': obj.get('hole_fillet_radius', 0),
                    'top_chamfer': top_feature_size if top_feature == 'chamfer' else 0,
                    'top_fillet': top_feature_size if top_feature == 'fillet' else 0,
                    'bottom_chamfer': bottom_feature_size if bottom_feature == 'chamfer' else 0,
                    'bottom_fillet': bottom_feature_size if bottom_feature == 'fillet' else 0,
                    'pos_x': pos_x, 'pos_y': pos_y, 'pos_z': pos_z,
                    'groove_depth': groove_params.get('groove_depth', 0) if groove_params else 0,
                    'groove_bottom_width': groove_params.get('groove_bottom_width', 0) if groove_params else 0,
                    'groove_top_width': groove_params.get('groove_top_width', 0) if groove_params else 0,
                    'groove_extrusion_length': groove_params.get('groove_extrusion_length', 0) if groove_params else 0,
                }
            return {
                'obj_type': 'cylinder_stepped_hole',
                'radius': (max(z_radius_data.values()) * S if _stored_ct2 in ('chamfer_both', 'fillet_both', 'chamfer_fillet')
                           else max(bottom_radius, top_radius)),
                'height': height,
                'stepped_large_r': obj.get('hole_stepped_large_r', 0) if hasattr(obj, 'get') else 0,
                'stepped_large_h': obj.get('hole_stepped_large_h', 0) if hasattr(obj, 'get') else 0,
                'stepped_small_r': obj.get('hole_stepped_small_r', 0) if hasattr(obj, 'get') else 0,
                'hole_fillet_radius': obj.get('hole_fillet_radius', 0) if hasattr(obj, 'get') else 0,
                'top_chamfer': top_feature_size if top_feature == 'chamfer' else 0,
                'top_fillet': top_feature_size if top_feature == 'fillet' else 0,
                'bottom_chamfer': bottom_feature_size if bottom_feature == 'chamfer' else 0,
                'bottom_fillet': bottom_feature_size if bottom_feature == 'fillet' else 0,
                'pos_x': pos_x, 'pos_y': pos_y, 'pos_z': pos_z,
                'groove_depth': groove_params.get('groove_depth', 0) if groove_params else 0,
                'groove_bottom_width': groove_params.get('groove_bottom_width', 0) if groove_params else 0,
                'groove_top_width': groove_params.get('groove_top_width', 0) if groove_params else 0,
                'groove_extrusion_length': groove_params.get('groove_extrusion_length', 0) if groove_params else 0,
            }
        # 实心圆柱外壁槽检测
        if has_groove_custom:
            is_cone = abs(bottom_radius - top_radius) > max(bottom_radius, top_radius) * 0.01
            # Stored properties always override mesh detection for grooved cylinders
            stored_ct = obj.get('chamfer_type') if hasattr(obj, 'get') else None
            stored_csz = obj.get('chamfer_size', 0) if hasattr(obj, 'get') else 0
            stored_fr = obj.get('fillet_radius_edge', 0) if hasattr(obj, 'get') else 0
            log_to_file(f"[STEP Exporter]   [GROOVE2:v4] stored_ct={stored_ct} stored_csz={stored_csz} "
                        f"is_cone={is_cone} bR={bottom_radius:.1f} tR={top_radius:.1f} "
                        f"mesh_tf={top_feature} mesh_tfs={top_feature_size if top_feature else 'N/A'}")
            if stored_ct in ('chamfer', 'fillet', 'chamfer_both', 'fillet_both',
                             'bottom_chamfer', 'bottom_fillet', 'chamfer_fillet'):
                has_edge_feature2 = True
                # Reset mesh-detected features; use stored properties only
                top_feature = None; top_feature_size = 0.0
                bottom_feature = None; bottom_feature_size = 0.0
                if stored_ct in ('chamfer', 'chamfer_both', 'chamfer_fillet'):
                    top_feature = 'chamfer'; top_feature_size = stored_csz  # already mm
                if stored_ct in ('fillet', 'fillet_both'):
                    top_feature = 'fillet'; top_feature_size = stored_fr
                if stored_ct in ('bottom_chamfer',):
                    bottom_feature = 'chamfer'; bottom_feature_size = stored_csz
                if stored_ct in ('bottom_fillet',):
                    bottom_feature = 'fillet'; bottom_feature_size = stored_fr
                if stored_ct in ('chamfer_both',):
                    bottom_feature = 'chamfer'; bottom_feature_size = stored_csz
                if stored_ct in ('fillet_both',):
                    bottom_feature = 'fillet'; bottom_feature_size = stored_fr
                if stored_ct in ('chamfer_fillet',):
                    bottom_feature = 'fillet'; bottom_feature_size = stored_fr
            else:
                # Filter out false chamfer/fillet detections from groove artifacts
                log_to_file(f"[STEP Exporter]   [FILTER2:v4] before: tf={top_feature} tfs={top_feature_size:.4f} "
                            f"bf={bottom_feature} bfs={bottom_feature_size:.4f} "
                            f"bR={bottom_radius:.1f} tR={top_radius:.1f} diff={abs(bottom_radius-top_radius):.1f}")
                if top_feature == 'chamfer' and top_feature_size > 0:
                    if abs(bottom_radius - top_radius) > 0.001:
                        if top_feature_size >= abs(bottom_radius - top_radius) * 0.95:
                            log_to_file(f"[STEP Exporter]   [FILTER2:v4] Clearing top chamfer: "
                                        f"{top_feature_size:.1f} >= {abs(bottom_radius-top_radius)*0.95:.1f}")
                            top_feature = None; top_feature_size = 0.0
                    if top_feature and top_feature_size >= top_radius * 0.9:
                        log_to_file(f"[STEP Exporter]   [FILTER2:v4] Clearing top chamfer (radius): "
                                    f"{top_feature_size:.1f} >= {top_radius*0.9:.1f}")
                        top_feature = None; top_feature_size = 0.0
                if bottom_feature == 'chamfer' and bottom_feature_size > 0:
                    if abs(bottom_radius - top_radius) > 0.001:
                        if bottom_feature_size >= abs(bottom_radius - top_radius) * 0.95:
                            bottom_feature = None; bottom_feature_size = 0.0
                    if bottom_feature_size >= bottom_radius * 0.9:
                        bottom_feature = None; bottom_feature_size = 0.0
                has_edge_feature2 = ((top_feature and top_feature != 'none' and top_feature_size > 0.0001) or
                                     (bottom_feature and bottom_feature != 'none' and bottom_feature_size > 0.0001))
                log_to_file(f"[STEP Exporter]   [FILTER2:v4] after: tf={top_feature} tfs={top_feature_size:.4f} "
                            f"is_cone={is_cone} has_edge2={has_edge_feature2}")
            if is_cone and has_edge_feature2:
                is_cone = False  # Treat as grooved cylinder with edge feature, not cone
            if is_cone:
                result = {
                    'obj_type': 'cone_groove',
                    'bottom_radius': bottom_radius,
                    'top_radius': top_radius,
                    'height': height,
                    'pos_x': pos_x, 'pos_y': pos_y, 'pos_z': pos_z,
                    'top_chamfer': top_feature_size if top_feature == 'chamfer' else 0,
                    'top_fillet': top_feature_size if top_feature == 'fillet' else 0,
                    'bottom_chamfer': bottom_feature_size if bottom_feature == 'chamfer' else 0,
                    'bottom_fillet': bottom_feature_size if bottom_feature == 'fillet' else 0,
                }
            else:
                result = {
                    'obj_type': 'grooved_cylinder',
                    'radius': (max(z_radius_data.values()) * S if stored_ct in ('chamfer_both', 'fillet_both', 'chamfer_fillet')
                               else max(bottom_radius, top_radius)),
                    'height': height,
                    'pos_x': pos_x, 'pos_y': pos_y, 'pos_z': pos_z,
                    'top_chamfer': top_feature_size if top_feature == 'chamfer' else 0,
                    'top_fillet': top_feature_size if top_feature == 'fillet' else 0,
                    'bottom_chamfer': bottom_feature_size if bottom_feature == 'chamfer' else 0,
                    'bottom_fillet': bottom_feature_size if bottom_feature == 'fillet' else 0,
                }
            result.update(groove_params)
            return result
        # 圆柱带倒角/圆角回退：mesh 检测可能漏掉底部特征，用 stored_ctype 修正
        stored_ctype_cls = obj.get('chamfer_type') if hasattr(obj, 'get') else None
        stored_orig_cls = obj.get('cylinder_original_radius', 0) if hasattr(obj, 'get') else 0
        is_cyl_feature = stored_ctype_cls in ('chamfer', 'bottom_chamfer', 'chamfer_both',
                                               'fillet', 'bottom_fillet', 'fillet_both',
                                               'chamfer_fillet')
        if is_cyl_feature:
            # Determine the original cylinder radius
            if stored_orig_cls > 0:
                orig_r = stored_orig_cls  # already in mm (all radii scaled by S)
            elif body_radius and body_radius > 0:
                orig_r = body_radius  # use body radius as fallback (no-hole objects lack cylinder_original_radius)
            else:
                orig_r = max(bottom_radius, top_radius)
            if bottom_radius * 0.85 <= orig_r <= bottom_radius * 1.25 and top_radius * 0.85 <= orig_r <= top_radius * 1.25:
                avg_radius = orig_r
                bottom_radius = orig_r
                top_radius = orig_r
            elif bottom_radius * 0.98 <= top_radius <= bottom_radius * 1.02:
                if body_radius and abs(body_radius - bottom_radius) / max(bottom_radius, 0.001) > 0.02:
                    avg_radius = body_radius
                else:
                    avg_radius = (bottom_radius + top_radius) / 2.0
            else:
                avg_radius = (bottom_radius + top_radius) / 2.0
                # Still mismatched: fall through to cone
                if abs(bottom_radius - top_radius) / max(bottom_radius, 0.001) > 0.05:
                    obj_type = 'cone'
                    if top_feature and bottom_feature:
                        if top_feature == 'chamfer' and bottom_feature == 'chamfer':
                            obj_type = 'cone_chamfer'
                        elif top_feature == 'fillet' and bottom_feature == 'fillet':
                            obj_type = 'cone_fillet'
                        else:
                            obj_type = 'cone_chamfer_fillet'
                    elif top_feature:
                        obj_type = 'cone_chamfer' if top_feature == 'chamfer' else 'cone_fillet'
                    elif bottom_feature:
                        obj_type = 'cone_chamfer' if bottom_feature == 'chamfer' else 'cone_fillet'
                    log_to_file(f"[STEP Exporter]   CLASSIFIED: {obj_type} bR={bottom_radius:.6f} tR={top_radius:.6f} h={height:.6f}")
                    return {
                        'obj_type': obj_type,
                        'bottom_radius': bottom_radius,
                        'top_radius': top_radius,
                        'height': height,
                        'top_feature': top_feature,
                        'top_feature_size': top_feature_size,
                        'bottom_feature': bottom_feature,
                        'bottom_feature_size': bottom_feature_size,
                        'pos_x': pos_x, 'pos_y': pos_y, 'pos_z': pos_z,
                    }
            # Cylinder with chamfer/fillet: use stored_ctype to determine obj_type
            # Read stored feature sizes from object properties (mm, already scaled by S in this context)
            stored_ch_sz = obj.get('chamfer_size', 0) if hasattr(obj, 'get') else 0
            stored_fr_r = obj.get('fillet_radius_edge', 0) if hasattr(obj, 'get') else 0
            obj_type = 'cylinder'
            # Reset features based on stored_ctype (mesh may not detect them)
            out_top_feat = None; out_top_sz = 0.0
            out_bot_feat = None; out_bot_sz = 0.0
            if stored_ctype_cls == 'chamfer':
                obj_type = 'cylinder_chamfer'
                out_top_feat = 'chamfer'; out_top_sz = stored_ch_sz
            elif stored_ctype_cls == 'bottom_chamfer':
                obj_type = 'cylinder_chamfer'
                out_bot_feat = 'chamfer'; out_bot_sz = stored_ch_sz
            elif stored_ctype_cls == 'chamfer_both':
                obj_type = 'cylinder_chamfer_both'
                out_top_feat = 'chamfer'; out_top_sz = stored_ch_sz
                out_bot_feat = 'chamfer'; out_bot_sz = stored_ch_sz
            elif stored_ctype_cls == 'fillet':
                obj_type = 'cylinder_fillet'
                out_top_feat = 'fillet'; out_top_sz = stored_fr_r
            elif stored_ctype_cls == 'bottom_fillet':
                obj_type = 'cylinder_fillet'
                out_bot_feat = 'fillet'; out_bot_sz = stored_fr_r
            elif stored_ctype_cls == 'fillet_both':
                obj_type = 'cylinder_fillet_both'
                out_top_feat = 'fillet'; out_top_sz = stored_fr_r
                out_bot_feat = 'fillet'; out_bot_sz = stored_fr_r
            elif stored_ctype_cls == 'chamfer_fillet':
                obj_type = 'cylinder_chamfer_fillet'
                out_top_feat = 'chamfer'; out_top_sz = stored_ch_sz
                out_bot_feat = 'fillet'; out_bot_sz = stored_fr_r
            return {
                'obj_type': obj_type,
                'radius': avg_radius,
                'height': height,
                'pos_x': pos_x, 'pos_y': pos_y, 'pos_z': pos_z,
                'top_feature': out_top_feat,
                'top_feature_size': out_top_sz,
                'bottom_feature': out_bot_feat,
                'bottom_feature_size': out_bot_sz,
            }
        elif bottom_radius * 0.98 <= top_radius <= bottom_radius * 1.02:
            # 使用体半径（过渡检测中已修正），避免极端z层混入面顶点导致半径偏小
            if body_radius and abs(body_radius - bottom_radius) / max(bottom_radius, 0.001) > 0.02:
                avg_radius = body_radius
            else:
                avg_radius = (bottom_radius + top_radius) / 2.0
            obj_type = 'cylinder'
            if top_feature == 'chamfer':
                if bottom_feature == 'fillet':
                    obj_type = 'cylinder_chamfer_fillet'
                elif bottom_feature == 'chamfer':
                    obj_type = 'cylinder_chamfer_both'
                else:
                    obj_type = 'cylinder_chamfer'
            elif top_feature == 'fillet':
                if bottom_feature == 'chamfer':
                    obj_type = 'cylinder_chamfer_fillet'  # reversed: chamfer at bottom
                elif bottom_feature == 'fillet':
                    obj_type = 'cylinder_fillet_both'
                else:
                    obj_type = 'cylinder_fillet'
            elif bottom_feature == 'fillet':
                obj_type = 'cylinder_fillet'
            elif bottom_feature == 'chamfer':
                obj_type = 'cylinder_chamfer'
            return {
                'obj_type': obj_type,
                'radius': avg_radius,
                'height': height,
                'pos_x': pos_x,
                'pos_y': pos_y,
                'pos_z': pos_z,
                'top_feature': top_feature,
                'top_feature_size': top_feature_size,
                'bottom_feature': bottom_feature,
                'bottom_feature_size': bottom_feature_size,
            }
        else:
            obj_type = 'cone'
            if top_feature and bottom_feature:
                if top_feature == 'chamfer' and bottom_feature == 'chamfer':
                    obj_type = 'cone_chamfer'
                elif top_feature == 'fillet' and bottom_feature == 'fillet':
                    obj_type = 'cone_fillet'
                else:
                    obj_type = 'cone_chamfer_fillet'
            elif top_feature == 'chamfer' or bottom_feature == 'chamfer':
                obj_type = 'cone_chamfer'
            elif top_feature == 'fillet' or bottom_feature == 'fillet':
                obj_type = 'cone_fillet'
            # 锥体 + 特征：从过渡区边界获取正确的本体半径
            # body_radius 初始化为 bottom_radius（极端面半径），对于锥体不适用
            body_bot_r = bottom_radius
            body_top_r = top_radius
            if bottom_feature and bottom_transition_zls:
                bzls = sorted(bottom_transition_zls)
                if bzls:
                    body_bot_r = z_radius_data.get(bzls[-1], bottom_radius / S) * S
                    log_to_file(f"[STEP Exporter]   body_bot: z_range=[{bzls[0]:.6f},{bzls[-1]:.6f}] zls={len(bzls)} -> r={body_bot_r:.6f}")
            if top_feature and top_transition_zls:
                tzls = sorted(top_transition_zls)
                if tzls:
                    body_top_r = z_radius_data.get(tzls[0], top_radius / S) * S
                    log_to_file(f"[STEP Exporter]   body_top: z_range=[{tzls[0]:.6f},{tzls[-1]:.6f}] zls={len(tzls)} -> r={body_top_r:.6f}")
            log_to_file(f"[STEP Exporter]   CLASSIFIED: {obj_type} bR={body_bot_r:.6f} tR={body_top_r:.6f} h={height:.6f}")
            return {
                'obj_type': obj_type,
                'bottom_radius': body_bot_r,
                'top_radius': body_top_r,
                'height': height,
                'pos_x': pos_x,
                'pos_y': pos_y,
                'pos_z': pos_z,
                'top_feature': top_feature,
                'top_feature_size': top_feature_size,
                'bottom_feature': bottom_feature,
                'bottom_feature_size': bottom_feature_size,
            }


