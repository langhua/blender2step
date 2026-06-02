"""
验证台阶环检测和壁厚分析算法 — 使用更细粒度的角度扇区

关键洞察:
- 矩形轮廓的顶点距离范围很大(边缘中心~35mm 到 角落~61mm)
- 按距离排序会混合不同角度的顶点, 无法区分内外轮廓
- 必须在相同角度区域内配对内外顶点
- 16扇区太粗, 角落扇区(22.5°)包含了角度差很大的顶点
"""
import math

class MockVertex:
    def __init__(self, x, y, z):
        self.co = type('Coord', (), {'x': x, 'y': y, 'z': z})()


def generate_rect_contour(cx, cy, z, half_w, half_d, n_per_side=24):
    """生成矩形轮廓的顶点坐标（4条边均匀采样）"""
    verts = []
    for i in range(n_per_side):
        t = i / (n_per_side - 1)
        y = -half_d + t * (2 * half_d)
        verts.append((cx + half_w, cy + y, z))
    for i in range(n_per_side):
        t = i / (n_per_side - 1)
        x = half_w - t * (2 * half_w)
        verts.append((cx + x, cy + half_d, z))
    for i in range(n_per_side):
        t = i / (n_per_side - 1)
        y = half_d - t * (2 * half_d)
        verts.append((cx - half_w, cy + y, z))
    for i in range(n_per_side):
        t = i / (n_per_side - 1)
        x = -half_w + t * (2 * half_w)
        verts.append((cx + x, cy - half_d, z))
    return verts


