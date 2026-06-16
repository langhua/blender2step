"""Cylinder and shell shape analysis for STEP Exporter."""
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
            if circularity < 0.05:
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
    custom_wt = obj.get('wall_thickness', 0.0)
    if custom_wt > 0:
        wall_thickness = custom_wt
        log_to_file(f"[STEP Exporter] Wall thickness from custom property: {wall_thickness:.2f}mm")
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
    step_ring_height = 0.0
    step_ring_width = 0.0
    custom_ring_h = obj.get('step_ring_height', 0.0)
    custom_ring_w = obj.get('step_ring_width', 0.0)
    if custom_ring_h > 0 and custom_ring_w > 0:
        step_ring_height = custom_ring_h
        step_ring_width = custom_ring_w
        log_to_file(f"[STEP Exporter] Step ring from custom property: height={step_ring_height:.1f}mm, width={step_ring_width:.1f}mm")
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
    
    return {
        'obj': obj,
        'width': width,
        'depth': depth,
        'outer_height': outer_height,
        'top_thickness': top_thickness,
        'wall_thickness': wall_thickness,
        'corner_radius': corner_radius,
        'outer_fillet_radius': outer_fillet_radius,
        'inner_fillet_radius': inner_fillet_radius,
        'top_recess': top_recess,
        'top_offset_y': top_offset_y,
        'window_len': window_len,
        'window_wid': window_wid,
        'window_data': window_data,
        'step_ring_height': step_ring_height,
        'step_ring_width': step_ring_width,
        'pos_x': obj.location.x,
        'pos_y': obj.location.y,
        'pos_z': obj.location.z,
    }

