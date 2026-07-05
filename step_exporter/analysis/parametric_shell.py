"""Analysis for parametric shell objects."""
from ..core.utils import log_to_file


def _analyze_parametric_shell_from_mesh(obj, context=None, scale=1.0):
    """Read parametric shell parameters from custom properties.
    Returns a dict compatible with the staged export pipeline, or None."""
    if obj.type != 'MESH':
        return None
    if obj.get('object_type', '') != 'parametric_shell':
        return None

    w = obj.get('width', 100.0)
    d = obj.get('depth', 80.0)
    h = obj.get('height', 50.0)
    t = obj.get('wall_thickness', 2.0)
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
    cr_mm = cr * unit_factor

    log_to_file(f"[STEP Exporter]   unit={unit}, factor={unit_factor}, dims={w_mm:.1f}x{d_mm:.1f}x{h_mm:.1f}mm")

    return {
        'obj': obj,
        'obj_type': 'parametric_shell',
        'width': w_mm,
        'depth': d_mm,
        'height': h_mm,
        'wall_thickness': t_mm,
        'corner_type': corner_type,
        'corner_radius': cr_mm,
        'pos_x': obj.location.x * scale,
        'pos_y': obj.location.y * scale,
        'pos_z': obj.location.z * scale,
    }
