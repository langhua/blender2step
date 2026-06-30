"""
CI test runner — run pytest inside Blender so bpy, bmesh, etc. are available.
Usage: blender --background --python ci_test_runner.py
"""
import bpy
import bmesh  # force-load in Blender's main process
import sys
import os
import subprocess

print(f"Blender {bpy.app.version_string} | Python {sys.version}")

# Install pytest
subprocess.run([sys.executable, "-m", "pip", "install", "pytest", "-q"], check=True)

# Run pytest in-process (subprocess would lose bpy/bmesh)
# Skip standalone diagnostic scripts, only run test_*.py files
import pytest
os.chdir(os.path.dirname(os.path.abspath(__file__)))
sys.exit(pytest.main([
    "step_exporter/tests/",
    "-v",
    "--ignore=step_exporter/tests/analyze_step.py",
    "--ignore=step_exporter/tests/analyze_step_detailed.py",
    "--ignore=step_exporter/tests/analyze_positions.py",
    "--ignore=step_exporter/tests/analyze_positions2.py",
    "--ignore=step_exporter/tests/check_coords.py",
    "--ignore=step_exporter/tests/diagnose_cpp_ext.py",
    "--ignore=step_exporter/tests/diagnose_import.py",
    "--ignore=step_exporter/tests/diagnose_step_exporter.py",
    "--ignore=step_exporter/tests/simple_test.py",
    "--ignore=step_exporter/tests/test_vscode_setup.py",
    "--ignore=step_exporter/tests/test_blender_export.py",
    "--ignore=step_exporter/tests/test_fix.py",
    "--ignore=step_exporter/tests/test_fix_terminal.py",
    "--ignore=step_exporter/tests/test_chamfered_cylinder.py",
    "--ignore=step_exporter/tests/test_fillet_cylinder.py",
    "--ignore=step_exporter/tests/test_multiple_tapers.py",
    "--ignore=step_exporter/tests/test_tapered_cylinder.py",
    "--ignore=step_exporter/tests/test_volume_zero.py",
    "--ignore=step_exporter/tests/test_output/",
]))


