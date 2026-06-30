"""
CI test runner — run pytest inside Blender so bpy, bmesh, etc. are available.
Usage: blender --background --python ci_test_runner.py
"""
import bpy
import bmesh  # force-load before step_exporter imports
import sys
import os
import subprocess

print(f"Blender {bpy.app.version_string} | Python {sys.version}")
print(f"bmesh loaded: {bmesh.__name__}")

# Install pytest
subprocess.run([sys.executable, "-m", "pip", "install", "pytest", "-q"], check=True)

# Run tests
os.chdir(os.path.dirname(os.path.abspath(__file__)))
sys.exit(subprocess.run(
    [sys.executable, "-m", "pytest", "step_exporter/tests/test_core_utils.py", "-v"]
).returncode)

