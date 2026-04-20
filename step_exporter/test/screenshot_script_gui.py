"""
FreeCAD截图脚本 - 使用GUI模式
用法: FreeCAD screenshot_script_gui.py -- <step_file> <output_image> [width] [height]
"""

import sys
import os

def main():
    args = sys.argv
    if '--' in args:
        idx = args.index('--')
        args = args[idx + 1:]
    
    # 优先从环境变量读取参数（支持run_test.py调用方式）
    step_file = os.environ.get('STEP_FILE')
    output_image = os.environ.get('OUTPUT_IMAGE')
    width = int(os.environ.get('IMAGE_WIDTH', '1920'))
    height = int(os.environ.get('IMAGE_HEIGHT', '1080'))
    
    # 如果环境变量没有设置，尝试从命令行参数读取
    if not step_file and len(args) >= 1:
        step_file = args[0]
    if not output_image and len(args) >= 2:
        output_image = args[1]
    if len(args) >= 3:
        width = int(args[2])
    if len(args) >= 4:
        height = int(args[3])
    
    if not step_file or not output_image:
        print("用法: FreeCAD screenshot_script_gui.py -- <step_file> <output_image> [width] [height]")
        print("或通过环境变量: STEP_FILE, OUTPUT_IMAGE, IMAGE_WIDTH, IMAGE_HEIGHT")
        sys.exit(1)
    
    print(f"Opening STEP file: {step_file}")
    
    import FreeCAD
    import FreeCADGui
    import Import
    
    doc = FreeCAD.newDocument("Screenshot")
    Import.insert(step_file, doc.Name)
    doc.recompute()
    
    objects = doc.Objects
    print(f"Found {len(objects)} objects")
    
    # 确保输出目录存在
    output_dir = os.path.dirname(output_image)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir, exist_ok=True)
    
    # 使用FreeCADGui截图
    try:
        view = FreeCADGui.ActiveDocument.ActiveView
        view.viewAxonometric()
        view.fitAll()
        
        # 等待渲染完成
        import time
        time.sleep(1)
        
        view.saveImage(output_image, width, height, "White")
        print(f"SUCCESS: Screenshot saved to {output_image}")
    except Exception as e:
        print(f"ERROR: Screenshot failed: {e}")
        import traceback
        traceback.print_exc()
    
    FreeCAD.closeDocument(doc.Name)
    print("Done!")

if __name__ == "__main__":
    main()
