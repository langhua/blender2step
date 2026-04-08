#!/usr/bin/env python3
"""
Test script to verify C++ extension module import
"""

import sys
import os

# Add the step_exporter/lib directory to Python path
lib_path = os.path.join(os.path.dirname(__file__), "step_exporter", "lib")
sys.path.insert(0, lib_path)

# Add lib path to system PATH for DLL loading
os.environ["PATH"] = lib_path + ";" + os.environ.get("PATH", "")

print("Testing C++ module import...")
print(f"Python version: {sys.version}")
print(f"Current directory: {os.getcwd()}")
print(f"Python path: {sys.path[:5]}...")  # Show first 5 paths
print(f"Lib path: {lib_path}")
print(f"Lib directory exists: {os.path.exists(lib_path)}")
print(f"_step_exporter.pyd exists: {os.path.exists(os.path.join(lib_path, '_step_exporter.pyd'))}")

# Try to import the module
try:
    import _step_exporter
    print("Successfully imported _step_exporter module")
    
    # Test module functionality
    if hasattr(_step_exporter, 'get_version'):
        version = _step_exporter.get_version()
        print(f"Module version: {version}")
    else:
        print("Module missing get_version function")
        
except ImportError as e:
    print(f"Import error: {e}")
    import traceback
    traceback.print_exc()
except Exception as e:
    print(f"Unexpected error: {e}")
    import traceback
    traceback.print_exc()

print("Test completed.")
