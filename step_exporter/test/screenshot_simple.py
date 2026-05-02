"""
简化版FreeCAD截图脚本 - 避免崩溃
"""

import os
import sys
import time

step_file = os.environ.get('STEP_FILE', 'F:\\git\\blender2step\\step_exporter\\test28.step')
output_image = os.environ.get('OUTPUT_IMAGE', 'F:\\git\\blender2step\\build\\test28.png')
width = int(os.environ.get('IMAGE_WIDTH', '1920'))
height = int(os.environ.get('IMAGE_HEIGHT', '1080'))

print(f'Simple FreeCAD Screenshot')
print(f'STEP file: {step_file}')
print(f'Output: {output_image}')

try:
    import FreeCAD
    import FreeCADGui
    import Import
    
    # 创建新文档
    doc = FreeCAD.newDocument("Screenshot")
    
    # 导入STEP文件
    print('Importing STEP...')
    Import.insert(step_file, doc.Name)
    doc.recompute()
    time.sleep(2)
    
    objects = doc.Objects
    print(f'Found {len(objects)} objects')
    for obj in objects:
        print(f'  - {obj.Name} ({obj.TypeId})')
    
    # 获取视图
    view = FreeCADGui.ActiveDocument.ActiveView
    
    # 设置视图
    view.viewAxonometric()
    view.fitAll()
    
    # 简单设置颜色
    for obj in doc.Objects:
        if hasattr(obj, 'ViewObject') and obj.ViewObject:
            try:
                obj.ViewObject.ShapeColor = (0.5, 0.7, 1.0)
            except:
                pass
    
    # 等待渲染
    print('Rendering...')
    time.sleep(3)
    
    # 截图
    print(f'Saving to: {output_image}')
    view.saveImage(output_image, width, height, "White")
    
    if os.path.exists(output_image):
        file_size = os.path.getsize(output_image)
        print(f'SUCCESS: {file_size} bytes')
    else:
        print(f'ERROR: Image not created')
    
    FreeCAD.closeDocument(doc.Name)
    
except Exception as e:
    print(f'ERROR: {e}')
    import traceback
    traceback.print_exc()
    sys.exit(1)

print('Done')

# 延迟退出
try:
    from PySide2 import QtCore
    import FreeCADGui
    
    def close_app():
        try:
            FreeCADGui.getMainWindow().close()
        except:
            pass
    
    timer = QtCore.QTimer()
    timer.timeout.connect(close_app)
    timer.setSingleShot(True)
    timer.start(500)
except:
    pass
