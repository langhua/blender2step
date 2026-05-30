"""Generate test40.step with updated C++ code to verify taper fix."""
import sys
import os

# Add the lib directory to path
lib_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'lib'))
sys.path.insert(0, lib_dir)

# Add DLL directory for Windows
if hasattr(os, 'add_dll_directory') and os.path.exists(lib_dir):
    os.add_dll_directory(lib_dir)

import _step_exporter as cpp_exporter

out_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'test40.step')

# Parameters matching test39.step
# width=100, depth=70, outer_height=10, top_thickness=2.0, wall_thickness=2.0
# corner_radius=20.0, outer_fillet_radius=1.5, inner_fillet_radius=0.75
# top_recess=10.0, top_offset_y=3.0 (estimated)
# window_len=0.0, window_wid=0.0 (no window for simplicity)

print("Generating test40.step with tapered top shell...")
print("Parameters: width=100, depth=70, height=10, recess=10")

success = cpp_exporter.export_top_shell_filleted_step(
    out_file,
    100.0, 70.0, 10.0,     # width, depth, outer_height
    2.0, 2.0, 20.0,         # top_thickness, wall_thickness, corner_radius
    1.5, 0.75,              # outer_fillet_radius, inner_fillet_radius
    10.0, 3.0,              # top_recess, top_offset_y
    0.0, 0.0,               # window_len, window_wid
    0.0, 0.0, 10.0,         # pos_x, pos_y, pos_z
    "AP242DIS", "MILLIMETER", 1)

print(f"Export result: {success}")

if success and os.path.exists(out_file):
    size = os.path.getsize(out_file)
    with open(out_file, 'r', encoding='utf-8', errors='replace') as f:
        content = f.read()
    solids = content.count('MANIFOLD_SOLID_BREP')
    print(f"SUCCESS: {out_file} ({size} bytes, {solids} solids)")
else:
    print(f"FAIL: Could not generate {out_file}")
