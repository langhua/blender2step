import bpy
import sys
import os
import json

sys.path.insert(0, r"F:\git\blender2step\step_exporter")

bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)

exec(open(r"F:\git\blender2step\step_exporter\test\create_mesh_cylinder.py", encoding="utf-8").read())

import _step_exporter as cpp_exporter

scale = 1000.0

all_objects = [obj for obj in bpy.context.scene.objects if obj.type == 'MESH']

output_dir = r"F:\git\blender2step\step_exporter\test\single_exports"
os.makedirs(output_dir, exist_ok=True)

results = []

for obj in all_objects:
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

    output_path = os.path.join(output_dir, f"{obj.name}.step")

    def log_callback(msg):
        pass

    success = cpp_exporter.init_incremental_export(
        output_path, 1, scale,
        1, 1, 1,
        'AP214DIS', 'MILLIMETER',
        1, 0.001,
        log_callback
    )

    if not success:
        results.append((obj.name, False, 0, 0, 0, 0, 0, "INIT_FAILED"))
        continue

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
        results.append((obj.name, True, size, toroidal, conical, cylindrical, plane, "OK"))
    else:
        results.append((obj.name, False, 0, 0, 0, 0, 0, "ADD_FAILED"))

with open(os.path.join(output_dir, "summary.txt"), "w") as f:
    f.write(f"{'Name':<45} {'Status':<12} {'Size':>10} {'TOR':>5} {'CON':>5} {'CYL':>5} {'PLANE':>6}\n")
    f.write("-" * 95 + "\n")
    for name, ok, size, tor, con, cyl, plane, status in results:
        f.write(f"{name:<45} {status:<12} {size:>10} {tor:>5} {con:>5} {cyl:>5} {plane:>6}\n")

print("Summary written to summary.txt")
