"""Bottom shell shape analysis.

=== 单位约定 (Unit Convention) ===
内部计算: 米 (Blender 原生单位)
分析结果 (返回 dict): 毫米 (mm) — ×S (S=1000)
C++ 导出函数: 毫米 (mm)
STEP 文件输出: 毫米 (mm)
"""
import sys, math
import bmesh
from mathutils import Vector
from ..core.utils import log_to_file
from ..core import _globals as _g

def _analyze_bottom_shell_from_mesh(obj, context, scale):
    """
    从 mesh 分析识别是否为底壳类型，并测量所有参数
    
    返回:
        dict: 包含底壳参数的字典，如果不是底壳则返回 None
    """
    if obj.type != 'MESH':
        return None
    
    # Quick path: read from custom properties if explicitly tagged
    if obj.get('object_type') == 'bottom_shell' and obj.get('_params_from_props'):
        w = obj.get('width', 100.0); d = obj.get('depth', 80.0)
        oh = obj.get('outer_height', 30.0); bt = obj.get('bottom_thickness', 2.0)
        wt = obj.get('wall_thickness', 2.0); cr = obj.get('corner_radius', 5.0)
        ofr = obj.get('outer_fillet_radius', 10.0); ifr = obj.get('inner_fillet_radius', 8.0)
        sh = obj.get('step_height', 1.0)
        has_holes = obj.get('has_holes', False)
        hr = obj.get('hole_radius', 3.0); hox = obj.get('hole_offset_x', 15.0)
        hoy = obj.get('hole_offset_y', 15.0)
        log_to_file(f"[STEP Exporter] Bottom shell from props: {w:.0f}x{d:.0f}x{oh:.0f}mm"
                    f" wall={wt:.1f} cr={cr:.1f} ofr={ofr:.1f} ifr={ifr:.1f} holes={has_holes}"
                    f" pos=({obj.location.x*scale:.0f},{obj.location.y*scale:.0f},{obj.location.z*scale:.0f})")
        return {
            'obj': obj, 'obj_type': 'bottom_shell',
            'width': w, 'depth': d, 'outer_height': oh,
            'bottom_thickness': bt, 'wall_thickness': wt,
            'corner_radius': cr, 'outer_fillet_radius': ofr,
            'inner_fillet_radius': ifr, 'step_height': sh,
            'has_holes': has_holes, 'hole_radius': hr,
            'hole_offset_x': hox, 'hole_offset_y': hoy,
            'pos_x': obj.location.x, 'pos_y': obj.location.y,
            'pos_z': obj.location.z + oh / 2.0,  # bottom shell has bottom at -oh/2, compensate to Z=0
        }
    
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
    
    # 应用单位缩放：所有尺寸参数 × scale (mm=1000, m=1)
    S = scale if scale > 0 else 1.0
    
    params = {
        'width': width * S,
        'depth': depth * S,
        'outer_height': outer_height * S,
        'bottom_thickness': bottom_thickness * S,
        'wall_thickness': wall_thickness * S,
        'corner_radius': corner_radius * S,
        'outer_fillet_radius': outer_fillet_radius * S,
        'inner_fillet_radius': inner_fillet_radius * S,
        'step_height': 1.0 * S,
        'pos_x': obj.location.x * S,
        'pos_y': obj.location.y * S,
        'pos_z': obj.location.z * S,
    }
    
    if has_holes:
        params['has_holes'] = True
        params['hole_radius'] = hole_radius_detected * S
        params['hole_offset_x'] = hole_offset_x * S
        params['hole_offset_y'] = hole_offset_y * S
        log_to_file(f"[STEP Exporter] Final hole params: radius={hole_radius_detected:.2f}, offset=({hole_offset_x:.1f},{hole_offset_y:.1f}), half_w={half_w:.1f}, half_d={half_d:.1f}")
    
    return params


