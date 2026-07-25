"""Standalone test: export parametric shell with known hole config, collect DIAG log."""
import sys, os

# Add OCCT DLL directory before importing _step_exporter
_lib_dir = os.path.join(os.path.dirname(__file__), 'step_exporter', 'lib')
os.add_dll_directory(_lib_dir)
sys.path.insert(0, _lib_dir)
import _step_exporter as cpp

# Shell params (estimated from test30 STEP bbox: X ~ ±36.5, Y ~ ±27.4, Z ~ 1.6..?)
width, depth, height = 73.0, 55.0, 40.0
thickness = 3.0
bottom_thickness = 2.0
corner_radius = 5.0
corner_type = "curved"
rim_type = "inside"
rim_width = 1.5
rim_height = 1.0
rim_shape = "rect"
rim_top_ratio = 1.0
bottom_fillet = 2.0
curve_ratio = 0.5
eccentric_y = 0.0
pos_x, pos_y, pos_z = 0.0, 0.0, 0.0

# Known window_data from test30 (3 rrect holes on bottom face fc=0)
window_data = (
    "9.800,9.500,3.600,44.600,2,25.700,0.100,0.200,0,0;"
    "-31.400,12.400,3.600,15.000,2,10.000,0.100,0.200,0,0;"
    "0.600,-18.400,3.600,12.000,2,8.000,0.100,0.200,0,0"
)

outfile = os.path.join(os.path.dirname(__file__), 'step_exporter', 'test_diag.step')

print(f"Exporting with diag to: {outfile}")
print(f"  shell: {width}x{depth}x{height} wall={thickness} bf={bottom_fillet}")
print(f"  pos=({pos_x},{pos_y},{pos_z})")
print(f"  window_data={window_data}")

success = cpp.export_parametric_shell_step(
    outfile,
    width, depth, height, thickness,
    bottom_thickness, corner_radius, corner_type,
    pos_x, pos_y, pos_z,
    rim_type, rim_width, rim_height,
    "AP214IS", "MILLIMETER", 1,
    rim_shape, rim_top_ratio,
    bottom_fillet, curve_ratio, eccentric_y, window_data,
    0.0, 0.0, 0.0,  # rot_x, rot_y, rot_z
)

print(f"Result: {'SUCCESS' if success else 'FAILED'}")

# Print the log file
logfile = outfile + ".log"
if os.path.exists(logfile):
    print(f"\n--- LOG ({logfile}) ---")
    with open(logfile, 'r', encoding='utf-8', errors='replace') as f:
        for line in f:
            if '[DIAG]' in line or 'Hole cutter' in line or 'pre-cut' in line or 'post-cut' in line or 'Applied' in line:
                print(line.rstrip())
    print("--- END LOG ---")
else:
    print(f"\nWARNING: No log file found at {logfile}")
