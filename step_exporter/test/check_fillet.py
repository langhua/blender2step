import bpy
import os
import sys

# Add the step_exporter test directory to the path
test_dir = r"F:\git\blender2step\step_exporter\test"
sys.path.insert(0, test_dir)

# Import the test functions
from create_mesh_cylinder import create_fillet_cylinder

# Clear existing objects
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete()

# Create the two fillet cylinders
print("Creating Cylinder_Fillet_Top...")
obj1 = create_fillet_cylinder(
    "Cylinder_Fillet_Top",
    [-120, -80, 0],
    25, 60, 6,  # 半径 25，高度 60，圆角半径 6
    segments=64
)

print("Creating Cylinder_Fillet_Small...")
obj2 = create_fillet_cylinder(
    "Cylinder_Fillet_Small",
    [-60, -80, 0],
    15, 40, 3,  # 半径 15，高度 40，圆角半径 3
    segments=64
)

print(f"Created {len(bpy.context.selected_objects)} objects")
for obj in bpy.context.scene.objects:
    if obj.type == 'MESH':
        print(f"  - {obj.name}: vertices={len(obj.data.vertices)}, edges={len(obj.data.edges)}, faces={len(obj.data.polygons)}")
