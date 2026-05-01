"""
分析STEP文件中的物体数量和类型
"""
import sys
import os

# 使用FreeCAD的Python环境
freecad_bin = r"F:\Program Files\FreeCAD 1.0\bin"
if freecad_bin not in sys.path:
    sys.path.insert(0, freecad_bin)

os.environ['PATH'] = freecad_bin + os.pathsep + os.environ.get('PATH', '')

import FreeCAD
import Import

step_file = r"F:\git\blender2step\step_exporter\test28.step"

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
        
        # 分析面类型
        face_types = {}
        for face in shape.Faces:
            ftype = face.Surface.__class__.__name__
            face_types[ftype] = face_types.get(ftype, 0) + 1
        print(f"  Face types: {face_types}")

FreeCAD.closeDocument(doc.Name)
print("\n" + "=" * 80)
print("Analysis complete")
