"""
FreeCAD截图脚本 - 使用GUI模式运行
用法: FreeCAD --console screenshot_script.py -- <step_file> <output_image> [width] [height]

示例:
  FreeCAD --console screenshot_script.py -- test28.step test28.png 1920 1080
"""

import sys
import os

def main():
    # 解析命令行参数
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
    
    # 导入FreeCAD模块
    import FreeCAD
    import FreeCADGui
    import Import
    
    # 创建新文档
    doc = FreeCAD.newDocument("Screenshot")
    
    # 导入STEP文件
    Import.insert(step_file, doc.Name)
    
    # 重新计算
    doc.recompute()
    
    # 获取视图
    view = FreeCADGui.ActiveDocument.ActiveView
    
    # 设置为等轴测视图
    view.viewAxonometric()
    
    # 设置为正交相机
    FreeCADGui.SendMsgToActiveView("OrthographicCamera")
    
    # 适应视图
    view.fitAll()
    
    # 确保输出目录存在
    output_dir = os.path.dirname(output_image)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir, exist_ok=True)
    
    # 保存截图
    print(f"Saving screenshot to: {output_image} ({width}x{height})")
    view.saveImage(output_image, width, height, "White")
    
    print("Screenshot saved successfully!")
    
    # 关闭文档
    FreeCAD.closeDocument(doc.Name)
    
    # 退出FreeCAD
    FreeCADGui.getMainWindow().close()

if __name__ == "__main__":
    main()
