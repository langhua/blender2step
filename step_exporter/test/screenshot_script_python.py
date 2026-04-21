"""
FreeCAD截图脚本 - 纯Python模式
用法: python screenshot_script_python.py <step_file> <output_image> [width] [height]
"""

import sys
import os

# 添加FreeCAD的Python模块路径
freecad_bin = r"F:\Program Files\FreeCAD 1.0\bin"
freecad_lib = r"F:\Program Files\FreeCAD 1.0\lib"
freecad_ext = r"F:\Program Files\FreeCAD 1.0\Ext"

# 设置环境变量
os.environ['PATH'] = freecad_bin + os.pathsep + os.environ.get('PATH', '')
os.environ['PYTHONPATH'] = freecad_lib + os.pathsep + freecad_ext + os.pathsep + os.environ.get('PYTHONPATH', '')

# 添加路径
sys.path.insert(0, freecad_lib)
sys.path.insert(0, freecad_ext)

def main():
    if len(sys.argv) < 3:
        print("用法: python screenshot_script_python.py <step_file> <output_image> [width] [height]")
        sys.exit(1)
    
    step_file = sys.argv[1]
    output_image = sys.argv[2]
    width = int(sys.argv[3]) if len(sys.argv) > 3 else 1920
    height = int(sys.argv[4]) if len(sys.argv) > 4 else 1080
    
    print(f"Opening STEP file: {step_file}")
    print(f"Output image: {output_image}")
    
    try:
        import FreeCAD
        import FreeCADGui
        import Import
        
        # 设置FreeCAD为无头模式
        FreeCADGui.showMainWindow()
        
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
        view = FreeCADGui.ActiveDocument.ActiveView
        view.viewAxonometric()
        view.fitAll()
        
        # 等待渲染完成
        import time
        time.sleep(2)
        
        view.saveImage(output_image, width, height, "White")
        print(f"SUCCESS: Screenshot saved to {output_image}")
        
        FreeCAD.closeDocument(doc.Name)
        print("Done!")
        
    except Exception as e:
        print(f"ERROR: Screenshot failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
