"""Test C++ export_top_shell_filleted_step directly with known-good params."""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import _step_exporter as cpp_exporter

out_file = os.path.join(os.path.dirname(__file__), 'test28.step')

# Known correct parameters from create_top_shell.py
# width=100, depth=70, outer_height=10, top_thickness=2.0, wall_thickness=2.0
# corner_radius=20.0, outer_fillet_radius=1.5, inner_fillet_radius=0.75
# top_recess=10.0, top_offset_y=3.0
# window_len=20.0, window_wid=10.0

print("Testing top shell without window...")
success = cpp_exporter.export_top_shell_filleted_step(
    out_file + ".nowindow",
    100.0, 70.0, 10.0,     # width, depth, outer_height
    2.0, 2.0, 20.0,         # top_thickness, wall_thickness, corner_radius
    1.5, 0.75,              # outer_fillet_radius, inner_fillet_radius
    11.5, 3.0,              # top_recess, top_offset_y (using detected values)
    0.0, 0.0,               # window_len, window_wid
    "AP242DIS", "MILLIMETER", 1)

print(f"No window: {success}")

print("\nTesting top shell with window...")
success2 = cpp_exporter.export_top_shell_filleted_step(
    out_file,
    100.0, 70.0, 10.0,
    2.0, 2.0, 20.0,
    1.5, 0.75,
    11.5, 3.0,
    20.0, 10.0,
    "AP242DIS", "MILLIMETER", 1)

print(f"With window: {success2}")