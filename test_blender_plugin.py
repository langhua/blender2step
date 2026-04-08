#!/usr/bin/env python3
"""
Test script to verify Blender plugin import
"""

import sys
import os

# Add the step_exporter directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "step_exporter"))

print("Testing Blender plugin import...")
print(f"Python version: {sys.version}")

# Try to import the plugin module
try:
    import step_exporter
    print("Successfully imported step_exporter module")
    
    # Check if the plugin has the required attributes
    if hasattr(step_exporter, 'bl_info'):
        print(f"Plugin info: {step_exporter.bl_info}")
    else:
        print("Plugin missing bl_info")
    
    # Check if C++ module is loaded
    if hasattr(step_exporter, 'CPP_MODULE_LOADED'):
        print(f"C++ module loaded: {step_exporter.CPP_MODULE_LOADED}")
        if step_exporter.CPP_MODULE_LOADED:
            print("✓ C++ module is successfully loaded")
        else:
            print("✗ C++ module failed to load")
            if hasattr(step_exporter, 'MODULE_LOAD_ERROR'):
                print(f"Error: {step_exporter.MODULE_LOAD_ERROR}")
    else:
        print("Plugin missing CPP_MODULE_LOADED attribute")
        
except ImportError as e:
    print(f"Import error: {e}")
    import traceback
    traceback.print_exc()
except Exception as e:
    print(f"Unexpected error: {e}")
    import traceback
    traceback.print_exc()

print("Test completed.")
