"""
分析STEP文件中的物体数量和位置
"""
import sys
import os

freecad_bin = r"F:\Program Files\FreeCAD 1.0\bin"
if freecad_bin not in sys.path:
    sys.path.insert(0, freecad_bin)

os.environ['PATH'] = freecad_bin + os.pathsep + os.environ.get('PATH', '')

import FreeCAD
import Import

step_file = r"F:\git\blender2step\step_exporter\testprogress_ui.step"

print(f"Analyzing: {step_file}")
print(f"File size: {os.path.getsize(step_file)} bytes")

doc = FreeCAD.newDocument("Analysis")
Import.insert(step_file, doc.Name)
doc.recompute()

objects = doc.Objects
print(f"\nFound {len(objects)} objects:")
print("=" * 80)

for i, obj in enumerate(objects, 1):
    print(f"\nObject {i}: {obj.Name}")
    print(f"  TypeId: {obj.TypeId}")
    
    if hasattr(obj, 'Shape'):
        shape = obj.Shape
        print(f"  Shape Type: {shape.ShapeType}")
        print(f"  Faces: {len(shape.Faces)}")
        print(f"  Edges: {len(shape.Edges)}")
        print(f"  Vertices: {len(shape.Vertexes)}")
        
        if shape.Volume > 0:
            print(f"  Volume: {shape.Volume:.2f}")
        
        bbox = shape.BoundBox
        print(f"  BoundingBox: X[{bbox.XMin:.1f}, {bbox.XMax:.1f}] Y[{bbox.YMin:.1f}, {bbox.YMax:.1f}] Z[{bbox.ZMin:.1f}, {bbox.ZMax:.1f}]")
        print(f"  Size: {bbox.XMax-bbox.XMin:.1f} x {bbox.YMax-bbox.YMin:.1f} x {bbox.ZMax-bbox.ZMin:.1f}")

print("\n" + "=" * 80)
if len(objects) == 2:
    b1 = objects[0].Shape.BoundBox
    b2 = objects[1].Shape.BoundBox
    print(f"Object 1 center: X={(b1.XMin+b1.XMax)/2:.1f}, Y={(b1.YMin+b1.YMax)/2:.1f}")
    print(f"Object 2 center: X={(b2.XMin+b2.XMax)/2:.1f}, Y={(b2.YMin+b2.YMax)/2:.1f}")
    print(f"Distance between centers: {abs((b1.XMin+b1.XMax)/2 - (b2.XMin+b2.XMax)/2):.1f}")
    if abs((b1.XMin+b1.XMax)/2 - (b2.XMin+b2.XMax)/2) > 50:
        print("✅ Objects are SEPARATED correctly")
    else:
        print("❌ Objects may be OVERLAPPING")

FreeCAD.closeDocument(doc.Name)
