"""Shared rounded-rectangle profile and fillet-ring utilities.
Used by parametric_shell.py and examples/create_bottom_shell.py.
"""
import math


def make_profile(hw, hd, cr_val, segments):
    """Build CCW (x,y) profile for a rounded rectangle.

    Args:
        hw: half-width of the straight-edge bounding box
        hd: half-depth of the straight-edge bounding box
        cr_val: corner radius
        segments: number of segments per 90° arc and per straight edge

    Returns:
        List of (x, y) tuples, CCW starting from right edge going +Y.
        Total points = 8 * segments.
    """
    n = segments
    rhw, rhd = hw, hd
    # Dynamic corner centers (match offset and radius)
    cc = [(-rhw + cr_val, -rhd + cr_val), (rhw - cr_val, -rhd + cr_val),
          (rhw - cr_val, rhd - cr_val), (-rhw + cr_val, rhd - cr_val)]

    pts = []
    # 1. Right edge (+Y)
    for i in range(1, n + 1):
        y = -rhd + cr_val + (2 * (rhd - cr_val)) * i / n
        pts.append((rhw, y))
    # 2. Back-right arc
    cx, cy = cc[2]
    for j in range(1, n + 1):
        a = j * (math.pi / 2) / n
        pts.append((cx + cr_val * math.cos(a), cy + cr_val * math.sin(a)))
    # 3. Back edge (-X)
    for i in range(1, n + 1):
        x = rhw - cr_val - (2 * (rhw - cr_val)) * i / n
        pts.append((x, rhd))
    # 4. Back-left arc
    cx, cy = cc[3]
    for j in range(1, n + 1):
        a = math.pi / 2 + j * (math.pi / 2) / n
        pts.append((cx + cr_val * math.cos(a), cy + cr_val * math.sin(a)))
    # 5. Left edge (-Y)
    for i in range(1, n + 1):
        y = rhd - cr_val - (2 * (rhd - cr_val)) * i / n
        pts.append((-rhw, y))
    # 6. Front-left arc
    cx, cy = cc[0]
    for j in range(1, n + 1):
        a = math.pi + j * (math.pi / 2) / n
        pts.append((cx + cr_val * math.cos(a), cy + cr_val * math.sin(a)))
    # 7. Front edge (+X)
    for i in range(1, n + 1):
        x = -rhw + cr_val + (2 * (rhw - cr_val)) * i / n
        pts.append((x, -rhd))
    # 8. Front-right arc
    cx, cy = cc[1]
    for j in range(1, n + 1):
        a = 3 * math.pi / 2 + j * (math.pi / 2) / n
        pts.append((cx + cr_val * math.cos(a), cy + cr_val * math.sin(a)))
    return pts


def add_fillet_rings(bm, wall_hw, wall_hd, wall_cr, bottom_hw, bottom_hd, bottom_cr,
                     bottom_z, fillet_r, fillet_seg, seg):
    """Add fillet transition rings + outer wall to a BMesh.

    Creates bottom N-gon face at Z=bottom_z, then fillet_seg transition rings
    using profile-based corner-radius interpolation, ending at the wall profile
    at Z = bottom_z + fillet_r.  Wall faces go from last ring up to Z=wall_top_z.

    Args:
        bm: BMesh to add geometry to
        wall_hw, wall_hd: half-width/depth of wall profile
        wall_cr: corner radius of wall profile
        bottom_hw, bottom_hd: half-width/depth of bottom profile
        bottom_cr: corner radius of bottom profile
        bottom_z: Z coordinate of bottom face
        fillet_r: fillet radius
        fillet_seg: number of fillet transition rings
        seg: segments per profile arc/edge

    Returns:
        (bottom_vertices, top_vertices, profile_count)
        where top_vertices are at Z = bottom_z + fillet_r (base of outer wall).
    """
    num_pts = 8 * seg

    # Bottom face (N-gon)
    bottom_pts = make_profile(bottom_hw, bottom_hd, bottom_cr, seg)
    bot_v = [bm.verts.new((x, y, bottom_z)) for x, y in bottom_pts]
    bm.faces.new(list(reversed(bot_v)))

    # Fillet transition rings
    prev = bot_v
    for si in range(1, fillet_seg + 1):
        frac = si / fillet_seg
        ang = math.pi / 2.0 * frac
        sin_a = math.sin(ang)
        rise = fillet_r * (1.0 - math.cos(ang))
        ring_cr = bottom_cr + (wall_cr - bottom_cr) * sin_a
        # Offset of this ring from the wall (0 at wall, fillet_r at bottom)
        ring_off_wall = fillet_r * (1.0 - sin_a)
        ring_hw = wall_hw - ring_off_wall
        ring_hd = wall_hd - ring_off_wall
        ring_pts = make_profile(ring_hw, ring_hd, ring_cr, seg)
        ring_v = [bm.verts.new((x, y, bottom_z + rise)) for x, y in ring_pts]
        for i in range(num_pts):
            j = (i + 1) % num_pts
            bm.faces.new([prev[i], prev[j], ring_v[j], ring_v[i]])
        prev = ring_v

    # Wall top vertices (caller should connect these to whatever is above)
    wall_pts = make_profile(wall_hw, wall_hd, wall_cr, seg)
    top_v = [bm.verts.new((x, y, bottom_z + fillet_r)) for x, y in wall_pts]
    for i in range(num_pts):
        j = (i + 1) % num_pts
        bm.faces.new([prev[i], prev[j], top_v[j], top_v[i]])

    return bot_v, top_v, num_pts
