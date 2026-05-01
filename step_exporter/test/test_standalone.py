#!/usr/bin/env python3
"""
独立测试脚本：不依赖Blender，直接测试C++扩展模块
"""
import os
import sys
import math

# 添加模块路径
script_dir = os.path.dirname(os.path.abspath(__file__))
step_exporter_dir = os.path.dirname(script_dir)
step_exporter_lib_dir = os.path.join(step_exporter_dir, 'lib')

sys.path.insert(0, step_exporter_dir)
sys.path.insert(0, step_exporter_lib_dir)

# 添加DLL搜索路径
if hasattr(os, 'add_dll_directory'):
    if os.path.exists(step_exporter_lib_dir):
        os.add_dll_directory(step_exporter_lib_dir)

os.environ['PATH'] = step_exporter_lib_dir + os.pathsep + os.environ.get('PATH', '')

try:
    import _step_exporter
    print("[OK] Successfully imported _step_exporter module")
    print(f"Module version: {_step_exporter.get_version()}")
except ImportError as e:
    print(f"[FAIL] Import failed: {e}")
    print(f"lib目录: {step_exporter_lib_dir}")
    print(f"lib目录存在: {os.path.exists(step_exporter_lib_dir)}")
    if os.path.exists(step_exporter_lib_dir):
        print(f"lib目录内容: {os.listdir(step_exporter_lib_dir)}")
    sys.exit(1)

def create_cylinder(radius, height, segments=32, center_z=0):
    """创建圆柱体网格数据"""
    vertices = []
    faces = []
    
    # 顶部和底部中心点
    vertices.append([0, 0, center_z + height])  # 顶部中心
    vertices.append([0, 0, center_z])  # 底部中心
    
    # 顶部和底部圆周点
    for i in range(segments):
        angle = 2 * math.pi * i / segments
        x = radius * math.cos(angle)
        y = radius * math.sin(angle)
        vertices.append([x, y, center_z + height])  # 顶部
        vertices.append([x, y, center_z])  # 底部
    
    # 侧面
    for i in range(segments):
        next_i = (i + 1) % segments
        # 侧面四边形（分成两个三角形）
        top_curr = 2 + i * 2
        top_next = 2 + next_i * 2
        bot_curr = 3 + i * 2
        bot_next = 3 + next_i * 2
        
        faces.append([top_curr, top_next, bot_curr])
        faces.append([top_next, bot_next, bot_curr])
    
    # 顶面
    for i in range(segments):
        next_i = (i + 1) % segments
        faces.append([0, 2 + next_i * 2, 2 + i * 2])
    
    # 底面
    for i in range(segments):
        next_i = (i + 1) % segments
        faces.append([1, 3 + i * 2, 3 + next_i * 2])
    
    return vertices, faces

def test_export():
    """测试导出功能"""
    print("\n=== 测试STEP导出 ===")
    
    # 创建测试对象
    objects_data = []
    
    # 1. 圆柱体 R25 H60
    verts, faces = create_cylinder(25, 60, segments=32)
    objects_data.append({
        'name': 'Cylinder_R25_H60',
        'type': 'mesh',
        'vertices': verts,
        'faces': faces,
    })
    
    # 2. 立方体 50x50x100 at (0, -80, 0)
    cube_verts = [
        [-25, -105, -50], [25, -105, -50], [25, -55, -50], [-25, -55, -50],
        [-25, -105, 50], [25, -105, 50], [25, -55, 50], [-25, -55, 50]
    ]
    cube_faces = [
        [0, 1, 2, 3], [4, 5, 6, 7], [0, 1, 5, 4],
        [2, 3, 7, 6], [1, 2, 6, 5], [0, 4, 7, 3]
    ]
    objects_data.append({
        'name': 'Cube_50x50x100',
        'type': 'mesh',
        'vertices': cube_verts,
        'faces': cube_faces,
    })
    
    # 3. 圆柱体 R25 H60 at (0, 80, 0)
    verts, faces = create_cylinder(25, 60, segments=32, center_z=0)
    # 移动到y=80
    for v in verts:
        v[1] += 80
    objects_data.append({
        'name': 'Cylinder_R25_H60_Y80',
        'type': 'mesh',
        'vertices': verts,
        'faces': faces,
    })
    
    # 输出文件路径
    output_file = os.path.join(step_exporter_dir, 'test28.step')
    log_file = output_file + '.log'
    
    print(f"导出 {len(objects_data)} 个对象到: {output_file}")
    
    try:
        # 调用C++导出函数
        result = _step_exporter.export_scene_enhanced(
            output_file,
            objects_data,
            1.0,  # 缩放因子（数据已经是mm）
            1,    # 修复几何
            1,    # 创建实体
            1     # 高级BREP
        )
        
        if result:
            print(f"[OK] Export successful")
            print(f"File size: {os.path.getsize(output_file)} bytes")
            
            # 检查日志文件
            if os.path.exists(log_file):
                print(f"\nLog file: {log_file}")
                with open(log_file, 'r', encoding='utf-8') as f:
                    log_content = f.read()
                
                # 查找包围盒信息
                import re
                bbox_matches = re.findall(r'Bounding box.*x\[([^\]]+)\]', log_content)
                print(f"\nFound {len(bbox_matches)} bounding box entries:")
                for i, bbox in enumerate(bbox_matches[:11], 1):
                    print(f"  Object {i}: x[{bbox}]")
                
                # 查找半径信息
                radius_matches = re.findall(r'Radius: ([\d.]+)', log_content)
                print(f"\nFound {len(radius_matches)} radius entries:")
                for i, radius in enumerate(radius_matches[:11], 1):
                    print(f"  Object {i}: Radius={radius}")
            
            return True
        else:
            print("[FAIL] Export failed")
            return False
    except Exception as e:
        print(f"[FAIL] Export error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("=== Standalone Test Script ===")
    success = test_export()
    if success:
        print("\n[OK] Test completed!")
    else:
        print("\n[FAIL] Test failed")
