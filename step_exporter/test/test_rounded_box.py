import sys
import os
import traceback

log_file = open(r'F:\git\blender2step\step_exporter\test_output.log', 'w', encoding='utf-8')

def log(msg):
    log_file.write(msg + '\n')
    log_file.flush()

log("Starting test...")

try:
    sys.path.insert(0, r'F:\git\blender2step\step_exporter')
    sys.path.insert(0, r'F:\git\blender2step\step_exporter\lib')
    os.environ['PATH'] = r'F:\git\blender2step\step_exporter\lib' + os.pathsep + os.environ.get('PATH', '')
    
    if hasattr(os, 'add_dll_directory'):
        os.add_dll_directory(r'F:\git\blender2step\step_exporter\lib')
        log("Added DLL directory")
    
    log("Importing _step_exporter...")
    import _step_exporter as cpp_exporter
    log(f"Imported successfully, version: {cpp_exporter.get_version()}")
    
    log(f"Available functions: {[x for x in dir(cpp_exporter) if not x.startswith('_')]}")
    
    output_path = r'F:\git\blender2step\step_exporter\test42.step'
    log(f"Calling export_rounded_box_step with output: {output_path}")
    
    result = cpp_exporter.export_rounded_box_step(
        output_path,
        100.0,   # width
        70.0,    # depth
        10.0,    # outer_height
        2.0,     # bottom_thickness
        2.0,     # wall_thickness
        20.0,    # corner_radius
    )
    
    log(f"Export result: {result}")

except Exception as e:
    log(f"ERROR: {e}")
    traceback.print_exc(file=log_file)

log_file.close()