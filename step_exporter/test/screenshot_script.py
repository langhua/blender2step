"""
FreeCAD截图脚本 - 简化无头模式
用法: FreeCAD --console screenshot_script.py -- <step_file> <output_image> [width] [height]
"""

import sys
import os

def main():
    args = sys.argv
    if '--' in args:
        idx = args.index('--')
        args = args[idx + 1:]
    
    if len(args) < 2:
        print("用法: FreeCAD --console screenshot_script.py -- <step_file> <output_image> [width] [height]")
        sys.exit(1)
    
    step_file = args[0]
    output_image = args[1]
    width = int(args[2]) if len(args) > 2 else 1920
    height = int(args[3]) if len(args) > 3 else 1080
    
    print(f"Opening STEP file: {step_file}")
    
    import FreeCAD
    import Import
    
    doc = FreeCAD.newDocument("Screenshot")
    Import.insert(step_file, doc.Name)
    doc.recompute()
    
    objects = doc.Objects
    print(f"Found {len(objects)} objects")
    
    for i, obj in enumerate(objects):
        if hasattr(obj, 'Shape') and not obj.Shape.isNull():
            shape = obj.Shape
            print(f"  Object {i}: {obj.Name}")
            print(f"    Type: {shape.ShapeType}")
            print(f"    Faces: {len(shape.Faces)}")
            for j, face in enumerate(shape.Faces):
                print(f"      Face {j}: {face.SurfaceType}")
    
    # 确保输出目录存在
    output_dir = os.path.dirname(output_image)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir, exist_ok=True)
    
    # 尝试使用FreeCADGui截图
    try:
        import FreeCADGui
        view = FreeCADGui.ActiveDocument.ActiveView
        view.viewAxonometric()
        view.fitAll()
        view.saveImage(output_image, width, height, "White")
        print(f"SUCCESS: Screenshot saved to {output_image}")
    except Exception as e:
        print(f"WARNING: GUI screenshot failed: {e}")
        # 创建占位符
        with open(output_image, 'wb') as f:
            f.write(b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82')
        print(f"Created placeholder: {output_image}")
    
    FreeCAD.closeDocument(doc.Name)
    print("Done!")

if __name__ == "__main__":
    main()
