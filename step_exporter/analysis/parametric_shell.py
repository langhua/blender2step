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

    # Scale dimensions and position: Blender BU values × scale → mm for STEP
    w_mm = w * scale
    d_mm = d * scale
    h_mm = h * scale
    t_mm = t * scale
    cr_mm = cr * scale

    log_to_file(f"[STEP Exporter]   blender_loc=({obj.location.x:.4f}, {obj.location.y:.4f}, {obj.location.z:.4f}) scale={scale}")
    log_to_file(f"[STEP Exporter]   dims: {w_mm:.1f}x{d_mm:.1f}x{h_mm:.1f}mm wall={t_mm:.2f} cr={cr_mm:.2f}")

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
