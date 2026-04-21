"""
测试Coin3D坐标设置方法
"""

import os
import sys
import math

output_image = os.environ.get('OUTPUT_IMAGE', 'F:\\git\\blender2step\\build\\test_coin3d.png')
width = 800
height = 600

print(f'Testing Coin3D coordinate setting methods...')
print(f'Output: {output_image}')

try:
    from pivy import coin
    from PIL import Image
    import numpy as np
    
    # 创建场景
    root = coin.SoSeparator()
    
    # 相机
    camera = coin.SoPerspectiveCamera()
    camera.position.setValue(0, 0, 5)
    root.addChild(camera)
    
    # 灯光
    light = coin.SoDirectionalLight()
    light.direction.setValue(0.5, 0.5, -1)
    light.intensity.setValue(1.0)
    root.addChild(light)
    
    # 材质 - 蓝色
    material = coin.SoMaterial()
    material.diffuseColor.setValue(0, 0, 1)
    root.addChild(material)
    
    # 创建金字塔几何体
    obj_sep = coin.SoSeparator()
    
    # 方法1: 使用setValues
    vertices1 = [
        (0, 1, 0),
        (-1, -1, 1),
        (1, -1, 1),
        (1, -1, -1),
        (-1, -1, -1)
    ]
    
    coord1 = coin.SoCoordinate3()
    coord1.point.setValues(0, len(vertices1), vertices1)
    obj_sep.addChild(coord1)
    
    face_set1 = coin.SoFaceSet()
    face_set1.numVertices.setValues(0, 4, [3, 3, 3, 3])
    obj_sep.addChild(face_set1)
    
    root.addChild(obj_sep)
    
    # 创建离屏渲染器
    viewport = coin.SbViewportRegion(width, height)
    renderer = coin.SoOffscreenRenderer(viewport)
    renderer.setBackgroundColor(coin.SbColor(0.9, 0.9, 0.9))
    
    # 渲染
    print('Rendering...')
    result = renderer.render(root)
    print(f'Render result: {result}')
    
    if result:
        buffer = renderer.getBuffer()
        pixels = np.frombuffer(buffer, dtype=np.uint8)
        
        buffer_size = len(pixels)
        expected_rgb = width * height * 3
        
        print(f'Buffer size: {buffer_size}')
        
        # 检查前几个像素
        print(f'First 20 pixels: {pixels[:60]}')
        
        # 检查是否有非白色像素
        non_white = 0
        for i in range(0, min(buffer_size, 1000), 3):
            r, g, b = pixels[i], pixels[i+1], pixels[i+2]
            if r < 250 or g < 250 or b < 250:
                non_white += 1
        
        print(f'Non-white pixels in first 1000: {non_white}')
        
        if buffer_size == expected_rgb:
            pixels = pixels.reshape((height, width, 3))
            img = Image.fromarray(pixels, 'RGB')
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
