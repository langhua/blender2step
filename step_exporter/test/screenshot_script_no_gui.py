"""
FreeCAD无GUI截图脚本 - 使用pivy coin进行离屏渲染
用法: FreeCADCmd -c screenshot_script_no_gui.py -- <step_file> <output_image> [width] [height]

示例:
  FreeCADCmd -c screenshot_script_no_gui.py -- test28.step test28.png 1920 1080
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
        print("用法: FreeCADCmd -c screenshot_script_no_gui.py -- <step_file> <output_image> [width] [height]")
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
    from pivy import coin
    
    # 设置无GUI模式
    try:
        FreeCADGui.setupWithoutGUI()
        print("GUI setup without GUI successful")
    except Exception as e:
        print(f"setupWithoutGUI warning: {e}")
    
    # 创建新文档
    doc = FreeCAD.newDocument("Screenshot")
    
    # 导入STEP文件
    Import.insert(step_file, doc.Name)
    
    # 重新计算
    doc.recompute()
    
    print("Document loaded and recomputed")
    
    # 获取所有对象
    objects = doc.Objects
    if not objects:
        print("ERROR: No objects found in document")
        sys.exit(1)
    
    print(f"Found {len(objects)} objects")
    
    # 创建场景图
    root = coin.SoSeparator()
    
    # 添加相机和灯光
    cam = coin.SoOrthographicCamera()
    root.addChild(cam)
    
    light = coin.SoDirectionalLight()
    root.addChild(light)
    
    # 为每个对象创建场景图
    for obj in objects:
        try:
            view = FreeCADGui.subgraphFromObject(obj)
            if view:
                root.addChild(view)
                print(f"Added {obj.Name} to scene")
        except Exception as e:
            print(f"Warning: Could not add {obj.Name} to scene: {e}")
    
    # 设置等轴测视角
    axo = coin.SbRotation(-0.353553, -0.146447, -0.353553, -0.853553)
    viewport = coin.SbViewportRegion(width, height)
    cam.orientation.setValue(axo)
    cam.viewAll(root, viewport)
    
    # 离屏渲染
    off = coin.SoOffscreenRenderer(viewport)
    root.ref()
    off.render(root)
    root.unref()
    
    # 确保输出目录存在
    output_dir = os.path.dirname(output_image)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir, exist_ok=True)
    
    # 保存截图
    print(f"Saving screenshot to: {output_image} ({width}x{height})")
    
    if off.isWriteSupported("PNG"):
        off.writeToFile(output_image, "PNG")
        print("Screenshot saved successfully!")
    else:
        print("ERROR: PNG format not supported")
        sys.exit(1)
    
    # 关闭文档
    FreeCAD.closeDocument(doc.Name)

if __name__ == "__main__":
    main()