def angular_sector_wall_thickness(mock_verts, cx, cy, num_sectors=36, inner_fraction=1/3, outer_fraction=1/3):
    """使用角度扇区分法计算壁厚/台阶环宽度"""
    sector_angle_step = 2.0 * math.pi / num_sectors
    sector_dists = [[] for _ in range(num_sectors)]

    for v in mock_verts:
        dx = v.co.x - cx
        dy = v.co.y - cy
        dist = math.sqrt(dx * dx + dy * dy)
        angle = math.atan2(dy, dx)
        if angle < 0:
            angle += 2.0 * math.pi
        sector_idx = int(angle / sector_angle_step) % num_sectors
        sector_dists[sector_idx].append(dist)

    sector_walls = []
    for s_dists in sector_dists:
        if len(s_dists) < 3:
            continue
        s_dists.sort()
        n_s = len(s_dists)
        inner_n = max(1, int(n_s * inner_fraction))
        outer_n = max(1, int(n_s * outer_fraction))
        inner_s = sum(s_dists[:inner_n]) / inner_n
        outer_s = sum(s_dists[-outer_n:]) / outer_n
        if outer_s > inner_s + 0.2:
            sector_walls.append(outer_s - inner_s)

    if not sector_walls:
        return None, sector_dists

    sector_walls.sort()
    trim_n = max(1, len(sector_walls) // 4)
    if len(sector_walls) > trim_n * 2:
        trimmed = sector_walls[trim_n:-trim_n]
    else:
        trimmed = sector_walls
    return sum(trimmed) / len(trimmed), sector_dists


def test_step_ring_angular(cx, cy, bottom_z, outer_hw, outer_hd, ring_width,
                           wall_thickness, z_layer, num_sectors_list):
    """测试台阶环检测 — 使用角度扇区法"""
    print(f"  Vertices at z={z_layer} (step ring mid-height)")

    inner_hw = outer_hw - ring_width
    inner_hd = outer_hd - ring_width
    cavity_hw = outer_hw - wall_thickness
    cavity_hd = outer_hd - wall_thickness

    outer_verts = generate_rect_contour(cx, cy, z_layer, outer_hw, outer_hd)
    ring_inner_verts = generate_rect_contour(cx, cy, z_layer, inner_hw, inner_hd)
    cavity_verts = generate_rect_contour(cx, cy, z_layer, cavity_hw, cavity_hd)

    # Test with just 2 contours (step ring only)
    mock_2c = [MockVertex(x, y, z_layer) for x, y, z in outer_verts + ring_inner_verts]
    # Test with 3 contours (step ring + cavity)
    mock_3c = [MockVertex(x, y, z_layer) for x, y, z in outer_verts + ring_inner_verts + cavity_verts]

    for label, mock_verts in [("2 contours", mock_2c), ("3 contours", mock_3c)]:
        print(f"    {label} ({len(mock_verts)} verts):")
        for num_sectors in num_sectors_list:
            result, _ = angular_sector_wall_thickness(mock_verts, cx, cy, num_sectors)
            if result is not None:
                err = abs(result - ring_width)
                print(f"      {num_sectors:3d} sectors → {result:.2f}mm (err={err:.2f}mm) {'✓' if err <= 1.0 else '✗'}")
            else:
                print(f"      {num_sectors:3d} sectors → no result")


def test_wall_thickness_angular(cx, cy, mid_z, outer_hw, outer_hd, wall_thickness, num_sectors_list):
    """测试壁厚分析 — 使用角度扇区法"""
    print(f"  Vertices at z={mid_z} (mid-height)")

    inner_hw = outer_hw - wall_thickness
    inner_hd = outer_hd - wall_thickness

    outer_verts = generate_rect_contour(cx, cy, mid_z, outer_hw, outer_hd)
    inner_verts = generate_rect_contour(cx, cy, mid_z, inner_hw, inner_hd)

    mock_verts = [MockVertex(x, y, mid_z) for x, y, z in outer_verts + inner_verts]

    print(f"    {len(mock_verts)} verts (outer+inner):")
    for num_sectors in num_sectors_list:
        result, sector_dists = angular_sector_wall_thickness(mock_verts, cx, cy, num_sectors)
        if result is not None:
            err = abs(result - wall_thickness)
            ok = err <= 0.5
            # Count populated sectors
            populated = sum(1 for s in sector_dists if len(s) >= 3)
            print(f"      {num_sectors:3d} sectors ({populated} populated) → {result:.2f}mm (err={err:.2f}mm) {'✓' if ok else '✗'}")
        else:
            print(f"      {num_sectors:3d} sectors → no result")


if __name__ == "__main__":
    print("=" * 70)
    print("Angular Sector Wall Thickness Analysis — Sector Count Comparison")
    print("=" * 70)

    num_sectors_list = [16, 24, 32, 48, 64, 96]

    # === Step Ring Detection ===
    print("\n--- Step Ring Detection (expected: 1.0mm) ---")
    cx, cy = 0.0, 0.0
    bottom_z = -6.0
    outer_hw, outer_hd = 50.0, 35.0
    ring_width = 1.0
    wall_thickness = 2.0

    test_step_ring_angular(cx, cy, bottom_z, outer_hw, outer_hd,
                           ring_width, wall_thickness, z_layer=-5.5,
                           num_sectors_list=num_sectors_list)

    # === Wall Thickness Detection ===
    print("\n--- Wall Thickness Detection (expected: 2.0mm) ---")
    mid_hw, mid_hd = 44.25, 29.25

    test_wall_thickness_angular(cx, cy, -0.5, mid_hw, mid_hd, 2.0, num_sectors_list)

    # === Effect of inner_fraction on wall thickness ===
    print("\n--- Effect of inner/outer fraction (64 sectors, wall thickness) ---")
    mock_verts_wt = [MockVertex(x, y, -0.5) for x, y, z in
                     generate_rect_contour(0, 0, -0.5, 44.25, 29.25) +
                     generate_rect_contour(0, 0, -0.5, 42.25, 27.25)]

    for frac in [0.1, 0.15, 0.2, 0.25, 0.33, 0.4, 0.5]:
        result, _ = angular_sector_wall_thickness(mock_verts_wt, 0, 0, 64, frac, frac)
        if result is not None:
            print(f"    frac={frac:.2f} → {result:.2f}mm (err={abs(result-2.0):.2f}mm)")
        else:
            print(f"    frac={frac:.2f} → no result")

    print("\n" + "=" * 70)
    print("Done")
    print("=" * 70)