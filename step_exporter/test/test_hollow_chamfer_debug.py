"""
单独测试 Cylinder_Tapered_Hollow_Chamfer
"""
import bpy
import sys
import os

sys.path.insert(0, r"F:\git\blender2step\step_exporter")

bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)

exec(open(r"F:\git\blender2step\step_exporter\test\create_mesh_cylinder.py").read())

import _step_exporter as cpp_exporter

scale = 1000.0

obj = bpy.data.objects.get("Cylinder_Tapered_Hollow_Chamfer")
if not obj:
    print("ERROR: Object not found!")
    sys.exit(1)

print(f"Object: {obj.name}")
print(f"Location: {obj.location}")

depsgraph = bpy.context.evaluated_depsgraph_get()
eval_obj = obj.evaluated_get(depsgraph)
mesh = eval_obj.data

vertices = []
for vert in mesh.vertices:
    world_co = eval_obj.matrix_world @ vert.co
    vertices.append([float(world_co.x) * scale, float(world_co.y) * scale, float(world_co.z) * scale])

mesh.calc_loop_triangles()
faces = []
for tri in mesh.loop_triangles:
    faces.append(list(tri.vertices))

normals = []
for tri in mesh.loop_triangles:
    normals.append([float(tri.normal.x), float(tri.normal.y), float(tri.normal.z)])

obj_data = {
    'name': obj.name,
    'type': 'mesh',
    'vertices': vertices,
    'faces': faces,
    'normals': normals,
    'matrix_world': list(eval_obj.matrix_world),
}

output_path = os.path.join(os.path.dirname(__file__), "test_hollow_chamfer.step")

def log_callback(msg):
    if msg:
        print(f"  [C++] {msg}")

success = cpp_exporter.init_incremental_export(
    output_path, 1, scale,
    1, 1, 1,
    'AP214DIS', 'MILLIMETER',
    1, 0.001,
    log_callback
)

if not success:
    print("INIT FAILED")
    sys.exit(1)

ok = cpp_exporter.add_object_to_export(obj_data, None)
cpp_exporter.finalize_incremental_export()

if ok:
    size = os.path.getsize(output_path)
    with open(output_path, 'r') as f:
        content = f.read()
    toroidal = content.count('TOROIDAL_SURFACE')
    conical = content.count('CONICAL_SURFACE')
    cylindrical = content.count('CYLINDRICAL_SURFACE')
    plane = content.count('PLANE')
    print(f"EXPORTED: {size} bytes")
    print(f"Surfaces: TOROIDAL={toroidal}, CONICAL={conical}, CYLINDRICAL={cylindrical}, PLANE={plane}")
else:
    print("ADD FAILED")
