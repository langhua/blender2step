import sys
sys.path.insert(0, r'F:\Program Files\FreeCAD 1.0\bin')
import FreeCAD, Import, os

output_dir = r'F:\git\blender2step\step_exporter\test\single_exports'

files = sorted([f for f in os.listdir(output_dir) if f.endswith('.step')])

print(f"{'Name':<40} {'Type':<8} {'Vol':>10} {'Faces':>6} {'Size':>20} {'Surfaces':<50} {'Status'}")
print("=" * 160)

for fname in files:
    fpath = os.path.join(output_dir, fname)
    try:
        doc = FreeCAD.newDocument('Temp')
        Import.insert(fpath, doc.Name)
        doc.recompute()
        
        for obj in doc.Objects:
            shape = obj.Shape
            bbox = shape.BoundBox
            sx = bbox.XMax - bbox.XMin
            sy = bbox.YMax - bbox.YMin
            sz = bbox.ZMax - bbox.ZMin
            
            face_types = {}
            for face in shape.Faces:
                ftype = face.Surface.__class__.__name__
                face_types[ftype] = face_types.get(ftype, 0) + 1
            
            surf_str = ', '.join(f'{k}={v}' for k, v in sorted(face_types.items()))
            
            issues = []
            if shape.ShapeType != 'Solid':
                issues.append(f'NOT_SOLID({shape.ShapeType})')
            if not shape.isClosed():
                issues.append('OPEN')
            if not shape.isValid():
                issues.append('INVALID')
            if shape.Volume <= 0:
                issues.append('ZERO_VOL')
            
            status = 'OK' if not issues else ','.join(issues)
            
            size_str = f'{sx:.1f}x{sy:.1f}x{sz:.1f}'
            print(f"{fname:<40} {shape.ShapeType:<8} {shape.Volume:>10.1f} {len(shape.Faces):>6} {size_str:>20} {surf_str:<50} {status}")
        
        FreeCAD.closeDocument(doc.Name)
    except Exception as e:
        print(f"{fname:<40} {'ERROR':<8} {'-':>10} {'-':>6} {'-':>20} {'-':<50} {str(e)[:50]}")
