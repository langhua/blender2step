"""Top shell shape analysis.

=== 单位约定 (Unit Convention) ===
内部计算: 米 (Blender 原生单位)
分析结果 (返回 dict): 毫米 (mm) — ×S (S=1000)
C++ 导出函数: 毫米 (mm)
STEP 文件输出: 毫米 (mm)

注意: window_data 字符串中的数值由调用方 (create_top_shell.py) 负责使用 mm 单位。
"""
import sys, math
import bmesh
from mathutils import Vector
from ..core.utils import log_to_file
from ..core import _globals as _g

def _analyze_top_shell_from_mesh(obj, context, scale):
    """
    从 mesh 分析识别是否为顶壳类型（锥形/渐变截面），并测量所有参数
    顶壳特征：顶部面顶点数显著少于底部开口（vratio < 0.75）
    
    返回:
        dict: 包含顶壳参数的字典，如果不是顶壳则返回 None
    """
    if obj.type != 'MESH':
        return None
    
    import bmesh
    import math
    from collections import defaultdict
    
    log_to_file(f"[STEP Exporter] Analyzing mesh for TOP shell: {obj.name}")
    
    depsgraph = context.evaluated_depsgraph_get()
    eval_obj = obj.evaluated_get(depsgraph)
    mesh_data = eval_obj.data
    
    bm = bmesh.new()
    bm.from_mesh(mesh_data)
    bm.verts.ensure_lookup_table()
    
    vertices = bm.verts
    if len(vertices) < 100:
        log_to_file(f"[STEP Exporter] Too few vertices ({len(vertices)}), not a top shell")
        bm.free()
        return None
    
    # Z层分析
    z_layers = defaultdict(list)
    for v in vertices:
        z_key = round(v.co.z / 0.01) * 0.01
        z_layers[z_key].append(v)
    
    sorted_z_levels = sorted(z_layers.keys())
    if len(sorted_z_levels) < 2:
        log_to_file(f"[STEP Exporter] Not enough z-levels, not a top shell")
        bm.free()
        return None
    
    min_z = sorted_z_levels[0]
    max_z = sorted_z_levels[-1]
    bottom_z = min_z
    top_z = max_z
    outer_height = top_z - bottom_z
    
    bottom_verts = z_layers[bottom_z]
    top_verts = z_layers[top_z]
    
    if len(bottom_verts) < 50 or len(top_verts) < 8:
        log_to_file(f"[STEP Exporter] No clear bottom/top planes, not a top shell")
        bm.free()
        return None
    
    # 关键判断：top面顶点应显著少于bottom（因为top面内收，面积小）
    top_vcount = len(top_verts)
    bot_vcount = len(bottom_verts)
    vratio = top_vcount / max(bot_vcount, 1)
    log_to_file(f"[STEP Exporter] Vertex count: top={top_vcount}, bottom={bot_vcount}, ratio={vratio:.3f}")
    
    if vratio >= 0.75:
        log_to_file(f"[STEP Exporter] Top-face vertex ratio >= 0.75 → NOT a top shell")
        bm.free()
        return None
    
    log_to_file(f"[STEP Exporter] Top-face has fewer vertices → TOP shell candidate")
    
    # === 计算底部（开口端）的外轮廓尺寸 ===
    bottom_coords = [(v.co.x, v.co.y, v.co.z) for v in bottom_verts]
    
    # === 圆形轮廓检测：排除圆柱体误判为顶壳 ===
    # 计算底部顶点到中心的距离，如果接近圆形则不是顶壳
    bot_dists = [math.sqrt(x*x + y*y) for x, y, z in bottom_coords]
    if bot_dists:
        mean_dist = sum(bot_dists) / len(bot_dists)
        log_to_file(f"[STEP Exporter] Top-shell circularity check: mean_dist={mean_dist:.4f}, n={len(bot_dists)}")
        if mean_dist > 0.001:
            std_dist = math.sqrt(sum((d - mean_dist)**2 for d in bot_dists) / len(bot_dists))
            circularity = std_dist / mean_dist  # 越小越圆
            log_to_file(f"[STEP Exporter] Top-shell circularity: std={std_dist:.4f}, circ={circularity:.4f}")
            if circularity < 0.02:
                log_to_file(f"[STEP Exporter] Bottom contour is circular (circ={circularity:.3f}) → NOT a top shell (likely cylinder)")
                bm.free()
                return None
        else:
            log_to_file(f"[STEP Exporter] Top-shell mean_dist too small ({mean_dist:.4f}) → likely not a shell")
    
    bottom_x_vals = [x for x, y, z in bottom_coords]
    bottom_y_vals = [y for x, y, z in bottom_coords]
    bot_width = max(bottom_x_vals) - min(bottom_x_vals)
    bot_depth = max(bottom_y_vals) - min(bottom_y_vals)
    bot_cx = (max(bottom_x_vals) + min(bottom_x_vals)) / 2.0
    bot_cy = (max(bottom_y_vals) + min(bottom_y_vals)) / 2.0

    log_to_file(f"[STEP Exporter] Bottom contour: {bot_width:.4f}x{bot_depth:.4f}, center=({bot_cx:.4f},{bot_cy:.4f})")

    # === 计算顶部（封闭面）的轮廓尺寸 ===
    top_coords = [(v.co.x, v.co.y, v.co.z) for v in top_verts]

    if top_coords:
        top_x_vals = [x for x, y, z in top_coords]
        top_y_vals = [y for x, y, z in top_coords]
        top_width = max(top_x_vals) - min(top_x_vals)
        top_depth = max(top_y_vals) - min(top_y_vals)
        top_cx = (max(top_x_vals) + min(top_x_vals)) / 2.0
        top_cy = (max(top_y_vals) + min(top_y_vals)) / 2.0
    else:
        top_width = 0
        top_depth = 0
        top_cx = bot_cx
        top_cy = bot_cy

    # 顶壳经过 180° X 翻转后，宽面可能在顶部(max_z)，窄面在底部(min_z)
    # 确保 width/depth 取自宽面（外壳轮廓），top_width/top_depth 取自窄面
    if bot_width < top_width:
        log_to_file(f"[STEP Exporter] Bottom is narrow face, top is wide face -> swapping")
        width, depth, cx, cy = top_width, top_depth, top_cx, top_cy
        top_width, top_depth, top_cx, top_cy = bot_width, bot_depth, bot_cx, bot_cy
    else:
        width, depth, cx, cy = bot_width, bot_depth, bot_cx, bot_cy

    half_w = width / 2.0
    half_d = depth / 2.0
    log_to_file(f"[STEP Exporter] Outer (wide) contour: {width:.4f}x{depth:.4f}, center=({cx:.4f},{cy:.4f})")
    log_to_file(f"[STEP Exporter] Inner (narrow) contour: {top_width:.4f}x{top_depth:.4f}, center=({top_cx:.4f},{top_cy:.4f})")

    if top_coords:
        top_recess_x = (width - top_width) / 2.0
        top_recess_y = (depth - top_depth) / 2.0
        top_recess = max(top_recess_x, top_recess_y)
        top_offset_y = top_cy - cy  # 正值表示顶部向+Y偏移
        
        log_to_file(f"[STEP Exporter] Top recess={top_recess:.1f}, Y offset={top_offset_y:.1f}")
    else:
        top_recess = 10.0
        top_offset_y = 0.0
    
    # === 顶壁厚度分析 ===
    top_thickness = 1.5
    # 找顶部Z层群（top面及其下方的填充层）
    top_z_layer_verts = []
    for z_level in sorted_z_levels:
        if z_level > top_z - 2.0:
            top_z_layer_verts.extend([(v.co.x, v.co.y, v.co.z) for v in z_layers[z_level]])
    
    if top_z_layer_verts:
        z_vals = [z for x, y, z in top_z_layer_verts]
        if min(z_vals) < top_z:
            top_thickness = top_z - min(z_vals)
            if top_thickness < 0.5:
                top_thickness = 1.5
    log_to_file(f"[STEP Exporter] Top thickness: {top_thickness:.2f}")
    
    # === 壁厚分析 ===
    # 优先从自定义属性读取（由 create_filleted_top_shell 设置）
    # 自定义属性以毫米 (mm) 存储，需 ×0.001 转换为米用于内部分析
    custom_wt = obj.get('wall_thickness', 0.0)
    if custom_wt > 0:
        wall_thickness = custom_wt * 0.001  # mm → m
        log_to_file(f"[STEP Exporter] Wall thickness from custom property: {wall_thickness:.2f}m")
    else:
        # 壁厚 = 外轮廓边界框 - 内轮廓边界框，避开台阶环和圆角顶点
        # 找底部区域上方第一个不含台阶环的Z层（顶点数80-150，非最大Z层）
        bottom_region_zls = [z for z in sorted_z_levels if z <= bottom_z + 3.0]
        wall_thickness = 2.0
        if len(bottom_region_zls) >= 2:
            # 找台阶环顶Z层（底部区域顶点数最多的Z层，通常是台阶环和外壁共用的底部）
            max_z = bottom_region_zls[0]
            max_n = len(z_layers[max_z])
            for z in bottom_region_zls[1:]:
                n = len(z_layers[z])
                if n > max_n:
                    max_n = n
                    max_z = z
            log_to_file(f"[STEP Exporter] Wall bottom Z={max_z:.2f} ({max_n}v), min Z={bottom_z:.2f}")

            # 在台阶环顶Z层上方 0.3mm 以上找一个顶点数合理的Z层（内轮廓顶点）
            inner_z = None
            for z in sorted(bottom_region_zls):
                if z > max_z + 0.3 and 60 <= len(z_layers[z]) <= 150:
                    inner_z = z
                    break

            if inner_z is not None:
                inner_coords = [(v.co.x, v.co.y) for v in z_layers[inner_z]]
                inner_xs = [x for x, y in inner_coords]
                inner_ys = [y for x, y in inner_coords]
                inner_w = max(inner_xs) - min(inner_xs)
                inner_d = max(inner_ys) - min(inner_ys)
                wall_w = (width - inner_w) / 2.0
                wall_d = (depth - inner_d) / 2.0
                wall_thickness = (wall_w + wall_d) / 2.0
                log_to_file(f"[STEP Exporter] Wall thickness: {wall_thickness:.2f}mm (inner contour at z={inner_z:.2f}: {inner_w:.1f}x{inner_d:.1f}, {len(z_layers[inner_z])}v)")
            else:
                log_to_file(f"[STEP Exporter] Wall thickness: {wall_thickness:.2f}mm (default, no suitable inner Z layer)")
                for z in sorted(bottom_region_zls):
                    log_to_file(f"[STEP Exporter]   z={z:.2f} n={len(z_layers[z])} v")
        else:
            log_to_file(f"[STEP Exporter] Wall thickness: {wall_thickness:.2f} (default, insufficient Z levels)")
    wall_thickness = max(1.0, min(10.0, wall_thickness))

    # === 台阶环检测 ===
    # 优先从自定义属性读取（由 create_filleted_top_shell 设置）
    # 自定义属性以毫米 (mm) 存储，需 ×0.001 转换为米用于内部分析
    step_ring_height = 0.0
    step_ring_width = 0.0
    custom_ring_h = obj.get('step_ring_height', 0.0)
    custom_ring_w = obj.get('step_ring_width', 0.0)
    if custom_ring_h > 0 and custom_ring_w > 0:
        step_ring_height = custom_ring_h * 0.001  # mm → m
        step_ring_width = custom_ring_w * 0.001   # mm → m
        log_to_file(f"[STEP Exporter] Step ring from custom property: height={step_ring_height:.2f}m, width={step_ring_width:.2f}m")
    elif len(bottom_region_zls) >= 2:
        # 角度扇区分析，P40-P90百份位避开圆角顶点
        z0 = bottom_region_zls[0]
        z1 = None
        for z in sorted(bottom_region_zls)[1:]:
            if z - z0 >= 0.3 and len(z_layers[z]) >= 40:
                z1 = z
                break

        if z1 is not None and len(z_layers[z0]) >= 80:
            z0_coords = [(v.co.x, v.co.y) for v in z_layers[z0]]
            num_sectors = 64
            sector_angle_step = 2.0 * math.pi / num_sectors
            sector_dists = [[] for _ in range(num_sectors)]

            for x, y in z0_coords:
                dx = x - cx
                dy = y - cy
                dist = math.sqrt(dx * dx + dy * dy)
                angle = math.atan2(dy, dx)
                if angle < 0:
                    angle += 2.0 * math.pi
                sector_idx = int(angle / sector_angle_step) % num_sectors
                sector_dists[sector_idx].append(dist)

            sector_gaps = []
            for s_dists in sector_dists:
                if len(s_dists) < 3:
                    continue
                s_dists.sort()
                n_s = len(s_dists)
                # P40: 跳过圆角顶点，取台阶环内轮廓位置
                inner_idx = max(0, int(n_s * 0.40))
                # P90: 取外轮廓位置
                outer_idx = min(n_s - 1, int(n_s * 0.90))
                if inner_idx >= outer_idx:
                    continue
                inner_val = s_dists[inner_idx]
                outer_val = s_dists[outer_idx]
                if outer_val > inner_val + 0.2:
                    sector_gaps.append(outer_val - inner_val)

            if len(sector_gaps) >= num_sectors // 4:
                sector_gaps.sort()
                trim_n = max(1, len(sector_gaps) // 4)
                if len(sector_gaps) > trim_n * 2:
                    trimmed = sector_gaps[trim_n:-trim_n]
                else:
                    trimmed = sector_gaps
                avg_gap = sum(trimmed) / len(trimmed)

                log_to_file(f"[STEP Exporter] Step ring check z0={z0:.2f} n={len(z_layers[z0])} sectors={len(sector_gaps)} avg_gap={avg_gap:.2f} wall_thickness={wall_thickness:.2f}")

                if 0.3 <= avg_gap <= wall_thickness * 0.8:
                    step_ring_width = round(avg_gap, 1)
                    step_ring_height = round(z1 - z0, 1)
                    log_to_file(f"[STEP Exporter] Step ring detected: height={step_ring_height:.1f}mm, width={step_ring_width:.1f}mm (angular-sector P40-P90 gap={avg_gap:.1f})")

    log_to_file(f"[STEP Exporter] Step ring: height={step_ring_height:.1f}mm, width={step_ring_width:.1f}mm")
    
    # === 角圆角分析 ===
    # 用底部顶点包围盒
    corner_radius = 0.0
    corner_verts = [(x, y) for x, y, z in bottom_coords
                    if abs(x - cx) > half_w * 0.6 and abs(y - cy) > half_d * 0.6]
    if corner_verts:
        radii = []
        for vx, vy in corner_verts:
            dx = half_w - abs(vx - cx)
            dy = half_d - abs(vy - cy)
            if dx > 0 and dy > 0:
                r = dx + dy + math.sqrt(2 * dx * dy)
                radii.append(r)
        if radii:
            radii.sort()
            corner_radius = radii[len(radii) // 2]
    if corner_radius < 1.0:
        corner_radius = min(width, depth) * 0.1
    log_to_file(f"[STEP Exporter] Corner radius: {corner_radius:.2f}")
    
    # === 圆角半径分析 ===
    # 底部圆角：找底部Z层群，测Z差值
    outer_fillet_radius = 0.0
    bottom_z_layer_verts = []
    for z_level in sorted_z_levels:
        if z_level < bottom_z + 3.0:
            bottom_z_layer_verts.extend([(v.co.x, v.co.y, v.co.z) for v in z_layers[z_level]])
    
    if bottom_z_layer_verts:
        bottom_z_vals = [z for x, y, z in bottom_z_layer_verts]
        if max(bottom_z_vals) > bottom_z + 0.5:
            outer_fillet_radius = max(bottom_z_vals) - bottom_z
    outer_fillet_radius = max(0.0, min(outer_fillet_radius, outer_height * 0.2))
    inner_fillet_radius = max(0.1, min(outer_fillet_radius * 0.6, 3.0))  # 内圆角基于外圆角估算
    
    # === 顶部窗口检测 ===
    window_len = 0.0
    window_wid = 0.0
    window_data = obj.get('window_data', '')
    if window_data:
        log_to_file(f"[STEP Exporter] Window data from custom property: {window_data}")
    # === 读取通孔圆倒角半径（可在Blender中修改） ===
    hole_fillet_radius = obj.get('hole_fillet_radius', 0.0)
    if hole_fillet_radius > 0.0 and window_data:
        # 将 fillet_radius 注入到 window_data 的圆孔条目中
        entries = window_data.split(';')
        modified = False
        for i, entry in enumerate(entries):
            parts = entry.split(',')
            # 圆孔格式: cx,cy,cz,radius,1 或 cx,cy,cz,radius,1,fillet_radius
            if len(parts) >= 5 and parts[4].strip() == '1':
                if len(parts) == 5:
                    # 没有 fillet_radius，追加
                    entries[i] = entry + f",{hole_fillet_radius:.3f}"
                    modified = True
                elif len(parts) == 6:
                    # 已有 fillet_radius，更新
                    entries[i] = ','.join(parts[:5]) + f",{hole_fillet_radius:.3f}"
                    modified = True
        if modified:
            window_data = ';'.join(entries)
            log_to_file(f"[STEP Exporter]   Updated hole fillet radius: {hole_fillet_radius:.3f}")
    if not window_data and top_coords and len(top_coords) > 30:
        top_z_layer_coords = [(v.co.x, v.co.y) for v in top_verts]
        top_dists = [math.sqrt((x - cx)**2 + (y - cy)**2) for x, y in top_z_layer_coords]
        if top_dists:
            max_top_dist = max(top_dists)
            inner_top = [(x, y) for (x, y), d in zip(top_z_layer_coords, top_dists) if d < max_top_dist * 0.7]
            if len(inner_top) >= 4:
                wx_vals = [x for x, y in inner_top]
                wy_vals = [y for x, y in inner_top]
                window_len = max(wx_vals) - min(wx_vals)
                window_wid = max(wy_vals) - min(wy_vals)
                log_to_file(f"[STEP Exporter] Window detected: {window_len:.1f}x{window_wid:.1f}")
    
    # 释放BMesh
    bm.free()
    
    log_to_file(f"[STEP Exporter] Detected TOP shell: {width:.4f}x{depth:.4f} h={outer_height:.4f} tt={top_thickness:.1f} wt={wall_thickness:.1f} cr={corner_radius:.1f} recess={top_recess:.1f} yOff={top_offset_y:.1f} ofr={outer_fillet_radius:.1f} ifr={inner_fillet_radius:.1f} win={window_len:.1f}x{window_wid:.1f} step_ring={step_ring_height:.1f}x{step_ring_width:.1f}")
    
    # 应用单位缩放：所有尺寸参数 × scale (mm=1000, m=1)
    S = scale if scale > 0 else 1.0
    
    # 缩放 window_data 中矩形窗口条目:
    #   4值: cx,cy,wlen,wwid → 全部缩放到mm (默认box)
    #   5-6值, type=0或3: cx,cy,wlen,wwid,type[,angle] → 前4值缩放
    #   5-6值, type=1: cx,cy,cz,radius,1[,fillet] → 圆形孔, 已经是mm
    #   7-8值, type=2: cx,cy,cz,w,h,2,cr[,fillet] → 圆角矩形孔, 已经是mm
    if window_data:
        scaled_entries = []
        for entry in window_data.split(';'):
            parts = entry.split(',')
            n = len(parts)
            if n >= 7:
                # Rounded-rect hole: type=2 at index 5, already mm
                scaled_entries.append(entry)
            elif n == 5 or n == 6:
                if parts[4] == '1':
                    # Circular hole: cx,cy,cz,radius,1[,fillet], already mm
                    scaled_entries.append(entry)
                else:
                    # Window: cx,cy,wlen,wwid,type[,angle], scale first 4
                    scaled = [str(float(parts[i]) * S) for i in range(4)]
                    scaled.extend(parts[4:])
                    scaled_entries.append(','.join(scaled))
            elif n == 4:
                # Window: cx,cy,wlen,wwid, scale all
                scaled = [str(float(p) * S) for p in parts]
                scaled_entries.append(','.join(scaled))
        window_data = ';'.join(scaled_entries)
        log_to_file(f"[STEP Exporter]   window_data scaled: {window_data[:200]}...")

    return {
        'obj': obj,
        'width': width * S,
        'depth': depth * S,
        'outer_height': outer_height * S,
        'top_thickness': top_thickness * S,
        'wall_thickness': wall_thickness * S,
        'corner_radius': corner_radius * S,
        'outer_fillet_radius': outer_fillet_radius * S,
        'inner_fillet_radius': inner_fillet_radius * S,
        'top_recess': top_recess * S,
        'top_offset_y': top_offset_y * S,
        'window_len': window_len * S,
        'window_wid': window_wid * S,
        'window_data': window_data,
        'step_ring_height': step_ring_height * S,
        'step_ring_width': step_ring_width * S,
        'pos_x': obj.location.x * S,
        'pos_y': obj.location.y * S,
        'pos_z': obj.location.z * S,
    }

