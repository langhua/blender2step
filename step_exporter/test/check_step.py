import sys
sys.path.insert(0, r'F:\Program Files\FreeCAD 1.0\bin')
sys.path.insert(0, r'F:\Program Files\FreeCAD 1.0\lib')

import FreeCAD
import Part

shape = Part.Shape()
shape.read('F:/git/blender2step/step_exporter/test/bottom_shell_filleted.step')

print('Shape valid:', shape.isValid())
print('Shape type:', shape.ShapeType)
print('Faces:', len(shape.Faces))
print('Edges:', len(shape.Edges))
print('Volume:', shape.Volume)
bb = shape.BoundBox
print('BoundBox: X[%.3f, %.3f] Y[%.3f, %.3f] Z[%.3f, %.3f]' % (bb.XMin, bb.XMax, bb.YMin, bb.YMax, bb.ZMin, bb.ZMax))

# Check step structure
z_values = set()
for v in shape.Vertexes:
    z = round(v.Point.z, 3)
    z_values.add(z)
print('Unique Z levels:', sorted(z_values))

z4_faces = [f for f in shape.Faces if abs(f.BoundBox.ZMin - 4.0) < 0.1 and abs(f.BoundBox.ZMax - 4.0) < 0.1]
z5_faces = [f for f in shape.Faces if abs(f.BoundBox.ZMin - 5.0) < 0.1 and abs(f.BoundBox.ZMax - 5.0) < 0.1]
print(f'Horizontal faces at z=4.0 (step 1): {len(z4_faces)}, area={sum(f.Area for f in z4_faces):.1f}')
print(f'Horizontal faces at z=5.0 (step 2): {len(z5_faces)}, area={sum(f.Area for f in z5_faces):.1f}')

if shape.isValid():
    print('Shape is valid!')
else:
    print('Shape is invalid!')