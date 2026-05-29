"""Export each top shell to a separate STEP file for individual testing."""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Need to run after create_top_shell.py creates the objects
import bpy

# Import the C++ module directly
import _step_exporter as cpp

out_dir = os.path.dirname(os.path.abspath(__file__))

# Parameters from the previous export
params = {
    'width': 100.0, 'depth': 70.0, 'outer_height': 10.0,
    'top_thickness': 1.5, 'wall_thickness': 2.7427,
    'corner_radius': 20.0,
    'outer_fillet_radius': 2.0, 'inner_fillet_radius': 1.2,
    'top_recess': 11.5182, 'top_offset_y': -3.0091,
}

# No-window shell
print("=== Exporting no-window shell (separate) ===")
result = cpp.export_top_shell_filleted_step(
    os.path.join(out_dir, 'test28_nowindow.step'),
    params['width'], params['depth'], params['outer_height'],
    params['top_thickness'], params['wall_thickness'], params['corner_radius'],
    params['outer_fillet_radius'], params['inner_fillet_radius'],
    params['top_recess'], params['top_offset_y'],
    0.0, 0.0,  # no window
    "AP242DIS", "MILLIMETER", 1
)
print(f"No-window export: {'OK' if result else 'FAILED'}")

# With-window shell
print("=== Exporting with-window shell (separate) ===")
result = cpp.export_top_shell_filleted_step(
    os.path.join(out_dir, 'test28_window.step'),
    params['width'], params['depth'], params['outer_height'],
    params['top_thickness'], params['wall_thickness'], params['corner_radius'],
    params['outer_fillet_radius'], params['inner_fillet_radius'],
    params['top_recess'], params['top_offset_y'],
    20.0, 10.0,  # 20x10 window
    "AP242DIS", "MILLIMETER", 1
)
print(f"With-window export: {'OK' if result else 'FAILED'}")