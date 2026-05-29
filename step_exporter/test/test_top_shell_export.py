"""Test: create top shells and export to STEP."""
import bpy
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'test'))

from create_top_shell import create_top_shell_scene

print("=== Creating top shells ===")
create_top_shell_scene()

print("\n=== Exporting to STEP ===")
out_file = os.path.join(os.path.dirname(__file__), 'test28.step')
bpy.ops.export_scene.step_enhanced(
    filepath=out_file,
    use_selected=False,
    apply_modifiers=True,
    unit='mm',
    step_schema='AP242DIS',
    enable_logging=True
)
print(f"=== Done: {out_file} ===")