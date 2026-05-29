"""Test which parameter causes crash by varying one at a time."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import _step_exporter as cpp_exporter

out_dir = os.path.dirname(__file__)

def export(p):
    """Call C++ export with positional args."""
    return cpp_exporter.export_top_shell_filleted_step(
        os.path.join(out_dir, p['file']),
        p['width'], p['depth'], p['outer_height'],
        p['top_thickness'], p['wall_thickness'], p['corner_radius'],
        p['outer_fillet_radius'], p['inner_fillet_radius'],
        p['top_recess'], p['top_offset_y'],
        p['window_len'], p['window_wid'],
        "AP242DIS", "MILLIMETER", 1)

base = {
    'file': 'test_params_1.step',
    'width': 100.0, 'depth': 70.0, 'outer_height': 10.0,
    'top_thickness': 2.0, 'wall_thickness': 2.0, 'corner_radius': 20.0,
    'outer_fillet_radius': 1.5, 'inner_fillet_radius': 0.75,
    'top_recess': 11.5, 'top_offset_y': 3.0,
    'window_len': 0.0, 'window_wid': 0.0,
}

# Test 1: baseline
print("Test 1: Baseline...")
print(f"  Result: {export(base)}")

# Test 2: outer_fillet=2.92
print("\nTest 2: outer_fillet=2.92...")
p2 = dict(base); p2['file'] = 'test_params_2.step'; p2['outer_fillet_radius'] = 2.92
print(f"  Result: {export(p2)}")

# Test 3: wall_thickness=2.74
print("\nTest 3: wall_thickness=2.74...")
p3 = dict(base); p3['file'] = 'test_params_3.step'; p3['wall_thickness'] = 2.74
print(f"  Result: {export(p3)}")

# Test 4: top_thickness=1.5
print("\nTest 4: top_thickness=1.5...")
p4 = dict(base); p4['file'] = 'test_params_4.step'; p4['top_thickness'] = 1.5
print(f"  Result: {export(p4)}")

# Test 5: all detected params
print("\nTest 5: All detected params...")
p5 = dict(base); p5['file'] = 'test_params_5.step'
p5.update({'outer_fillet_radius': 2.92, 'wall_thickness': 2.74, 'top_thickness': 1.5,
           'inner_fillet_radius': 1.0, 'top_offset_y': -3.0})
print(f"  Result: {export(p5)}")

# Test 6: top_offset_y=-3.0 only
print("\nTest 6: top_offset_y=-3.0...")
p6 = dict(base); p6['file'] = 'test_params_6.step'; p6['top_offset_y'] = -3.0
print(f"  Result: {export(p6)}")

print("\nAll tests done.")