"""
FreeCAD截图脚本 - GUI模式自动关闭版本
使用FreeCAD.exe，截图后自动退出
"""

import os
import sys
import time

def main():
    # 从环境变量读取参数
    step_file = os.environ.get('STEP_FILE')
    output_image = os.environ.get('OUTPUT_IMAGE')
    width = int(os.environ.get('IMAGE_WIDTH', '1920'))
    height = int(os.environ.get('IMAGE_HEIGHT', '1080'))
    
    print(f'=' * 60)
    print(f'FreeCAD Screenshot Script (GUI Auto-Close)')
    print(f'=' * 60)
    print(f'STEP file: {step_file}')
    print(f'Output image: {output_image}')
    print(f'Resolution: {width}x{height}')
    
    if not step_file or not output_image:
        print('ERROR: STEP_FILE or OUTPUT_IMAGE not set')
        sys.exit(1)
    
    if not os.path.exists(step_file):
        print(f'ERROR: STEP file not found: {step_file}')
        sys.exit(1)
    
    try:
        import FreeCAD
        import FreeCADGui
        import Import
        
        # 确保输出目录存在
        output_dir = os.path.dirname(output_image)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir, exist_ok=True)
            print(f'Created output directory: {output_dir}')
        
        # 创建新文档
        print('Creating new document...')
        doc = FreeCAD.newDocument("Screenshot")
        
        # 导入STEP文件
        print(f'Importing STEP file: {step_file}')
        Import.insert(step_file, doc.Name)
        doc.recompute()
        
        # 等待导入完成
        time.sleep(1)
        
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
        
        # 等待渲染完成
        print('Waiting for rendering...')
        time.sleep(2)
        
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
        print('Document closed')
        
    except Exception as e:
        print(f'ERROR: Screenshot failed: {e}')
        import traceback
        traceback.print_exc()
        sys.exit(1)
    
    print('Screenshot script completed')
    
    # 关闭文档
    try:
        FreeCAD.closeDocument(doc.Name)
        print('Document closed')
    except:
        pass
    
    # 退出FreeCAD GUI
    print('Closing FreeCAD...')
    try:
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

if __name__ == "__main__":
    main()
