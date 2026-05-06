"""
逐个导出并校验每个圆柱体的 STEP 导出
"""
import bpy
import sys
import os
import json

sys.path.insert(0, r"F:\git\blender2step\step_exporter")

bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)

exec(open(r"F:\git\blender2step\step_exporter\test\create_mesh_cylinder.py").read())

import _step_exporter as cpp_exporter

scale = 1000.0

all_objects = [obj for obj in bpy.context.scene.objects if obj.type == 'MESH']
print(f"\nTotal objects: {len(all_objects)}")
for obj in all_objects:
    print(f"  - {obj.name}")

def export_single_object(obj, output_path):
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

    def log_callback(msg):
        print(f"  [C++] {msg}")

    success = cpp_exporter.init_incremental_export(
        output_path, 1, scale,
        1, 1, 1,
        'AP214DIS', 'MILLIMETER',
        1, 0.001,
        log_callback
    )

    if not success:
        print(f"  FAILED to init export")
        return False

    ok = cpp_exporter.add_object_to_export(obj_data, None)
    cpp_exporter.finalize_incremental_export()

    if ok:
        size = os.path.getsize(output_path)
        print(f"  EXPORTED: {size} bytes")

        with open(output_path, 'r') as f:
            content = f.read()
        toroidal = content.count('TOROIDAL_SURFACE')
        conical = content.count('CONICAL_SURFACE')
        cylindrical = content.count('CYLINDRICAL_SURFACE')
        plane = content.count('PLANE')
        print(f"  Surfaces: TOROIDAL={toroidal}, CONICAL={conical}, CYLINDRICAL={cylindrical}, PLANE={plane}")
    else:
        print(f"  FAILED to add object")

    return ok

output_dir = r"F:\git\blender2step\step_exporter\test\single_exports"
os.makedirs(output_dir, exist_ok=True)

for obj in all_objects:
    print(f"\n{'='*60}")
    print(f"Exporting: {obj.name}")
    print(f"  Location: {obj.location}")
    print(f"  Custom props: {dict(obj.items()) if obj.items() else 'none'}")
    output_path = os.path.join(output_dir, f"{obj.name}.step")
    export_single_object(obj, output_path)

print(f"\n{'='*60}")
print("All exports complete!")
