import bpy
import sys
import os

# Import the C++ extension module
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lib'))
import _step_exporter as cpp_exporter

step_file = os.path.join(os.path.dirname(__file__), 'bottom_shell_filleted.step')

# Use the C++ module to read and validate the STEP file
print(f"Validating STEP file: {step_file}")
print(f"File size: {os.path.getsize(step_file)} bytes")

# Check if the file can be read by OpenCASCADE
# We'll use a simple approach: try to import it back
result = cpp_exporter.validate_step_file(step_file)
print(f"Validation result: {result}")
