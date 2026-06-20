"""Verify _step_exporter.pyd build and merge_step_files function"""
import sys
sys.path.insert(0, 'f:/git/blender2step/step_exporter/lib')
try:
    import _step_exporter as cpp
    print(f"Module loaded OK")
    print(f"Version: {cpp.get_version()}")
    print(f"OCCT: {cpp.get_occt_version()}")
    
    # Check if merge_step_files exists
    if hasattr(cpp, 'merge_step_files'):
        print("merge_step_files: FOUND")
    else:
        print("merge_step_files: MISSING - build may have failed!")
except Exception as e:
    print(f"ERROR loading module: {e}")
    import traceback
    traceback.print_exc()
