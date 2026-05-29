"""Export no-window shell with logging OFF to see C++ console output."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import _step_exporter as cpp

out_dir = os.path.dirname(os.path.abspath(__file__))

result = cpp.export_top_shell_filleted_step(
    os.path.join(out_dir, 'test28_debug.step'),
    100.0, 70.0, 10.0,  # w, d, h
    1.5, 2.7427, 20.0,  # tt, wt, cr
    2.0, 1.2,  # ofr, ifr
    11.5182, -3.0091,  # recess, yOff
    0.0, 0.0,  # no window
    "AP242DIS", "MILLIMETER", 0)  # logging OFF
print(f"Export: {'OK' if result else 'FAILED'}")