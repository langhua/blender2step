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
    log_to_file(f"[STEP Exporter]   curve_ratio={obj.get('curve_ratio', 50.0):.0f}% eccentric_y={obj.get('eccentric_y', 0.0):.0f}%")
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
        'eccentric_y': obj.get('eccentric_y', 0.0) / 100.0,
        'pos_x': obj.location.x * scale, 'pos_y': -obj.location.y * scale,
        'pos_z': (obj.location.z * scale) - (h_mm / 2.0),
        'window_data': _convert_window_data(obj, scale, h_mm),
    }


def _convert_window_data(obj, scale, h_mm):
    """Convert window_data from shell-local to world coords.
    Also fix incorrect cz values from old Z-clamp bug.
    IMPORTANT: Apply Rotation (Ctrl+A) on the shell before export."""
    wd = obj.get('window_data', '')
    if not wd or not obj.get('window_data_local'):
        return wd

    pos_x = obj.location.x * scale
    pos_y = obj.location.y * scale
    pos_z = (obj.location.z * scale) - (h_mm / 2.0)
    t_mm = obj.get('wall_thickness', 2.0) * (1000.0 if obj.get('unit', 'm') == 'm' else 1.0)

    entries = wd.split(';')
    converted = []
    for entry in entries:
        entry = entry.strip()
        if not entry:
            continue
        parts = entry.split(',')
        if len(parts) < 5:
            converted.append(entry)
            continue
        try:
            cx = float(parts[0])
            cy = float(parts[1])
            cz = float(parts[2])
            face = int(float(parts[-1])) if len(parts) >= 8 else -1

            # Fix old Z-clamp bug: wrong cz for bottom/top face holes
            if face == 0 and (cz > h_mm * 0.5 or cz < 0):
                cz = min(max(cz, 0.0), t_mm)
            elif face == 1 and (cz < h_mm * 0.5 or cz > h_mm):
                cz = max(min(cz, h_mm), h_mm - t_mm)

            cx_w = cx + pos_x
            cy_w = -(cy + pos_y)
            cz_w = cz + pos_z
            parts[0] = f"{cx_w:.3f}"
            parts[1] = f"{cy_w:.3f}"
            parts[2] = f"{cz_w:.3f}"
        except ValueError:
            pass
        converted.append(','.join(parts))
    return ';'.join(converted)
