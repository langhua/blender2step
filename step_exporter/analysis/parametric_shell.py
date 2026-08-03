"""Analysis for parametric shell objects."""
from ..core.utils import log_to_file


def _analyze_parametric_shell_from_mesh(obj, context=None, scale=1.0):
    """Read parametric shell parameters from custom properties.
    Returns a dict compatible with the staged export pipeline, or None."""
    if obj.type != 'MESH':
        return None
    if obj.get('object_type', '') != 'parametric_shell':
        return None

    # Shell will be exported as parametric solid, with holes cut via OCCT boolean ops
    if obj.get('window_data', ''):
        log_to_file(f"[STEP Exporter] Parametric shell has holes — will cut via OCCT boolean")

    w = obj.get('width', 100.0)
    d = obj.get('depth', 80.0)
    h = obj.get('height', 50.0)
    t = obj.get('wall_thickness', 2.0)
    bt = obj.get('bottom_thickness', t)  # default to wall thickness if not set
    cr = obj.get('corner_radius', 0.0)
    corner_type = obj.get('corner_type', 'square')

    log_to_file(f"[STEP Exporter] Parametric shell: {w:.0f}x{d:.0f}x{h:.0f}mm"
                f" wall={t:.1f} corner={corner_type} cr={cr:.1f}")

    # Read unit (default 'm' for backward compat with objects created before unit support)
    unit = obj.get('unit', 'm')
    # Conversion factor to mm for STEP output
    unit_factor = 1000.0 if unit == 'm' else 1.0

    w_mm = w * unit_factor
    d_mm = d * unit_factor
    h_mm = h * unit_factor
    t_mm = t * unit_factor
    bt_mm = bt * unit_factor
    cr_mm = cr * unit_factor

    rim_type = obj.get('rim_type', 'none')
    rim_w_mm = obj.get('rim_width', 1.0) * unit_factor if rim_type != 'none' else 0.0
    rim_h_mm = obj.get('rim_height', 1.0) * unit_factor if rim_type != 'none' else 0.0
    rim_shape = obj.get('rim_shape', 'rect')
    rim_top_ratio = obj.get('rim_top_ratio', 100.0) / 100.0  # 0.0-1.0
    bf = obj.get('bottom_fillet', 0.0) * unit_factor

    log_to_file(f"[STEP Exporter]   unit={unit}, factor={unit_factor}, dims={w_mm:.1f}x{d_mm:.1f}x{h_mm:.1f}mm")
    log_to_file(f"[STEP Exporter]   curve_ratio={obj.get('curve_ratio', 50.0):.0f}% curve_ratio_y={obj.get('curve_ratio_y', obj.get('curve_ratio', 50.0)):.0f}% eccentric_y={obj.get('eccentric_y', 0.0):.0f}%")
    if rim_type != 'none':
        log_to_file(f"[STEP Exporter]   rim={rim_type} rw={rim_w_mm:.1f} rh={rim_h_mm:.1f} shape={rim_shape} ratio={rim_top_ratio:.2f}")
    if bf > 0:
        log_to_file(f"[STEP Exporter]   bottom_fillet={bf:.1f}mm")

    return {
        'obj': obj,
        'obj_type': 'parametric_shell',
        'width': w_mm,
        'depth': d_mm,
        'height': h_mm,
        'wall_thickness': t_mm,
        'bottom_thickness': bt_mm,
        'corner_type': corner_type,
        'corner_radius': cr_mm,
        'rim_type': rim_type,
        'rim_width': rim_w_mm,
        'rim_height': rim_h_mm,
        'rim_shape': rim_shape,
        'rim_top_ratio': rim_top_ratio,
        'bottom_fillet': bf,
        'curve_ratio': obj.get('curve_ratio', 0.5) / 100.0 if obj.get('corner_type') == 'curved' else 0.5,
        'curve_ratio_y': obj.get('curve_ratio_y', obj.get('curve_ratio', 50.0)) / 100.0 if obj.get('corner_type') == 'curved' else 0.5,
        'eccentric_y': obj.get('eccentric_y', 0.0) / 100.0,
        'pos_x': obj.location.x * scale,
        'pos_y': obj.location.y * scale,
        'pos_z': (obj.location.z * scale) - (h_mm / 2.0),
        'rot_x': obj.rotation_euler.x, 'rot_y': obj.rotation_euler.y, 'rot_z': obj.rotation_euler.z,
        'window_data': _fix_window_data_faces(obj),
    }


def _fix_window_data_faces(obj):
    """Fix hole face assignments for STEP export constraints.
    Parametric shell top is open (only a rim) → face 1 (top) holes route to nearest side wall.
    Coordinates remain in shell-local mm — C++ cuts holes BEFORE translating the shell.
    For rotated shells: if flipped 180° around X or Y, swap bottom↔top faces
    since the shell-local 'top' now corresponds to the solid bottom in the user's view."""
    wd = obj.get('window_data', '')
    if not wd or not obj.get('window_data_local'):
        return wd

    import math
    rx, ry, rz = obj.rotation_euler.x, obj.rotation_euler.y, obj.rotation_euler.z
    # Check if shell is flipped (180° around X or Y) — top/bottom swap
    flipped = (abs(abs(rx) - math.pi) < 0.01) or (abs(abs(ry) - math.pi) < 0.01)

    unit_factor = 1000.0 if obj.get('unit', 'm') == 'm' else 1.0
    w_mm = obj.get('width', 100.0) * unit_factor
    d_mm = obj.get('depth', 80.0) * unit_factor
    half_w, half_d = w_mm / 2.0, d_mm / 2.0

    entries = wd.split(';')
    fixed = []
    for entry in entries:
        entry = entry.strip()
        if not entry:
            continue
        parts = entry.split(',')
        if len(parts) < 8:
            fixed.append(entry)
            continue
        try:
            face = int(float(parts[-1]))
            if face == 1:  # top face (open rim, no solid wall)
                if flipped:
                    # Shell is flipped 180°: shell-local top → world bottom.
                    # Remap to bottom face (solid wall) and mirror cz to cut actual material.
                    h_mm = obj.get('height', 50.0) * unit_factor
                    cz = float(parts[2])
                    parts[2] = f"{h_mm - cz:.3f}"
                    parts[-1] = "0"
                else:
                    # Normal orientation: reroute open-top hole to nearest side wall
                    cx = float(parts[0])
                    cy = float(parts[1])
                    dist_r = abs(cx - half_w)
                    dist_l = abs(cx + half_w)
                    dist_b = abs(cy - half_d)
                    dist_f = abs(cy + half_d)
                    nearest = min(dist_r, dist_l, dist_b, dist_f)
                    if nearest == dist_r:
                        parts[0] = f"{half_w:.3f}"
                        parts[-1] = "3"
                    elif nearest == dist_l:
                        parts[0] = f"{-half_w:.3f}"
                        parts[-1] = "2"
                    elif nearest == dist_b:
                        parts[1] = f"{half_d:.3f}"
                        parts[-1] = "5"
                    else:
                        parts[1] = f"{-half_d:.3f}"
                        parts[-1] = "4"
        except (ValueError, IndexError):
            pass
        fixed.append(','.join(parts))
    return ';'.join(fixed)
