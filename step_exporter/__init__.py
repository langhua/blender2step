"""
STEP Exporter for Blender (Enhanced)
Version 4.1.2 with advanced BREP and solid creation support
"""

bl_info = {
    "name": "STEP Exporter (Enhanced)",
    "author": "Blender STEP Exporter",
    "version": (4, 1, 3),
    "blender": (4, 2, 0),
    "location": "File > Export > STEP (Enhanced)",
    "description": "Export to STEP format with advanced BREP, solid creation and geometry fixing",
    "category": "Import-Export",
}

import sys, os

# Support running as script (VSCode Blender Development) — set up package
if not __package__:
    _here = os.path.dirname(os.path.abspath(__file__))
    _parent = os.path.dirname(_here)
    if _parent not in sys.path:
        sys.path.insert(0, _parent)
    if _here not in sys.path:
        sys.path.insert(0, _here)
    __package__ = "step_exporter"

sys.path.append(os.path.abspath(os.path.dirname(__file__)))

# ====================== C++ module loading ======================
from .core.utils import log_to_file

_log_init_time = __import__("time").strftime("%H:%M:%S")
log_to_file(f"[STEP Exporter] [MODULE:v4] __init__.py loaded at {_log_init_time}")

from .core import _globals as _g

try:
    script_dir = os.path.dirname(os.path.realpath(__file__))
    if script_dir not in sys.path:
        sys.path.insert(0, script_dir)
    lib_path = os.path.join(script_dir, "lib")
    if os.path.exists(lib_path):
        os.environ["PATH"] = lib_path + ";" + os.environ.get("PATH", "")

    try:
        if os.path.exists(lib_path) and lib_path not in sys.path:
            sys.path.insert(0, lib_path)
        import _step_exporter as _mod
        _g.step_exporter = _mod
        if hasattr(_mod, "get_version"):
            log_to_file(f"[STEP Exporter] [OK] C++ loaded (lib) v={_mod.get_version()}")
            _g.CPP_MODULE_LOADED = True
        else:
            _g.MODULE_LOAD_ERROR = "C++ module missing functions"
    except ImportError:
        try:
            import _step_exporter as _mod
            _g.step_exporter = _mod
            if hasattr(_mod, "get_version"):
                log_to_file(f"[STEP Exporter] [OK] C++ loaded (direct) v={_mod.get_version()}")
                _g.CPP_MODULE_LOADED = True
            else:
                _g.MODULE_LOAD_ERROR = "C++ module missing functions"
        except ImportError as e:
            _g.MODULE_LOAD_ERROR = f"ImportError: {e}"
except Exception as e:
    _g.MODULE_LOAD_ERROR = f"Error: {e}"

# ====================== Sub-module imports ======================
from . import core
from . import analysis
from . import export
from . import ui

# Re-export for backward compatibility
from .core.utils import log_to_file, _verify_step_shell, _merge_step_files, _merge_log_files
from .core.mesh_data import _get_mesh_data_enhanced, _get_curve_data_enhanced
from .analysis import _analyze_top_shell_from_mesh, _analyze_bottom_shell_from_mesh, _analyze_cylinder_from_mesh
from .export import _export_parametric_sync, _export_bottom_shells_sync, _export_cylinder_staged, _parametric_export_staged, _export_worker_timer
from .ui import (
    STEP_EXPORTER_OT_export_enhanced, STEP_EXPORTER_PT_main_panel, STEP_EXPORTER_PT_sample_generators,
    STEP_EXPORTER_OT_create_top_shell, STEP_EXPORTER_OT_create_bottom_shell, STEP_EXPORTER_OT_create_rect_box,
    STEP_EXPORTER_OT_create_cylinder, STEP_EXPORTER_OT_create_cylinder_gallery,
    STEP_EXPORTER_OT_create_cone_gallery, STEP_EXPORTER_OT_create_cone_gallery_inverted,
    STEP_EXPORTER_OT_create_parametric_cylinder,
    STEP_EXPORTER_OT_create_parametric_shell,
    STEP_EXPORTER_OT_add_hole_to_shell,
    STEP_EXPORTER_OT_remove_shell_hole,
    STEP_EXPORTER_OT_edit_shell_hole,
    STEP_EXPORTER_OT_clear_shell_holes,
    STEP_EXPORTER_PT_shell_holes,
    STEP_EXPORTER_PT_cylinder_panel, menu_func_export_enhanced,
    _generate_parametric_cylinder, _apply_edge_treatment,
    _create_holes, _apply_hole_fillet, _on_hole_param_change, _boolean_difference,
)

_classes = (
    STEP_EXPORTER_OT_export_enhanced,
    STEP_EXPORTER_PT_main_panel,
    STEP_EXPORTER_PT_sample_generators,
    STEP_EXPORTER_OT_create_top_shell,
    STEP_EXPORTER_OT_create_bottom_shell,
    STEP_EXPORTER_OT_create_rect_box,
    STEP_EXPORTER_OT_create_cylinder,
    STEP_EXPORTER_OT_create_cylinder_gallery,
    STEP_EXPORTER_OT_create_cone_gallery, STEP_EXPORTER_OT_create_cone_gallery_inverted,
    STEP_EXPORTER_OT_create_parametric_cylinder,
    STEP_EXPORTER_OT_create_parametric_shell,
    STEP_EXPORTER_OT_add_hole_to_shell,
    STEP_EXPORTER_OT_remove_shell_hole,
    STEP_EXPORTER_OT_edit_shell_hole,
    STEP_EXPORTER_OT_clear_shell_holes,
    STEP_EXPORTER_PT_shell_holes,
    STEP_EXPORTER_PT_cylinder_panel,
)


def register():
    from .export.progress_report import register as _rp
    _rp()
    from .core.i18n import register_translations
    register_translations()
    import bpy
    for cls in _classes:
        try:
            bpy.utils.register_class(cls)
        except ValueError:
            bpy.utils.unregister_class(cls)
            bpy.utils.register_class(cls)
    from bpy.types import TOPBAR_MT_file_export
    TOPBAR_MT_file_export.append(menu_func_export_enhanced)


def unregister():
    import bpy
    from bpy.types import TOPBAR_MT_file_export
    TOPBAR_MT_file_export.remove(menu_func_export_enhanced)
    for cls in reversed(_classes):
        bpy.utils.unregister_class(cls)
    from .export.progress_report import unregister as _urp
    _urp()
    from .core.i18n import unregister_translations
    unregister_translations()


if __name__ == "__main__":
    register()
