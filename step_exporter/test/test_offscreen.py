"""
测试OffscreenRenderer是否正常工作
"""

import os
import sys

output_image = os.environ.get('OUTPUT_IMAGE', 'F:\\git\\blender2step\\build\\test_offscreen.png')
width = 800
height = 600

print(f'Testing OffscreenRenderer...')
print(f'Output: {output_image}')

try:
    from pivy import coin
    from PIL import Image
    import numpy as np
    
    # 创建离屏渲染器
    viewport = coin.SbViewportRegion(width, height)
    renderer = coin.SoOffscreenRenderer(viewport)
    renderer.setBackgroundColor(coin.SbColor(1, 1, 1))
    
    # 创建简单场景 - 一个红色立方体
    root = coin.SoSeparator()
    
    # 相机
    camera = coin.SoPerspectiveCamera()
    camera.position.setValue(0, 0, 5)
    root.addChild(camera)
    
    # 灯光
    light = coin.SoDirectionalLight()
    light.direction.setValue(0, 0, -1)
    light.intensity.setValue(1.0)
    root.addChild(light)
    
    # 材质 - 红色
    material = coin.SoMaterial()
    material.diffuseColor.setValue(1, 0, 0)
    root.addChild(material)
    
    # 立方体
    cube = coin.SoCube()
    root.addChild(cube)
    
    # 渲染
    print('Rendering...')
    result = renderer.render(root)
    print(f'Render result: {result}')
    
    if result:
        # 获取像素缓冲区
        buffer = renderer.getBuffer()
        pixels = np.frombuffer(buffer, dtype=np.uint8)
        
        buffer_size = len(pixels)
        expected_rgb = width * height * 3
        expected_rgba = width * height * 4
        
        print(f'Buffer size: {buffer_size}')
        print(f'Expected RGB: {expected_rgb}')
        print(f'Expected RGBA: {expected_rgba}')
        
        # 检查前几个像素
        print(f'First 10 pixels: {pixels[:40]}')
        
        if buffer_size == expected_rgb:
            pixels = pixels.reshape((height, width, 3))
            img = Image.fromarray(pixels, 'RGB')
        elif buffer_size == expected_rgba:
            pixels = pixels.reshape((height, width, 4))
            img = Image.fromarray(pixels, 'RGBA')
        else:
            print(f'ERROR: Unexpected buffer size')
            sys.exit(1)
        
        img.save(output_image, 'PNG')
        
        if os.path.exists(output_image):
            file_size = os.path.getsize(output_image)
            print(f'SUCCESS: Saved to {output_image}')
            print(f'File size: {file_size} bytes')
        else:
            print('ERROR: File not created')
    else:
        print('ERROR: Render failed')
        
except Exception as e:
    print(f'ERROR: {e}')
    import traceback
    traceback.print_exc()
    sys.exit(1)

print('Test completed')
