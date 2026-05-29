import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lib'))

import bpy
import _step_exporter as cpp

out_file = os.path.join(os.path.dirname(__file__), 'test28_loft.step')

print("=== Exporting loft-based top shell ===")
result = cpp.export_top_shell_filleted_step(
    out_file,
    100.0, 70.0, 10.0,
    1.5, 2.7427, 20.0,
    2.0, 1.2,
    11.5182, -3.0091,
    0.0, 0.0,
    0.0, 0.0, 0.0,
    "AP242DIS", "MILLIMETER", 1
)
print(f"Loft export: {'OK' if result else 'FAILED'}")
print(f"Output: {out_file}")
