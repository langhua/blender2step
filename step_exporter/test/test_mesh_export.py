"""
Quick test: export bottom shell mesh via incremental exporter (mesh-based path)
"""
import bpy
import sys
import os

script_dir = os.path.dirname(os.path.abspath(__file__))
test_dir = os.path.dirname(script_dir)
lib_dir = os.path.join(test_dir, 'lib')

sys.path.insert(0, test_dir)
sys.path.insert(0, lib_dir)
os.environ['PATH'] = lib_dir + os.pathsep + os.environ.get('PATH', '')
if hasattr(os, 'add_dll_directory'):
    os.add_dll_directory(lib_dir)

# Load create_bottom_shell.py
create_script = os.path.join(script_dir, 'create_bottom_shell.py')
with open(create_script, 'r', encoding='utf-8') as f:
    code = f.read()
script_globals = {'__name__': '__main__', '__file__': create_script}
exec(compile(code, create_script, 'exec'), script_globals)

# Create the bottom shell mesh
print("Creating bottom shell...")
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete()
script_globals['create_filleted_bottom_shells_scene']()

import _step_exporter as cpp_exporter

output_path = os.path.join(test_dir, 'test28_mesh.step')
log_path = output_path + '.log'

log_file = open(log_path, 'w', encoding='utf-8')
def log_callback(msg):
    print(f'[LOG] {msg}')
    log_file.write(msg + '\n')
    log_file.flush()

scale = 1000.0

# Collect mesh objects
objects_data = []
for obj in bpy.context.scene.objects:
    if obj.type != 'MESH':
        continue
    depsgraph = bpy.context.evaluated_depsgraph_get()
    eval_obj = obj.evaluated_get(depsgraph)
    mesh = eval_obj.data
    
    vertices = []
    for vert in mesh.vertices:
        world_co = eval_obj.matrix_world @ vert.co
        vertices.append([float(world_co.x) * scale, float(world_co.y) * scale, float(world_co.z) * scale])
    
    mesh.calc_loop_triangles()
    faces = []
    normals = []
    for tri in mesh.loop_triangles:
        faces.append(list(tri.vertices))
        normals.append([float(tri.normal.x), float(tri.normal.y), float(tri.normal.z)])
    
    objects_data.append({
        'name': obj.name,
        'type': 'mesh',
        'vertices': vertices,
        'faces': faces,
        'normals': normals,
        'matrix_world': list(eval_obj.matrix_world),
    })
    print(f'  {obj.name}: {len(vertices)} verts, {len(faces)} faces')

print(f'Exporting {len(objects_data)} objects to {output_path}')

# Initialize incremental export
cpp_exporter.init_incremental_export(
    output_path,
    len(objects_data),
    scale,
    1,  # fix_geometry
    1,  # create_solid
    1,  # advanced_brep
    'AP214IS',
    'MILLIMETER',
    1,  # enable_logging
    0.001,  # sew_tolerance
    log_callback
)

# Add objects
for obj_data in objects_data:
    cpp_exporter.add_object_to_export(obj_data, lambda p: None)

# Finalize
success = cpp_exporter.finalize_incremental_export()
log_file.close()

if success:
    size = os.path.getsize(output_path)
    print(f'SUCCESS: {output_path} ({size} bytes)')
else:
    print('FAILED')
    sys.exit(1)