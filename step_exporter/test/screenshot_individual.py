"""
使用FreeCAD GUI模式截图 - 逐个对象截图
用法: FreeCAD screenshot_individual.py -- <step_file> <output_dir>
"""

import sys
import os

def main():
    args = sys.argv
    if '--' in args:
        idx = args.index('--')
        args = args[idx + 1:]
    
    if len(args) < 2:
        print("用法: FreeCAD screenshot_individual.py -- <step_file> <output_dir>")
        sys.exit(1)
    
    step_file = args[0]
    output_dir = args[1]
    
    # 确保输出目录存在
    if not os.path.exists(output_dir):
        os.makedirs(output_dir, exist_ok=True)
    
    # 验证输出目录
    if not os.path.isdir(output_dir):
        print(f"错误: {output_dir} 不是有效的目录")
        sys.exit(1)
    
    # 转换为绝对路径
    output_dir = os.path.abspath(output_dir)
    
    print(f"Opening STEP file: {step_file}")
    print(f"Output directory: {output_dir}")
    
    import FreeCAD
    import FreeCADGui
    import Import
    import time
    
    doc = FreeCAD.newDocument("Screenshot")
    Import.insert(step_file, doc.Name)
    doc.recompute()
    
    objects = doc.Objects
    print(f"Found {len(objects)} objects")
    
    # 等待加载完成
    time.sleep(2)
    
    for i, obj in enumerate(objects):
        print(f"Processing object {i+1}/{len(objects)}: {obj.Name}")
        
        # 隐藏所有对象
        for o in objects:
            o.ViewObject.Visibility = False
        
        # 只显示当前对象
        obj.ViewObject.Visibility = True
        
        # 等待渲染
        time.sleep(0.5)
        
        # 截图
        view = FreeCADGui.ActiveDocument.ActiveView
        view.viewAxonometric()
        view.fitAll()
        time.sleep(0.5)
        
        # 构建完整的文件路径 - 使用正斜杠，确保路径格式正确
        output_filename = f"obj_{i+1}_{obj.Name}.png"
        output_image = output_dir + "/" + output_filename
        
        # 转换为正斜杠格式（FreeCAD在Windows上也能处理）
        output_image = output_image.replace("\\", "/")
        
        print(f"  Saving to: {output_image}")
        
        try:
            view.saveImage(output_image, 1920, 1080, "White")
            # 验证文件是否创建成功
            if os.path.exists(output_image):
                print(f"  SUCCESS: {output_image}")
            else:
                print(f"  WARNING: File not created at {output_image}")
        except Exception as e:
            print(f"  ERROR: {e}")
            import traceback
            traceback.print_exc()
    
    # 显示所有对象
    for o in objects:
        o.ViewObject.Visibility = True
    
    view.fitAll()
    time.sleep(0.5)
    
    # 截图所有对象
    output_filename = "all_objects.png"
    output_image = output_dir + "/" + output_filename
    output_image = output_image.replace("\\", "/")
    
    print(f"Saving all objects to: {output_image}")
    
    try:
        view.saveImage(output_image, 1920, 1080, "White")
        if os.path.exists(output_image):
            print(f"SUCCESS: All objects screenshot saved to {output_image}")
        else:
            print(f"WARNING: File not created at {output_image}")
    except Exception as e:
        print(f"ERROR: All objects screenshot failed: {e}")
        import traceback
        traceback.print_exc()
    
    FreeCAD.closeDocument(doc.Name)
    print("Done!")

if __name__ == "__main__":
    main()