def _analyze_bottom_shell_from_mesh(obj, context, scale):
    """
    从 mesh 分析识别是否为底壳类型，并测量所有参数
    
    返回:
        dict: 包含底壳参数的字典，如果不是底壳则返回 None
    """
    if obj.type != 'MESH':
        return None
    
    import bmesh
    from collections import defaultdict
    
    log_to_file(f"[STEP Exporter] Analyzing mesh for bottom shell: {obj.name}")
    
    depsgraph = context.evaluated_depsgraph_get()
    eval_obj = obj.evaluated_get(depsgraph)
    mesh_data = eval_obj.data
    
    bm = bmesh.new()
    bm.from_mesh(mesh_data)
    bm.verts.ensure_lookup_table()
    
    vertices = bm.verts
    if len(vertices) < 100:
        log_to_file(f"[STEP Exporter] Too few vertices ({len(vertices)}), not a bottom shell")
        bm.free()
        return None
    
    z_layers = defaultdict(list)
    for v in vertices:
        z_key = round(v.co.z / 0.01) * 0.01
        z_layers[z_key].append(v)
    
    sorted_z_levels = sorted(z_layers.keys())
    
    if len(sorted_z_levels) < 2:
        log_to_file(f"[STEP Exporter] Not enough z-levels ({len(sorted_z_levels)}), not a bottom shell")
        bm.free()
        return None
    
    min_z = sorted_z_levels[0]
    max_z = sorted_z_levels[-1]
    total_height = max_z - min_z
    
    log_to_file(f"[STEP Exporter] z=[{min_z:.3f}, {max_z:.3f}], height={total_height:.3f}, levels={len(sorted_z_levels)}")
    
    bottom_z = sorted_z_levels[0]
    bottom_verts = z_layers[bottom_z]
    top_z = sorted_z_levels[-1]
    top_verts = z_layers[top_z]
    
    if len(bottom_verts) < 50 or len(top_verts) < 50:
        log_to_file(f"[STEP Exporter] No clear bottom/top planes, not a bottom shell")
        bm.free()
        return None
    
    # 区分顶壳/底壳：顶壳的封闭面在 max-Z（顶点少），开口在 min-Z（内外壁顶点多）
    # 底壳的封闭面在 min-Z，开口在 max-Z
    top_vcount = len(top_verts)
    bot_vcount = len(bottom_verts)
    vratio = top_vcount / max(bot_vcount, 1)
    log_to_file(f"[STEP Exporter] Vertex count: top={top_vcount}, bottom={bot_vcount}, ratio={vratio:.3f}")
    
    # 关键判断：如果底部顶点显著多于顶部（ratio < 0.7），说明开口在底部 → 顶壳
    if vratio < 0.70:
        log_to_file(f"[STEP Exporter] Bottom has significantly more vertices (ratio={vratio:.3f}) → TOP shell (opening at bottom), not bottom shell")
        bm.free()
        return None
    
    # 几何检查：顶壳锥形渐缩，顶面bbox显著小于底面bbox
    top_x_coords = [v.co.x for v in top_verts]
    top_y_coords = [v.co.y for v in top_verts]
    bottom_x_coords = [v.co.x for v in bottom_verts]
    bottom_y_coords = [v.co.y for v in bottom_verts]
    top_w = max(top_x_coords) - min(top_x_coords)
    top_d = max(top_y_coords) - min(top_y_coords)
    bot_w = max(bottom_x_coords) - min(bottom_x_coords)
    bot_d = max(bottom_y_coords) - min(bottom_y_coords)
    area_ratio = (top_w * top_d) / max(bot_w * bot_d, 0.01)
    log_to_file(f"[STEP Exporter] Top bbox: {top_w:.1f}x{top_d:.1f}, Bottom bbox: {bot_w:.1f}x{bot_d:.1f}, area_ratio={area_ratio:.3f}")
    
    if area_ratio < 0.80:
        log_to_file(f"[STEP Exporter] Top face area is {area_ratio:.3f}x bottom → TOP shell (tapered), not bottom shell")
        bm.free()
        return None
    
    total_levels = len(sorted_z_levels)
    
    # 从底部顶点计算物体中心和尺寸
    bottom_x_coords = [v.co.x for v in bottom_verts]
    bottom_y_coords = [v.co.y for v in bottom_verts]
    obj_center_x = (max(bottom_x_coords) + min(bottom_x_coords)) / 2.0
    obj_center_y = (max(bottom_y_coords) + min(bottom_y_coords)) / 2.0
    width = max(bottom_x_coords) - min(bottom_x_coords)
    depth = max(bottom_y_coords) - min(bottom_y_coords)
    half_w = width / 2.0
    half_d = depth / 2.0
    log_to_file(f"[STEP Exporter] Shell center=({obj_center_x:.1f},{obj_center_y:.1f}), size={width:.1f}x{depth:.1f}")
    
    # 找到外层垂直壁开始的位置（外圆角结束处）
    outer_wall_start_z = None
    for i in range(1, len(sorted_z_levels)):
        gap = sorted_z_levels[i] - sorted_z_levels[i-1]
        levels_after = total_levels - i
        if levels_after < total_levels * 0.25 and gap > 0.1:
            outer_wall_start_z = sorted_z_levels[i-1]
            break
    
    if outer_wall_start_z is None:
        outer_wall_start_z = sorted_z_levels[-2] if len(sorted_z_levels) > 1 else sorted_z_levels[-1]
    
    outer_fillet_radius = outer_wall_start_z - bottom_z
    log_to_file(f"[STEP Exporter] outer_wall_start_z={outer_wall_start_z:.2f}, outer_fillet={outer_fillet_radius:.2f}")
    
    # ===== 提取外壁顶点坐标用于后续分析（然后释放 bmesh）=====
    try:
        outer_wall_verts_coords = [(v.co.x, v.co.y, v.co.z) for v in z_layers.get(outer_wall_start_z, bottom_verts)]
        log_to_file(f"[STEP Exporter] outer_wall_verts at z={outer_wall_start_z:.2f}: {len(outer_wall_verts_coords)} vertices")
    except Exception as e:
        log_to_file(f"[STEP Exporter] ERROR extracting outer wall coords: {e}")
        return None
    
    # ===== 找到具有最大外轮廓的z层用于角点检测 =====
    # 在底壳模型中，底部因圆角（fillet）而收缩，真正的全尺寸外轮廓在更高的z层
    # 扫描所有z层，找到顶点到中心距离最大的层（即外轮廓最完整的层）
    corner_detect_verts_coords = None
    corner_detect_z = None
    max_outer_dist_overall = 0.0
    for z_level in sorted_z_levels:
        verts_at_z = z_layers.get(z_level, [])
        if len(verts_at_z) < 20:
            continue
        coords = [(v.co.x, v.co.y, v.co.z) for v in verts_at_z]
        dists = [math.sqrt((x - obj_center_x)**2 + (y - obj_center_y)**2) for x, y, z in coords]
        if dists:
            max_d_at_z = max(dists)
            if max_d_at_z > max_outer_dist_overall:
                max_outer_dist_overall = max_d_at_z
                corner_detect_verts_coords = coords
                corner_detect_z = z_level
    if corner_detect_verts_coords is None:
        corner_detect_verts_coords = [(v.co.x, v.co.y, v.co.z) for v in bottom_verts]
        corner_detect_z = bottom_z
    log_to_file(f"[STEP Exporter] Corner detect z-level: z={corner_detect_z:.2f}, max_outer_dist={max_outer_dist_overall:.1f}, verts={len(corner_detect_verts_coords)}")
    
    # ===== 从最大外轮廓顶点重新计算宽度和深度 =====
    # half_w/half_d 应从全尺寸外轮廓计算，而非收缩的底部
    max_contour_x = max(x for x, y, z in corner_detect_verts_coords)
    min_contour_x = min(x for x, y, z in corner_detect_verts_coords)
    max_contour_y = max(y for x, y, z in corner_detect_verts_coords)
    min_contour_y = min(y for x, y, z in corner_detect_verts_coords)
    full_width = max_contour_x - min_contour_x
    full_depth = max_contour_y - min_contour_y
    half_w_corner = full_width / 2.0
    half_d_corner = full_depth / 2.0
    log_to_file(f"[STEP Exporter] Contour dimensions from full profile: {full_width:.1f}x{full_depth:.1f} (vs bottom: {width:.1f}x{depth:.1f})")
    
    # 用全尺寸更新 width/depth（后续传递给C++）
    width = full_width
    depth = full_depth
    half_w = half_w_corner
    half_d = half_d_corner
    
    # 中间层顶点用于壁厚检测
    mid_z_target = bottom_z + total_height * 0.5
    mid_z = min(sorted_z_levels, key=lambda z: abs(z - mid_z_target))
    mid_verts_coords = [(v.co.x, v.co.y, v.co.z) for v in z_layers.get(mid_z, [])]
    
    # ===== Z层分析找内腔底部 =====
    # 在底部z层和外部壁起始z层之间，找顶点数最多的z层作为内腔底面
    inner_bottom_z = None
    bottom_thickness = 2.0
    
    search_upper_z = outer_wall_start_z if outer_wall_start_z else max_z
    
    max_inner_vert_count = 0
    for z_level in sorted_z_levels:
        if z_level > bottom_z + 0.3 and z_level < search_upper_z - 0.3:
            count = len(z_layers[z_level])
            if count > max_inner_vert_count and count >= 20:
                max_inner_vert_count = count
                inner_bottom_z = z_level
    
    if inner_bottom_z is not None:
        bottom_thickness = inner_bottom_z - bottom_z
        log_to_file(f"[STEP Exporter] Inner bottom via Z-layer: z={inner_bottom_z:.2f}, bottom_thickness={bottom_thickness:.2f}, verts={max_inner_vert_count}")
    else:
        # Z层分析失败（布尔运算后的2层网格），使用默认底部厚度
        log_to_file(f"[STEP Exporter] Inner bottom not found via Z-layer (levels={len(sorted_z_levels)}), using default bottom_thickness={bottom_thickness:.1f}")
        inner_bottom_z = bottom_z + bottom_thickness
    
    # 保存底部顶点数，用于后续孔检测
    bottom_vert_count_before_free = len(bottom_verts)
    bottom_vert_coords = [(v.co.x, v.co.y, v.co.z) for v in bottom_verts]
    
    # ===== 圆形检测：如果底部外轮廓是圆形，说明是圆柱/空心圆柱，不是底壳 =====
    # 底壳底部是圆角矩形（拐角处半径小，边长处半径大），std/mean 较大
    # 圆柱/空心圆柱底部是正圆，外轮廓所有顶点到中心距离相同，std/mean 很小
    bottom_all_dists = [math.sqrt((x - obj_center_x)**2 + (y - obj_center_y)**2) 
                        for x, y, z in bottom_vert_coords]
    if bottom_all_dists:
        max_bd = max(bottom_all_dists)
        # 仅保留外圈顶点（最外层 15%），排除内孔顶点
        outer_bottom_dists = [d for d in bottom_all_dists if d > max_bd * 0.85]
        if len(outer_bottom_dists) >= 8:
            mean_obd = sum(outer_bottom_dists) / len(outer_bottom_dists)
            std_obd = math.sqrt(sum((d - mean_obd)**2 for d in outer_bottom_dists) / len(outer_bottom_dists))
            circularity = std_obd / mean_obd if mean_obd > 0 else 1.0
            log_to_file(f"[STEP Exporter] Bottom circularity check: circ={circularity:.4f} (n_outer={len(outer_bottom_dists)})")
            if circularity < 0.02:
                log_to_file(f"[STEP Exporter] Bottom outer contour is circular, not a bottom shell -> skipping to cylinder detection")
                bm.free()
                return None
    
    # 释放 BMesh（所有 z_layers 中的 BMVert 引用现在无效）
    bm.free()
    
    # outer_height = 使用实际网格Z向高度 (top_z, bottom_z 已在前面定义)
    outer_height = max(top_z - bottom_z, 8.0)
    
    if outer_fillet_radius > outer_height * 0.5:
        outer_fillet_radius = 0.0
    
    # 内圆角基于外圆角估算（底壳内外圆角比例约1:2）
    # 另可从 Z-layer gap 检测内壁起始位置推算（见 create_bottom_shell.py 的 measure 逻辑）
    inner_fillet_radius = max(0.1, min(outer_fillet_radius * 0.5, 3.0))
    
    # ===== 角圆角检测（用最大外轮廓层的坐标）=====
    corner_radius = 0.0
    
    # 过滤到仅最外层轮廓顶点（排除内轮廓和填充顶点）
    outer_dists = [math.sqrt((x - obj_center_x)**2 + (y - obj_center_y)**2) 
                   for x, y, z in corner_detect_verts_coords]
    if outer_dists:
        max_d = max(outer_dists)
        # 仅保留距离中心最远的顶点（外轮廓），排除内侧墙壁顶点
        outer_contour_only = [(x, y) for (x, y, z), d in zip(corner_detect_verts_coords, outer_dists) 
                             if d > max_d * 0.85]
        log_to_file(f"[STEP Exporter] Outer contour filter: {len(outer_contour_only)}/{len(corner_detect_verts_coords)} vertices (max_d={max_d:.1f})")
    else:
        outer_contour_only = [(x, y) for x, y, z in corner_detect_verts_coords]
    
    corner_verts = [(x, y) for x, y in outer_contour_only 
                    if abs(x - obj_center_x) > half_w * 0.6 
                    and abs(y - obj_center_y) > half_d * 0.6]
    log_to_file(f"[STEP Exporter] corner_verts filter: hw={half_w:.1f} hd={half_d:.1f} found={len(corner_verts)} from {len(outer_contour_only)}")
    if corner_verts:
        radii = []
        for cx, cy in corner_verts:
            dx = half_w - abs(cx - obj_center_x)
            dy = half_d - abs(cy - obj_center_y)
            if dx > 0 and dy > 0:
                # 圆角半径精确公式：对于圆角矩形角弧上的点，
                # R = dx + dy + sqrt(2*dx*dy)
                r = dx + dy + math.sqrt(2 * dx * dy)
                radii.append(r)
        if radii:
            radii.sort()
            log_to_file(f"[STEP Exporter] Raw corner radii: min={radii[0]:.2f} max={radii[-1]:.2f} median={radii[len(radii)//2]:.2f}")
            # 使用中位数代替75%分位数，外轮廓顶点产生的值应一致
            corner_radius = radii[len(radii) // 2]
            log_to_file(f"[STEP Exporter] Corner radius computed from {len(radii)} verts (median): {corner_radius:.2f}")
    if corner_radius < 1.0:
        corner_radius = min(width, depth) * 0.2
        log_to_file(f"[STEP Exporter] Corner radius fallback: {corner_radius:.2f}")
    
    # ===== 圆形截面检查 =====
    outer_dists = [math.sqrt((x - obj_center_x)**2 + (y - obj_center_y)**2) for x, y, z in corner_detect_verts_coords]
    if outer_dists:
        min_d, max_d = min(outer_dists), max(outer_dists)
        if max_d > 0 and min_d / max_d > 0.85:
            log_to_file(f"[STEP Exporter] Cross-section too circular, not a bottom shell")
            return None
    
    # ===== 壁厚检测 =====
    wall_thickness = 2.0
    if mid_verts_coords:
        flat_x_outer_vals = [abs(x - obj_center_x) for x, y, z in mid_verts_coords 
                            if abs(y - obj_center_y) < depth * 0.15]
        flat_x_inner_vals = [abs(x - obj_center_x) for x, y, z in mid_verts_coords 
                            if abs(y - obj_center_y) < depth * 0.15 
                            and abs(x - obj_center_x) < half_w * 0.98]
        flat_y_outer_vals = [abs(y - obj_center_y) for x, y, z in mid_verts_coords 
                            if abs(x - obj_center_x) < width * 0.15]
        flat_y_inner_vals = [abs(y - obj_center_y) for x, y, z in mid_verts_coords 
                            if abs(x - obj_center_x) < width * 0.15 
                            and abs(y - obj_center_y) < half_d * 0.98]
        
        fxo = max(flat_x_outer_vals) if flat_x_outer_vals else 0
        fxi = max(flat_x_inner_vals) if flat_x_inner_vals else 0
        fyo = max(flat_y_outer_vals) if flat_y_outer_vals else 0
        fyi = max(flat_y_inner_vals) if flat_y_inner_vals else 0
        
        if fxi > 0 and fyi > 0:
            wall_thickness = ((fxo - fxi) + (fyo - fyi)) / 2
    
    if wall_thickness < 0.5:
        wall_thickness = 2.0
    
    log_to_file(f"[STEP Exporter] Detected bottom shell: {width:.1f}x{depth:.1f} h={outer_height:.1f} bt={bottom_thickness:.1f} wt={wall_thickness:.1f} cr={corner_radius:.1f} ofr={outer_fillet_radius:.1f} ifr={inner_fillet_radius:.1f}")
    
    # ===== 检测螺丝孔：用底层顶点数判断 =====
    # 带孔的底壳在底部z层有大量额外顶点（孔边界三角化产生），无孔底壳底部顶点较少
    has_holes = False
    hole_radius_detected = 1.5
    hole_offset_x = 25.0
    hole_offset_y = 20.0
    
    bottom_vert_count = bottom_vert_count_before_free
    
    # 无孔底壳约257顶点，带孔约636顶点。用阈值300区分
    if bottom_vert_count > 400:
        has_holes = True
        log_to_file(f"[STEP Exporter] Has holes detected (bottom_verts={bottom_vert_count})")
        
        # 自动检测孔位置：分析底部顶点在四个象限的聚簇分布
        ocx, ocy = obj_center_x, obj_center_y
        q_pp, q_pn, q_np, q_nn = [], [], [], []
        for bx, by, bz in bottom_vert_coords:
            dx = bx - ocx
            dy = by - ocy
            if dx > 0 and dy > 0:
                q_pp.append((dx, dy))
            elif dx > 0 and dy < 0:
                q_pn.append((dx, dy))
            elif dx < 0 and dy > 0:
                q_np.append((dx, dy))
            elif dx < 0 and dy < 0:
                q_nn.append((dx, dy))
        
        hole_cx_vals = []
        hole_cy_vals = []
        hole_radius_vals = []
        
        for q in [q_pp, q_pn, q_np, q_nn]:
            if len(q) < 10:
                continue
            # 按距离中心排序
            q_radii = sorted([(math.sqrt(x*x + y*y), x, y) for x, y in q])
            
            # ===== 方法1: 间隙检测（内外簇之间的最大间隙）=====
            best_gap = 0
            best_idx = len(q_radii) // 2
            search_start = max(1, len(q_radii) // 4)
            search_end = min(len(q_radii) - 1, 3 * len(q_radii) // 4)
            for i in range(search_start, search_end):
                gap = q_radii[i][0] - q_radii[i-1][0]
                if gap > best_gap:
                    best_gap = gap
                    best_idx = i
            
            gap_detected = best_gap > 2.0
            
            if gap_detected:
                # 间隙检测成功：内簇为孔边界顶点
                inner = [(x, y) for r, x, y in q_radii[:best_idx]]
                if inner:
                    hole_cx_vals.append(abs(sum(x for x, y in inner) / len(inner)))
                    hole_cy_vals.append(abs(sum(y for x, y in inner) / len(inner)))
                    cx_q = sum(x for x, y in inner) / len(inner)
                    cy_q = sum(y for x, y in inner) / len(inner)
                    r_q = sum(math.sqrt((x - cx_q)**2 + (y - cy_q)**2) for x, y in inner) / len(inner)
                    hole_radius_vals.append(r_q)
            else:
                # ===== 方法2: 滑动窗口密度聚类（间隙检测失败时）=====
                # 滑动窗口找空间最紧凑的簇（最小位置方差），而非最短半径
                # 孔边界顶点形成一个紧密的圆形簇，内部三角化点分散但半径更小
                window_size = max(4, min(len(q_radii) // 6, 12))
                best_cluster = None
                best_variance = float('inf')
                for i in range(len(q_radii) - window_size + 1):
                    window_pts = [(x, y) for r, x, y in q_radii[i:i+window_size]]
                    cx_w = sum(x for x, y in window_pts) / window_size
                    cy_w = sum(y for x, y in window_pts) / window_size
                    variance = sum((x - cx_w)**2 + (y - cy_w)**2 for x, y in window_pts) / window_size
                    if variance < best_variance:
                        best_variance = variance
                        best_cluster = window_pts
                
                if best_cluster and best_variance < 25.0:
                    hole_cx_vals.append(abs(sum(x for x, y in best_cluster) / len(best_cluster)))
                    hole_cy_vals.append(abs(sum(y for x, y in best_cluster) / len(best_cluster)))
                    log_to_file(f"[STEP Exporter] Quadrant gap detection failed (best_gap={best_gap:.2f}), density cluster found (variance={best_variance:.2f})")
                else:
                    log_to_file(f"[STEP Exporter] Quadrant gap/cluster detection both failed (best_gap={best_gap:.2f}, best_variance={best_variance:.2f})")
        
        if hole_cx_vals and hole_cy_vals:
            hole_cx = sum(hole_cx_vals) / len(hole_cx_vals)
            hole_cy = sum(hole_cy_vals) / len(hole_cy_vals)
            hole_offset_x = half_w - hole_cx
            hole_offset_y = half_d - hole_cy
            if hole_radius_vals:
                hole_radius_detected = sum(hole_radius_vals) / len(hole_radius_vals)
            log_to_file(f"[STEP Exporter] Auto-detected hole positions: cx={hole_cx:.1f}, cy={hole_cy:.1f}, r={hole_radius_detected:.2f}, offset=({hole_offset_x:.1f},{hole_offset_y:.1f})")
            
            # ===== 检测结果质量验证：簇半径过大说明检测到了错误的内簇 =====
            # 孔半径通常 ≤ 4.0mm，如果检测到的簇半径 > 6.0，则间隙检测可能包含了桥接顶点
            if hole_radius_detected > 6.0:
                log_to_file(f"[STEP Exporter] WARNING: Detected cluster radius ({hole_radius_detected:.2f}) too large, detection likely wrong. Discarding.")
                hole_cx_vals = []
                hole_cy_vals = []
        
        # ===== 合理性检查：检测到的孔偏移必须在合理范围内 =====
        # hole_offset_x 应满足: 5.0 <= offset <= half_w - 5.0 (孔不能太靠边或太靠中心)
        # hole_offset_y 应满足: 5.0 <= offset <= half_d - 5.0
        fallback_offset_x = max(5.0, min(half_w * 0.5, half_w - 5.0))
        fallback_offset_y = max(5.0, min(half_d * 0.5, half_d - 5.0))
        log_to_file(f"[STEP Exporter] Fallback hole offsets: ({fallback_offset_x:.1f}, {fallback_offset_y:.1f}) based on half_w={half_w:.1f}, half_d={half_d:.1f}")
        
        if not hole_cx_vals or not hole_cy_vals:
            # 检测完全失败，使用尺寸比例回退值
            hole_offset_x = fallback_offset_x
            hole_offset_y = fallback_offset_y
            log_to_file(f"[STEP Exporter] Hole detection failed, using fallback offsets: ({hole_offset_x:.1f}, {hole_offset_y:.1f})")
        else:
            # 独立检查每个偏移量（不用 elif 链，确保两个都修正）
            x_fixed = False
            y_fixed = False
            if hole_offset_x < 5.0 or hole_offset_x > half_w - 5.0:
                hole_offset_x = fallback_offset_x
                x_fixed = True
            if hole_offset_y < 5.0 or hole_offset_y > half_d - 5.0:
                hole_offset_y = fallback_offset_y
                y_fixed = True
            if x_fixed or y_fixed:
                log_to_file(f"[STEP Exporter] Hole offset out of range corrected: x={x_fixed} y={y_fixed}, final=({hole_offset_x:.1f},{hole_offset_y:.1f})")
    else:
        log_to_file(f"[STEP Exporter] No holes detected (bottom_verts={bottom_vert_count})")
    
    params = {
        'width': width,
        'depth': depth,
        'outer_height': outer_height,
        'bottom_thickness': bottom_thickness,
        'wall_thickness': wall_thickness,
        'corner_radius': corner_radius,
        'outer_fillet_radius': outer_fillet_radius,
        'inner_fillet_radius': inner_fillet_radius,
        'step_height': 1.0,
        'pos_x': obj.location.x,
        'pos_y': obj.location.y,
        'pos_z': obj.location.z,
    }
    
    if has_holes:
        params['has_holes'] = True
        params['hole_radius'] = hole_radius_detected
        params['hole_offset_x'] = hole_offset_x
        params['hole_offset_y'] = hole_offset_y
        log_to_file(f"[STEP Exporter] Final hole params: radius={hole_radius_detected:.2f}, offset=({hole_offset_x:.1f},{hole_offset_y:.1f}), half_w={half_w:.1f}, half_d={half_d:.1f}")
    
    return params


def _analyze_cylinder_from_mesh(obj, context, scale):
    """
    从 mesh 分析识别是否为圆柱/圆锥/空心圆柱类型，并测量所有参数
    
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
    if std_b > bottom_radius * 0.15 or std_t > top_radius * 0.15:
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
    has_groove_custom = obj.get('step_groove_depth') is not None
    groove_params = {}
    if has_groove_custom:
        groove_params = {
            'groove_depth': obj['step_groove_depth'],
            'groove_bottom_width': obj.get('step_groove_bottom_width', 0),
            'groove_top_width': obj.get('step_groove_top_width', 0),
            'groove_extrusion_length': obj.get('step_groove_extrusion_length', 0),
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
    stored_hole_type = obj.get('hole_type') if hasattr(obj, 'get') else None
    stored_pos = obj.get('hole_position') if hasattr(obj, 'get') else None
    log_to_file(f"[STEP Exporter]   Stored props: hole_type={stored_hole_type}, hole_position={stored_pos}, is_tapered={obj.get('hole_is_tapered') if hasattr(obj,'get') else None}")
    if stored_hole_type == 'through' or stored_pos == 'through':
        hole_pattern_detected = True
        hole_position = 'through'
        stored_hr = obj.get('hole_radius') if hasattr(obj, 'get') else None
        hole_radius = stored_hr if stored_hr else body_radius * 0.35
        hole_depth = height
        log_to_file(f"[STEP Exporter]   Through-hole detected from stored property, r={hole_radius:.4f}")
    elif stored_pos in ('top', 'bottom', 'both'):
        hole_pattern_detected = True
        hole_position = stored_pos
        # 使用存储的孔半径和深度，避免 mesh z-level 分析误差
        stored_hr = obj.get('hole_radius') if hasattr(obj, 'get') else None
        stored_hd = obj.get('hole_depth') if hasattr(obj, 'get') else None
        hole_radius = stored_hr if stored_hr else body_radius * 0.35
        hole_depth = stored_hd if stored_hd else height * 0.5
        if stored_pos == 'both':
            hole_depth_top = hole_depth
        log_to_file(f"[STEP Exporter]   Blind hole from stored property: pos={stored_pos} r={hole_radius:.4f} d={hole_depth:.4f}")
    
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
        if stored_hr is not None and stored_pos2 in ('top', 'bottom', 'both') and stored_hr > 0.0005:
            inner_r = stored_hr
            log_to_file(f"[STEP Exporter]   Using stored hole_radius={stored_hr:.4f} from object property")
        
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
                if stored_pos3 == 'top':
                    hole_pattern_detected = True
                    hole_position = 'top'
                    hole_radius = inner_r
                    hole_depth = top_hole_d
                    log_to_file(f"[STEP Exporter]   Using stored hole_position=top, overriding dual-blind detection")
                elif stored_pos3 == 'bottom':
                    hole_pattern_detected = True
                    hole_position = 'bottom'
                    hole_radius = inner_r
                    hole_depth = bottom_hole_d
                    log_to_file(f"[STEP Exporter]   Using stored hole_position=bottom, overriding dual-blind detection")
                else:
                    hole_pattern_detected = True
                    hole_position = 'both'
                    hole_radius = inner_r
                    stored_depth = obj.get('hole_depth') if hasattr(obj, 'get') else None
                    if stored_depth is not None:
                        hole_depth = stored_depth
                        hole_depth_top = stored_depth
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
            hole_radius = inner_r
            hole_depth = bottom_hole_d
            log_to_file(f"[STEP Exporter]   Bottom blind hole: inner_r={inner_r:.4f} hole_depth={bottom_hole_d:.4f} ({bottom_hole_d/height*100:.0f}%)")
        elif top_has_hole:
            hole_pattern_detected = True
            hole_position = 'top'
            hole_radius = inner_r
            hole_depth = top_hole_d
            log_to_file(f"[STEP Exporter]   Top blind hole: inner_r={inner_r:.4f} hole_depth={top_hole_d:.4f} ({top_hole_d/height*100:.0f}%)")
        else:
            log_to_file(f"[STEP Exporter]   Blind hole check: inner_r={inner_r:.6f} btm_d={bottom_hole_d:.6f} top_d={top_hole_d:.6f} — not detected")
    
    if not cylindrical_body and bottom_radius > 0.01:
        above_zls = [zl for zl in sorted_z if zl > body_end_z and zl in z_radius_data]
        if above_zls:
            above_r_first = z_radius_data[above_zls[0]]
            if above_r_first < bottom_radius * 0.6:
                log_to_file(f"[STEP Exporter]   Hole pattern detected: bottom_r={bottom_radius:.3f} above_r={above_r_first:.3f}, treating as cylinder")
                cylindrical_body = True
                body_radius = bottom_radius
                top_radius = bottom_radius  # 防止后续检测为锥体
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
            bottom_transition_zls = [zl for zl in sorted_z if zl < sorted_z[0] and zl in z_radius_data]
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
                # r0 != r1 == r2 → 顶部倒角，r0 是完整半径（圆柱体）
                body_radius = r0
                bottom_radius = r0
                top_radius = r0  # 让后续比例检查通过，确保返回 cylinder 而非 cone
                top_feature = 'chamfer'
                top_feature_size = r0 - r2
                top_transition_zls = [valid_zls[0], valid_zls[1]]
                cylindrical_body = True
                body_end_z = valid_zls[2]
            elif ratio_01 < 0.01 and ratio_12 > 0.01:
                # r0 == r1 != r2 → 底部倒角（圆柱体）
                body_radius = r0
                bottom_radius = r0
                top_radius = r0
                bottom_feature = 'chamfer'
                bottom_feature_size = r0 - r2
                bottom_transition_zls = [valid_zls[1], valid_zls[2]]
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
    
    # 对于圆柱本体有过渡 → 修正 radius 为 body_radius
    if cylindrical_body and (top_feature or bottom_feature):
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
    if not cylindrical_body and top_feature and bottom_feature:
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
                # - Bottom inner radius significantly larger than top
                # - For 4+ levels: bottom section has significant taper
                # - For 3 levels: accept by gap between bottom and top inner
                if len(inner_z_data) >= 4:
                    is_stepped = (top_range < max(top_mean * 0.05, 0.10) and
                                  bot_range > max(top_mean * 0.08, 0.30) and
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
                    if 0.5 <= small_h <= height * 0.6:
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
    
    # 构建返回参数
    # 应用单位缩放：所有尺寸参数 × scale（mm=1000, m=1）
    S = scale if scale > 0 else 1.0
    
    # 检测到孔洞模式（顶部/底部盲孔）：返回盲孔圆柱体类型
    # 使用 OpenCASCADE 布尔减操作创建参数化盲孔
    if hole_pattern_detected:
        if hole_position == 'through':
            # 通孔：使用空心圆柱体（直孔或锥形孔）
            body_radius_for_export = max(bottom_radius, top_radius)
            hole_fillet_r = obj.get('hole_fillet_radius', 0.0) if hasattr(obj, 'get') else 0.0
            hole_is_tapered_thru = obj.get('hole_is_tapered', False) if hasattr(obj, 'get') else False
            opening_r = obj.get('hole_opening_radius', hole_radius) if hasattr(obj, 'get') else hole_radius
            end_r = obj.get('hole_end_radius', hole_radius) if hasattr(obj, 'get') else hole_radius
            
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
                return {
                    'obj_type': 'hollow_cylinder_tapered',
                    'outer_radius': body_radius_for_export * S,
                    'inner_radius_top': opening_r * S,
                    'inner_radius_bottom': end_r * S,
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
            has_outer_feature = (stored_chamfer_type in ('chamfer','fillet','chamfer_both','chamfer_fillet','fillet_both'))
            obj_type_out = 'hollow_cylinder_tapered' if has_outer_feature else 'hollow_cylinder'
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
            if hole_fillet_r > 0 and not has_outer_feature:
                result['top_feature'] = 'fillet'
                result['top_feature_size'] = hole_fillet_r
                result['bottom_feature'] = 'fillet'
                result['bottom_feature_size'] = hole_fillet_r
                result['obj_type'] = 'hollow_cylinder_tapered'
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
            if hole_r_opening_stored > 0:
                hole_radius = hole_r_opening_stored
            hole_r_bottom = hole_r_end_stored
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
        elif stored_ctype == 'chamfer_both':
            top_ch = stored_csz * 0.001; btm_ch = stored_csz * 0.001
        elif stored_ctype == 'fillet_both':
            top_fr = stored_fr * 0.001; btm_fr = stored_fr * 0.001
        elif stored_ctype == 'chamfer_fillet':
            top_ch = stored_csz * 0.001; btm_fr = stored_fr * 0.001
        if stored_orig_r > 0:
            body_radius_for_export = stored_orig_r * 0.001  # use original radius
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
        for k in ('groove_depth', 'groove_bottom_width', 'groove_top_width', 'groove_extrusion_length'):
            if k in groove_params: groove_params[k] *= S
    if stepped_hole_params:
        for k in ('small_hole_radius', 'small_hole_height', 'inner_bottom_radius', 'inner_top_radius'):
            if k in stepped_hole_params: stepped_hole_params[k] *= S
    
    if is_hollow:
        if bottom_radius * 0.98 <= top_radius <= bottom_radius * 1.02:
            # 检查锥形通孔
            hole_is_tapered_thru = obj.get('hole_is_tapered', False) if hasattr(obj, 'get') else False
            inner_end_r = obj.get('hole_end_radius', inner_radius) if hasattr(obj, 'get') else inner_radius
            inner_opening_r = obj.get('hole_opening_radius', inner_radius) if hasattr(obj, 'get') else inner_radius
            
            if hole_is_tapered_thru and abs(inner_opening_r - inner_end_r) > 0.0001:
                obj_type = 'hollow_cylinder_tapered'
                fillet_r = obj.get('hole_fillet_radius', 0.0) if hasattr(obj, 'get') else 0.0
                log_to_file(f"[STEP Exporter]   Tapered through-hole: opening_r={inner_opening_r:.3f} end_r={inner_end_r:.3f}")
                return {
                    'obj_type': obj_type,
                    'outer_radius': max(bottom_radius, top_radius),
                    'inner_radius_top': inner_opening_r,
                    'inner_radius_bottom': inner_end_r,
                    'height': height,
                    'hole_fillet_radius': fillet_r,
                    'pos_x': pos_x,
                    'pos_y': pos_y,
                    'pos_z': pos_z,
                }
            
            obj_type = 'hollow_cylinder'
            if top_feature == 'fillet':
                obj_type = 'hollow_cylinder_fillet'
            return {
                'obj_type': obj_type,
                'outer_radius': max(bottom_radius, top_radius),
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
        if bottom_radius * 0.98 <= top_radius <= bottom_radius * 1.02:
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


