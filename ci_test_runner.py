"""
CI test runner — run pytest inside Blender so bpy, bmesh, etc. are available.
Usage: blender --background --python ci_test_runner.py
"""
import bpy
import sys
import os
import subprocess

print(f"Blender {bpy.app.version_string} | Python {sys.version}")

# Install pytest
subprocess.run([sys.executable, "-m", "pip", "install", "pytest"], check=True)

# Run tests
os.chdir(os.path.dirname(os.path.abspath(__file__)))
sys.exit(subprocess.run(
    [sys.executable, "-m", "pytest", "step_exporter/tests/test_core_utils.py", "-v"]
).returncode)

