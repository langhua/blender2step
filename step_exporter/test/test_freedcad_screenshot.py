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
    import Part
    
    # 创建新文档
    doc = FreeCAD.newDocument("Test")
    
    # 导入STEP文件 - 尝试使用Part模块
    print('Importing STEP file using Part module...')
    try:
        shape = Part.Shape()
        shape.read(step_file)
        doc.addObject('Part::Feature', 'ImportedShape').Shape = shape
        doc.recompute()
        print('Successfully imported using Part module')
    except Exception as e1:
        print(f'Part module import failed: {e1}')
        print('Trying Import module...')
        try:
            Import.insert(step_file, doc.Name)
            doc.recompute()
            print('Successfully imported using Import module')
        except Exception as e2:
            print(f'Import module also failed: {e2}')
            raise
    
    objects = doc.Objects
    print(f'Found {len(objects)} objects')
    for obj in objects:
        print(f'  Object: {obj.Name}, Type: {obj.TypeId}')
        if hasattr(obj, 'LinkedObject') and obj.LinkedObject:
            print(f'    -> Linked to: {obj.LinkedObject.Name}')
    
    # 获取视图 - 处理FreeCADCmd模式
    try:
        view = FreeCADGui.ActiveDocument.ActiveView
    except AttributeError:
        print('FreeCADGui.ActiveDocument not available, trying alternative method...')
        view = FreeCADGui.getDocument(doc.Name).ActiveView
    
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
        if hasattr(obj, 'ViewObject') and obj.ViewObject:
            # 处理Link对象
            actual_obj = obj
            if hasattr(obj, 'LinkedObject') and obj.LinkedObject:
                actual_obj = obj.LinkedObject
                print(f'  Using linked object: {actual_obj.Name}')
            
            # 获取可用的显示模式
            try:
                if hasattr(actual_obj, 'ViewObject') and actual_obj.ViewObject:
                    modes = actual_obj.ViewObject.listDisplayModes()
                    print(f'Available display modes for {actual_obj.Name}: {modes}')
                    # 优先选择 Shaded 模式以显示光滑的解析曲面
                    chosen_mode = None
                    for mode in ['Shaded', 'Flat Lines', 'Gouraud', 'Shaded with edges', 'Hidden line', 'Wireframe']:
                        if mode in modes:
                            chosen_mode = mode
                            break
                    if chosen_mode is None and len(modes) > 0:
                        chosen_mode = modes[0]
                    
                    if chosen_mode:
                        actual_obj.ViewObject.DisplayMode = chosen_mode
                        print(f'Set display mode to: {chosen_mode}')
            except Exception as e:
                print(f'Warning: Failed to set display mode for {actual_obj.Name}: {e}')
            
            # 设置材质颜色（浅蓝色）
            try:
                if hasattr(actual_obj, 'ViewObject') and actual_obj.ViewObject:
                    actual_obj.ViewObject.ShapeColor = (0.4, 0.6, 0.8)
                    actual_obj.ViewObject.Transparency = 0
            except Exception as e:
                print(f'Warning: Failed to set shape color for {actual_obj.Name}: {e}')
            # 隐藏边线 - 关键修复：将LineWidth设为0并设置LineColor与ShapeColor相同
            try:
                obj.ViewObject.LineWidth = 0.0
                obj.ViewObject.LineColor = (0.4, 0.6, 0.8)  # 与ShapeColor相同，使边线不可见
            except Exception as e:
                print(f'Warning: Failed to set line properties for {obj.Name}: {e}')
            # 启用光照
            try:
                obj.ViewObject.Lighting = "One side"
            except Exception as e:
                print(f'Warning: Failed to set lighting for {obj.Name}: {e}')
    
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
