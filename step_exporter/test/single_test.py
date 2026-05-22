"""Test: export only the NoHoles mesh with fix_geometry=0 create_solid=0"""
import bpy
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import _step_exporter as cpp_exporter

# Create the bottom shells using the same code as run_test.py
# We'll run the script up to creating the objects, then export separately
test_dir = os.path.dirname(os.path.abspath(__file__))
run_test_path = os.path.join(test_dir, 'run_test.py')

# Read and execute the part that creates the bottom shells
with open(run_test_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Find the split point: "Step 1: Exporting STEP file"
split_point = content.find("Step 1: Exporting STEP file")
setup_code = content[:split_point]

# Execute setup
exec(setup_code)

# Now export only one object with minimal settings
for obj in bpy.data.objects:
    if 'NoHoles' in obj.name:
        print(f"\nExporting: {obj.name}", flush=True)
        mesh = obj.data
        vertices = [[v.co.x, v.co.y, v.co.z] for v in mesh.vertices]
        faces = [list(p.vertices) for p in mesh.polygons]
        
        print(f"Vertices: {len(vertices)}, Faces: {len(faces)}", flush=True)
        
        obj_data = {
            'name': obj.name,
            'type': 'MESH',
            'vertices': vertices,
            'faces': faces,
        }
        
        step_path = os.path.join(test_dir, 'test_single.step')
        
        def log_cb(msg):
            pass
        
        print("Init...", flush=True)
        ok = cpp_exporter.init_incremental_export(step_path, 1, 1000.0, 0, 0, 1, 'AP214DIS', 'MILLIMETER', 0, 0.001, log_cb)
        print(f"Init: {ok}", flush=True)
        
        print("Add object...", flush=True)
        result = cpp_exporter.add_object_to_export(obj_data, lambda p: None)
        print(f"Add object: {result}", flush=True)
        
        print("Finalize...", flush=True)
        result = cpp_exporter.finalize_incremental_export()
        print(f"Finalize: {result}", flush=True)
        
        print(f"File exists: {os.path.exists(step_path)}", flush=True)
        if os.path.exists(step_path):
            print(f"File size: {os.path.getsize(step_path)}", flush=True)
        break