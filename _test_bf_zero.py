"""Test script for bottom_fillet=0 curved shell issue."""
import sys, os

# Setup path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'step_exporter', 'lib'))
import _step_exporter as cpp

# User's parameters from screenshot
width, depth, height = 100.0, 80.0, 50.0
thickness = 2.0
corner_radius = 5.0
corner_type = "curved"
rim_type = "inside"
rim_width = 1.5
rim_height = 1.0
rim_shape = "rect"
rim_top_ratio = 1.0
bottom_fillet = 0.0
curve_ratio = 0.5
pos_x, pos_y, pos_z = 0.0, 0.0, 0.0

outfile = os.path.join(os.path.dirname(__file__), 'test_bf_zero.step')

print(f"Testing with bf={bottom_fillet}, curved corners...")
print(f"  dims: {width}x{depth}x{height}, wall={thickness}, cr={corner_radius}")
print(f"  curve_ratio={curve_ratio}, rim={rim_type} rw={rim_width} rh={rim_height}")

success = cpp.export_parametric_shell_step(
    outfile,
    width, depth, height, thickness,
    corner_radius, corner_type,
    pos_x, pos_y, pos_z,
    rim_type, rim_width, rim_height,
    "AP214IS", "MILLIMETER", 1,
    rim_shape, rim_top_ratio,
    bottom_fillet, curve_ratio
)

print(f"Result: {'SUCCESS' if success else 'FAILED'}")
print(f"Output: {outfile}")

# Also test with bf=2 for comparison
outfile2 = os.path.join(os.path.dirname(__file__), 'test_bf_two.step')
success2 = cpp.export_parametric_shell_step(
    outfile2,
    width, depth, height, thickness,
    corner_radius, corner_type,
    pos_x, pos_y, pos_z,
    rim_type, rim_width, rim_height,
    "AP214IS", "MILLIMETER", 1,
    rim_shape, rim_top_ratio,
    2.0, curve_ratio
)
print(f"\nComparison (bf=2): {'SUCCESS' if success2 else 'FAILED'}")
print(f"Output: {outfile2}")
