"""
测试FreeCAD内置截图功能
"""

import os
import sys

step_file = os.environ.get('STEP_FILE', 'F:\\git\\blender2step\\step_exporter\\test58.step')
output_image = os.environ.get('OUTPUT_IMAGE', 'F:\\git\\blender2step\\build\\test_freedcad_screenshot.png')
width = int(os.environ.get('IMAGE_WIDTH', '1920'))
height = int(os.environ.get('IMAGE_HEIGHT', '1080'))

print(f'Testing FreeCAD built-in screenshot...')
print(f'STEP file: {step_file}')
print(f'Output: {output_image}')

try:
    import FreeCAD
    import FreeCADGui
    import Import
    
    # 创建新文档
    doc = FreeCAD.newDocument("Test")
    
    # 导入STEP文件
    Import.insert(step_file, doc.Name)
    doc.recompute()
    
    objects = doc.Objects
    print(f'Found {len(objects)} objects')
    
    # 获取视图
    view = FreeCADGui.ActiveDocument.ActiveView
    
    # 设置等轴测视图
    print('Setting axonometric view...')
    view.viewAxonometric()
    
    # 适配所有对象
    print('Fitting all objects...')
    view.fitAll()
    
    # 切换到着色模式（美化渲染）
    print('Switching to shaded mode...')
    
    # 设置显示模式为着色
    for obj in doc.Objects:
        if hasattr(obj, 'ViewObject'):
            # 尝试多种显示模式
            try:
                obj.ViewObject.DisplayMode = "Shaded"
            except:
                try:
                    obj.ViewObject.DisplayMode = "Flat Lines"
                except:
                    obj.ViewObject.DisplayMode = "Gouraud"
            
            # 设置材质颜色（浅蓝色）
            obj.ViewObject.ShapeColor = (0.4, 0.6, 0.8)
            # 设置透明度
            obj.ViewObject.Transparency = 0
            # 隐藏边线
            obj.ViewObject.LineWidth = 0.0
            obj.ViewObject.LineColor = (0.2, 0.2, 0.2)
            # 启用光照
            obj.ViewObject.Lighting = "One side"
    
    # 等待渲染完成
    print('Waiting for rendering...')
    import time
    time.sleep(3)
    
    # 截图
    print(f'Saving screenshot to: {output_image}')
    view.saveImage(output_image, width, height, "White")
    
    # 验证截图是否成功
    if os.path.exists(output_image):
        file_size = os.path.getsize(output_image)
        print(f'SUCCESS: Screenshot saved to {output_image}')
        print(f'File size: {file_size} bytes')
    else:
        print(f'ERROR: Screenshot file not created: {output_image}')
    
    # 关闭文档
    FreeCAD.closeDocument(doc.Name)
    
except Exception as e:
    print(f'ERROR: {e}')
    import traceback
    traceback.print_exc()
    sys.exit(1)

print('Test completed')

# 退出FreeCAD GUI
print('Closing FreeCAD...')
try:
    import FreeCADGui
    # 使用QTimer延迟退出，确保截图已保存
    from PySide2 import QtCore
    
    def close_freedcad():
        try:
            FreeCADGui.getMainWindow().close()
        except:
            pass
    
    timer = QtCore.QTimer()
    timer.timeout.connect(close_freedcad)
    timer.setSingleShot(True)
    timer.start(500)  # 0.5秒后退出
    print('Timer started, FreeCAD will close in 0.5 seconds...')
except Exception as e:
    print(f'Warning: Failed to start timer: {e}')
    sys.exit(0)
