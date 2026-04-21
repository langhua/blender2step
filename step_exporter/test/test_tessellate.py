"""
测试tessellate返回的数据格式
"""

import os
import sys

step_file = os.environ.get('STEP_FILE', 'F:\\git\\blender2step\\step_exporter\\test58.step')

print(f'Testing tessellate format...')
print(f'STEP file: {step_file}')

try:
    import FreeCAD
    import Import
    
    # 创建新文档
    doc = FreeCAD.newDocument("Test")
    
    # 导入STEP文件
    Import.insert(step_file, doc.Name)
    doc.recompute()
    
    objects = doc.Objects
    print(f'Found {len(objects)} objects')
    
    for obj in objects:
        if hasattr(obj, 'Shape') and obj.Shape:
            shape = obj.Shape
            
            # 获取顶点和面
            mesh = shape.tessellate(0.1)
            vertices = mesh[0]
            faces = mesh[1]
            
            print(f'\nObject {obj.Name}:')
            print(f'  Vertices count: {len(vertices)}')
            print(f'  First 3 vertices: {vertices[:3]}')
            print(f'  Faces count: {len(faces)}')
            print(f'  First 3 faces: {faces[:3]}')
            print(f'  Face 0 vertex count: {len(faces[0])}')
            
            # 检查顶点索引是否在范围内
            max_index = max([max(face) for face in faces])
            print(f'  Max vertex index: {max_index}')
            print(f'  Valid: {max_index < len(vertices)}')
    
    # 关闭文档
    FreeCAD.closeDocument(doc.Name)
    
except Exception as e:
    print(f'ERROR: {e}')
    import traceback
    traceback.print_exc()
    sys.exit(1)

print('\nTest completed')
