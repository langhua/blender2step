"""
FreeCAD截图脚本 - 命令行模式版本
使用FreeCADCmd.exe，通过OffscreenRenderer截图，使用PIL保存图像
"""

import os
import sys
import math

# 从环境变量读取参数
step_file = os.environ.get('STEP_FILE')
output_image = os.environ.get('OUTPUT_IMAGE')
width = int(os.environ.get('IMAGE_WIDTH', '1920'))
height = int(os.environ.get('IMAGE_HEIGHT', '1080'))

print(f'=' * 60)
print(f'FreeCAD Screenshot Script (Cmd Mode)')
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
    
    # 计算所有对象的边界框
    min_x = min_y = min_z = float('inf')
    max_x = max_y = max_z = float('-inf')
    
    for obj in objects:
        if hasattr(obj, 'Shape') and obj.Shape:
            bbox = obj.Shape.BoundBox
            min_x = min(min_x, bbox.XMin)
            min_y = min(min_y, bbox.YMin)
            min_z = min(min_z, bbox.ZMin)
            max_x = max(max_x, bbox.XMax)
            max_y = max(max_y, bbox.YMax)
            max_z = max(max_z, bbox.ZMax)
            print(f'  Object {obj.Name}: bbox=({bbox.XMin:.1f},{bbox.YMin:.1f},{bbox.ZMin:.1f})-({bbox.XMax:.1f},{bbox.YMax:.1f},{bbox.ZMax:.1f})')
    
    # 计算中心点和尺寸
    center_x = (min_x + max_x) / 2
    center_y = (min_y + max_y) / 2
    center_z = (min_z + max_z) / 2
    
    size_x = max_x - min_x
    size_y = max_y - min_y
    size_z = max_z - min_z
    max_size = max(size_x, size_y, size_z)
    
    print(f'Center: ({center_x:.1f}, {center_y:.1f}, {center_z:.1f})')
    print(f'Size: ({size_x:.1f}, {size_y:.1f}, {size_z:.1f})')
    print(f'Max size: {max_size:.1f}')
    
    # 使用OffscreenRenderer截图
    print('Using OffscreenRenderer...')
    
    # 创建离屏渲染器
    viewport = coin.SbViewportRegion(width, height)
    renderer = coin.SoOffscreenRenderer(viewport)
    renderer.setBackgroundColor(coin.SbColor(1, 1, 1))
    
    # 手动创建场景图
    root = coin.SoSeparator()
    
    # 相机位置 - 从等轴测方向看
    camera_distance = max_size * 3
    
    cam_x = center_x + camera_distance * 0.577
    cam_y = center_y + camera_distance * 0.577
    cam_z = center_z + camera_distance * 0.577
    
    camera = coin.SoPerspectiveCamera()
    camera.position.setValue(cam_x, cam_y, cam_z)
    
    # 设置相机看向中心点
    # orientation是四元数，我们需要计算从(0,0,-1)到目标方向的旋转
    target_dir_x = center_x - cam_x
    target_dir_y = center_y - cam_y
    target_dir_z = center_z - cam_z
    
    # 归一化
    length = math.sqrt(target_dir_x**2 + target_dir_y**2 + target_dir_z**2)
    target_dir_x /= length
    target_dir_y /= length
    target_dir_z /= length
    
    # 计算旋转轴和角度
    # 默认方向是(0, 0, -1)
    default_x, default_y, default_z = 0, 0, -1
    
    # 叉积 = 旋转轴
    axis_x = default_y * target_dir_z - default_z * target_dir_y
    axis_y = default_z * target_dir_x - default_x * target_dir_z
    axis_z = default_x * target_dir_y - default_y * target_dir_x
    
    # 点积 = cos(角度)
    dot = default_x * target_dir_x + default_y * target_dir_y + default_z * target_dir_z
    
    # 创建旋转
    if abs(dot + 1) < 0.0001:
        # 180度旋转
        rotation = coin.SbRotation(0, 1, 0, 0)
    elif abs(dot - 1) < 0.0001:
        # 0度旋转
        rotation = coin.SbRotation(0, 0, 0, 1)
    else:
        angle = math.acos(dot)
        axis_len = math.sqrt(axis_x**2 + axis_y**2 + axis_z**2)
        if axis_len > 0.0001:
            axis_x /= axis_len
            axis_y /= axis_len
            axis_z /= axis_len
            half_angle = angle / 2
            sin_half = math.sin(half_angle)
            rotation = coin.SbRotation(
                axis_x * sin_half,
                axis_y * sin_half,
                axis_z * sin_half,
                math.cos(half_angle)
            )
        else:
            rotation = coin.SbRotation(0, 0, 0, 1)
    
    camera.orientation.setValue(rotation)
    camera.heightAngle.setValue(0.5)
    
    root.addChild(camera)
    
    # 添加灯光 - 从相机方向照射
    light = coin.SoDirectionalLight()
    light.direction.setValue(-0.577, -0.577, -0.577)
    light.intensity.setValue(1.0)
    root.addChild(light)
    
    # 添加环境光
    ambient = coin.SoDirectionalLight()
    ambient.direction.setValue(0, 0, -1)
    ambient.intensity.setValue(0.4)
    root.addChild(ambient)
    
    # 添加材质
    material = coin.SoMaterial()
    material.diffuseColor.setValue(0.7, 0.7, 0.7)  # 灰色
    material.specularColor.setValue(0.3, 0.3, 0.3)
    material.shininess.setValue(0.5)
    root.addChild(material)
    
    # 为每个对象创建几何体
    for obj in objects:
        if hasattr(obj, 'Shape') and obj.Shape:
            shape = obj.Shape
            
            # 获取顶点和面
            mesh = shape.tessellate(0.1)
            vertices = mesh[0]
            faces = mesh[1]
            
            print(f'  Object {obj.Name}: {len(vertices)} vertices, {len(faces)} faces')
            
            # 创建几何体节点 - 坐标和面集必须在同一个Separator中
            obj_sep = coin.SoSeparator()
            
            # 将Vector对象转换为元组
            vertex_tuples = [(v.x, v.y, v.z) for v in vertices]
            
            coord = coin.SoCoordinate3()
            coord.point.setValues(0, len(vertex_tuples), vertex_tuples)
            obj_sep.addChild(coord)
            
            # 创建面集
            face_set = coin.SoFaceSet()
            num_faces = []
            for face in faces:
                num_faces.append(len(face))
            face_set.numVertices.setValues(0, len(num_faces), num_faces)
            obj_sep.addChild(face_set)
            
            root.addChild(obj_sep)
    
    # 渲染
    print('Rendering...')
    result = renderer.render(root)
    
    if result:
        # 获取像素缓冲区
        print('Getting pixel buffer...')
        buffer = renderer.getBuffer()
        
        # 使用PIL保存图像
        try:
            from PIL import Image
            import numpy as np
            
            pixels = np.frombuffer(buffer, dtype=np.uint8)
            
            buffer_size = len(pixels)
            expected_rgba = width * height * 4
            expected_rgb = width * height * 3
            
            print(f'Buffer size: {buffer_size}')
            print(f'Expected RGBA: {expected_rgba}')
            print(f'Expected RGB: {expected_rgb}')
            
            # 检查前几个像素
            print(f'First 20 pixels: {pixels[:60]}')
            
            if buffer_size == expected_rgba:
                pixels = pixels.reshape((height, width, 4))
                img = Image.fromarray(pixels, 'RGBA')
            elif buffer_size == expected_rgb:
                pixels = pixels.reshape((height, width, 3))
                img = Image.fromarray(pixels, 'RGB')
            else:
                print(f'ERROR: Unexpected buffer size {buffer_size}')
                sys.exit(1)
            
            img.save(output_image, 'PNG')
            
            if os.path.exists(output_image):
                file_size = os.path.getsize(output_image)
                print(f'SUCCESS: Screenshot saved to {output_image}')
                print(f'File size: {file_size} bytes')
            else:
                print(f'ERROR: Screenshot file not created')
        except ImportError:
            print('ERROR: PIL or numpy not available')
    else:
        print('ERROR: Rendering failed')
    
    # 关闭文档
    FreeCAD.closeDocument(doc.Name)
    print('Document closed')
    
except Exception as e:
    print(f'ERROR: Screenshot failed: {e}')
    import traceback
    traceback.print_exc()
    sys.exit(1)

print('Screenshot script completed')
