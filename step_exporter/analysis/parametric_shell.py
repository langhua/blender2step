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
        'pos_x': obj.location.x * scale,
        'pos_y': obj.location.y * scale,
        'pos_z': (obj.location.z * scale) - (h_mm / 2.0),
        'rot_x': obj.rotation_euler.x, 'rot_y': obj.rotation_euler.y, 'rot_z': obj.rotation_euler.z,
        'window_data': _convert_window_data(obj, scale, h_mm),
    }


def _convert_window_data(obj, scale, h_mm):
    """Convert window_data from shell-local to world coords.
    Applies object rotation to hole positions, so C++ rotation
    (applied after cutting) flips them back to match Blender's viewport."""
    wd = obj.get('window_data', '')
    if not wd or not obj.get('window_data_local'):
        return wd

    pos_x = obj.location.x * scale
    pos_y = obj.location.y * scale
    pos_z = (obj.location.z * scale) - (h_mm / 2.0)
    t_mm = obj.get('wall_thickness', 2.0) * (1000.0 if obj.get('unit', 'm') == 'm' else 1.0)

    # Check if object has significant rotation (any axis)
    rx, ry, rz = obj.rotation_euler.x, obj.rotation_euler.y, obj.rotation_euler.z
    has_rotation = abs(rx) > 1e-6 or abs(ry) > 1e-6 or abs(rz) > 1e-6

    # For rotated shells, the C++ rotation (applied after cutting) will flip X/Z.
    # Compensate by pre-negating coords so the net result matches Blender's viewport.
    # Only bottom/top face holes (fc=0,1) need X compensation for Y rotation.
    # Side face holes (fc=2-5) have different axis mappings.
    negate_x = has_rotation and abs(ry) > 1e-6

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

            # Clamp cz to valid range for the assigned face.
            if face == 0:
                cz = max(0.0, min(cz, t_mm))
            elif face == 1:
                cz = min(h_mm, max(cz, h_mm - t_mm))

            # Apply rotation compensation:
            # Y rotation flips X; C++ will flip it back after cutting.
            # Only applies to bottom/top face holes where X is along-face.
            # Side face holes (fc=2-5): X is through-wall, not compensated.
            if negate_x and face in (0, 1):
                cx_w = pos_x - cx
            else:
                cx_w = cx + pos_x
            cy_w = cy + pos_y
            cz_w = cz + pos_z
            parts[0] = f"{cx_w:.3f}"
            parts[1] = f"{cy_w:.3f}"
            parts[2] = f"{cz_w:.3f}"
        except ValueError:
            pass
        converted.append(','.join(parts))
    return ';'.join(converted)
