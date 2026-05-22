"""Simple test: export mesh to STEP with incremental API"""
import bpy
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import _step_exporter as cpp_exporter

# Create a simple cube mesh
bpy.ops.mesh.primitive_cube_add(size=2, location=(0, 0, 0))
obj = bpy.context.active_object
obj.name = "TestCube"

# Get mesh data
mesh = obj.data
vertices = [[v.co.x, v.co.y, v.co.z] for v in mesh.vertices]
faces = [list(p.vertices) for p in mesh.polygons]

obj_data = {
    'name': obj.name,
    'vertices': vertices,
    'faces': faces
}

step_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'test_cube.step')

print("=== Init ===", flush=True)
success = cpp_exporter.init_incremental_export(
    step_path,
    [obj_data],
    1000.0,
    True,   # fix_geometry
    True,   # create_solid
    True,   # advanced_brep
    0,      # schema
    2,      # unit (MM)
    0.001,  # sewing_tolerance
    True,   # enable_logging
)
print(f"init = {success}", flush=True)

print("=== Add object ===", flush=True)
def progress_cb(pct):
    pass

try:
    success = cpp_exporter.add_object_to_export(obj_data, progress_cb)
    print(f"add_object = {success}", flush=True)
except Exception as e:
    print(f"ERROR in add_object: {e}", flush=True)
    import traceback
    traceback.print_exc()

print("=== Finalize ===", flush=True)
try:
    success = cpp_exporter.finalize_incremental_export()
    print(f"finalize = {success}", flush=True)
except Exception as e:
    print(f"ERROR in finalize: {e}", flush=True)
    import traceback
    traceback.print_exc()

print("=== Done ===", flush=True)
print(f"File exists: {os.path.exists(step_path)}", flush=True)
print(f"File size: {os.path.getsize(step_path) if os.path.exists(step_path) else 0}", flush=True)