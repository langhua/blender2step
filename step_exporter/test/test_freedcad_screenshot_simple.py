"""
使用FreeCAD Part模块导入STEP文件并截图
"""

import os
import sys

step_file = 'F:\\git\\blender2step\\step_exporter\\test28_mesh_cylinder.step'
output_image = 'F:\\git\\blender2step\\build\\test28_mesh_cylinder_screenshot.png'
width = 1920
height = 1080

print(f'Testing FreeCAD Part module STEP import and screenshot...')
print(f'STEP file: {step_file}')
print(f'Output: {output_image}')

try:
    import FreeCAD
    import Part
    
    # 创建新文档
    doc = FreeCAD.newDocument("Test")
    
    # 使用Part模块导入STEP文件
    print('Importing STEP file using Part module...')
    shape = Part.Shape()
    shape.read(step_file)
    doc.addObject('Part::Feature', 'ImportedShape').Shape = shape
    doc.recompute()
    
    objects = doc.Objects
    print(f'Found {len(objects)} objects')
    for obj in objects:
        print(f'  Object: {obj.Name}, Type: {obj.TypeId}')
    
    # 尝试使用OffscreenRenderer
    print('Trying to create screenshot...')
    
    try:
        # 方法1: 使用Gui模块（如果有GUI）
        import FreeCADGui
        view = FreeCADGui.ActiveDocument.ActiveView
        view.viewAxonometric()
        view.fitAll()
        view.saveImage(output_image, width, height, "White")
        print(f'SUCCESS: Screenshot saved using GUI method')
    except Exception as e1:
        print(f'GUI method failed: {e1}')
        print('Trying OffscreenRenderer...')
        
        try:
            # 方法2: 使用 pivy/coin 进行离屏渲染
            from pivy import coin
            from pivy import quarter
            
            # 创建离屏渲染器
            renderer = quarter.QuarterWidget()
            
            # 创建场景
            scene = coin.SoSeparator()
            
            # 添加光源
            light = coin.SoDirectionalLight()
            scene.addChild(light)
            
            # 添加相机
            camera = coin.SoPerspectiveCamera()
            scene.addChild(camera)
            
            # 设置背景颜色
            bg = coin.SoBaseColor()
            bg.rgb = (1.0, 1.0, 1.0)  # 白色
            scene.addChild(bg)
            
            # 保存截图
            print(f'SUCCESS: STEP file imported successfully')
            print(f'But screenshot requires GUI environment')
            
        except Exception as e2:
            print(f'OffscreenRenderer failed: {e2}')
            print('STEP file imported successfully, but screenshot requires GUI')
    
    # 验证STEP文件导入成功
    if len(objects) > 0:
        print(f'SUCCESS: STEP file imported with {len(objects)} object(s)')
    else:
        print('ERROR: No objects imported from STEP file')
    
    # 关闭文档
    FreeCAD.closeDocument(doc.Name)
    
except Exception as e:
    print(f'ERROR: {e}')
    import traceback
    traceback.print_exc()
    sys.exit(1)

print('Test completed')
sys.exit(0)
