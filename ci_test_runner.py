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
import pytest
os.chdir(os.path.dirname(os.path.abspath(__file__)))
sys.exit(pytest.main(["step_exporter/tests/test_core_utils.py", "-v"]))


