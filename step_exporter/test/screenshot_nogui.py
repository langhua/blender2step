"""
FreeCAD无GUI截图脚本 - 使用pivy coin进行离屏渲染
"""

import sys
import os

def main():
    # 从环境变量读取参数
    step_file = os.environ.get('STEP_FILE')
    output_image = os.environ.get('OUTPUT_IMAGE')
    width = int(os.environ.get('IMAGE_WIDTH', '1920'))
    height = int(os.environ.get('IMAGE_HEIGHT', '1080'))
    
    print(f'=' * 60)
    print(f'FreeCAD Screenshot Script (No-GUI OffscreenRenderer)')
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
        from pivy import coin
        
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
        
        objects = doc.Objects
        print(f'Found {len(objects)} objects')
        
        if not objects:
            print('ERROR: No objects found in document')
            sys.exit(1)
        
        # 创建场景图
        root = coin.SoSeparator()
        
        # 添加相机和灯光
        cam = coin.SoOrthographicCamera()
        root.addChild(cam)
        
        light = coin.SoDirectionalLight()
        light.direction.setValue(0.5, 0.5, -1)
        light.intensity.setValue(1.0)
        root.addChild(light)
        
        # 为每个对象创建场景图
        for obj in objects:
            try:
                view = FreeCADGui.subgraphFromObject(obj)
                if view:
                    root.addChild(view)
                    print(f'Added {obj.Name} to scene')
                else:
                    print(f'Warning: subgraphFromObject returned None for {obj.Name}')
            except Exception as e:
                print(f'Warning: Could not add {obj.Name} to scene: {e}')
                import traceback
                traceback.print_exc()
        
        # 设置等轴测视角
        print('Setting axonometric view...')
        axo = coin.SbRotation(-0.353553, -0.146447, -0.353553, -0.853553)
        viewport = coin.SbViewportRegion(width, height)
        cam.orientation.setValue(axo)
        cam.viewAll(root, viewport)
        
        # 离屏渲染
        print('Rendering...')
        off = coin.SoOffscreenRenderer(viewport)
        off.setBackgroundColor(coin.SbColor(1, 1, 1))
        
        root.ref()
        result = off.render(root)
        root.unref()
        
        print(f'Render result: {result}')
        
        # 保存截图
        print(f'Saving screenshot to: {output_image} ({width}x{height})')
        
        if off.isWriteSupported("PNG"):
            off.writeToFile(output_image, "PNG")
            print('Screenshot saved successfully!')
        else:
            print('ERROR: PNG format not supported')
            sys.exit(1)
        
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

if __name__ == "__main__":
    main()
