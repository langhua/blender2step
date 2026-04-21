"""
简单测试脚本：导出单个圆柱体STEP文件并生成FreeCAD截图
用法: 
  blender --background --python run_test_simple.py -- --test-number 57
"""

import bpy
import sys
import os
import time
import subprocess
import argparse

def parse_args():
    parser = argparse.ArgumentParser(description='Run simple test')
    parser.add_argument('--test-number', type=str, default='57', help='Test number')
    parser.add_argument('--output-dir', type=str, default=r'F:\git\blender2step\step_exporter', help='Output directory')
    parser.add_argument('--screenshot-dir', type=str, default=r'F:\git\blender2step\build', help='Screenshot directory')
    parser.add_argument('--freecad-path', type=str, default=r'F:\Program Files\FreeCAD 1.0\bin\FreeCAD.exe', help='FreeCAD path')
    parser.add_argument('--skip-screenshot', action='store_true', help='Skip screenshot')
    
    if '--' in sys.argv:
        idx = sys.argv.index('--')
        script_args = sys.argv[idx + 1:]
    else:
        script_args = []
    
    return parser.parse_args(script_args)

def create_simple_cylinder():
    """创建简单圆柱体"""
    # 清除场景
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)
    
    # 创建圆柱体
    bpy.ops.mesh.primitive_cylinder_add(
        radius=25,
        depth=60,
        location=[0, 0, 0],
        vertices=32
    )
    
    obj = bpy.context.active_object
    obj.name = "Simple_Cylinder"
    
    print(f"Created simple cylinder: {obj.name}")
    print(f"Vertices: {len(obj.data.vertices)}")
    print(f"Faces: {len(obj.data.polygons)}")

def export_step(args):
    """导出STEP文件"""
    test_number = args.test_number
    output_dir = args.output_dir
    
    output_path = os.path.join(output_dir, f'test{test_number}.step')
    log_path = output_path + '.log'
    
    # 选择所有对象
    bpy.ops.object.select_all(action='SELECT')
    
    objects_to_export = [obj for obj in bpy.context.scene.objects if obj.type in ('MESH', 'CURVE')]
    print(f'Objects to export: {len(objects_to_export)}')
    for obj in objects_to_export:
        print(f'  - {obj.name}')
    
    # 添加路径
    script_dir = os.path.dirname(os.path.abspath(__file__))
    step_exporter_dir = os.path.dirname(script_dir)
    step_exporter_lib_dir = os.path.join(step_exporter_dir, 'lib')
    
    if step_exporter_dir not in sys.path:
        sys.path.insert(0, step_exporter_dir)
    if step_exporter_lib_dir not in sys.path:
        sys.path.insert(0, step_exporter_lib_dir)
    
    # DLL搜索路径
    if step_exporter_lib_dir not in os.environ.get('PATH', ''):
        os.environ['PATH'] = step_exporter_lib_dir + os.pathsep + os.environ.get('PATH', '')
    
    if hasattr(os, 'add_dll_directory'):
        if os.path.exists(step_exporter_lib_dir):
            os.add_dll_directory(step_exporter_lib_dir)
    
    # 导入C++扩展
    import _step_exporter as cpp_exporter
    
    # 打开日志
    log_file = open(log_path, 'w', encoding='utf-8')
    
    def log_callback(msg):
        print(f'[LOG] {msg}')
        log_file.write(msg + '\n')
        log_file.flush()
    
    # 准备对象数据
    objects_data = []
    scale = 1000.0
    
    for obj in objects_to_export:
        depsgraph = bpy.context.evaluated_depsgraph_get()
        eval_obj = obj.evaluated_get(depsgraph)
        mesh = eval_obj.data
        
        vertices = []
        for vert in mesh.vertices:
            world_co = eval_obj.matrix_world @ vert.co
            vertices.append([float(world_co.x) * scale, float(world_co.y) * scale, float(world_co.z) * scale])
        
        mesh.calc_loop_triangles()
        faces = []
        for tri in mesh.loop_triangles:
            faces.append(list(tri.vertices))
        
        normals = []
        for tri in mesh.loop_triangles:
            normals.append([float(tri.normal.x), float(tri.normal.y), float(tri.normal.z)])
        
        objects_data.append({
            'name': obj.name,
            'type': 'mesh',
            'vertices': vertices,
            'faces': faces,
            'normals': normals,
            'matrix_world': list(eval_obj.matrix_world),
        })
    
    print(f'Prepared {len(objects_data)} objects')
    
    # 初始化导出
    success = cpp_exporter.init_incremental_export(
        output_path, len(objects_data), scale, 1, 1, 1,
        'AP214DIS', 'MILLIMETER', 1, 0.001, log_callback
    )
    
    if not success:
        print('ERROR: Failed to initialize export')
        log_file.close()
        sys.exit(1)
    
    # 添加对象
    for i, obj_data in enumerate(objects_data):
        print(f'Exporting object {i+1}/{len(objects_data)}: {obj_data["name"]}')
        success = cpp_exporter.add_object_to_export(obj_data, lambda p: None)
        print(f'  -> {"OK" if success else "FAILED"}')
    
    # 完成导出
    success = cpp_exporter.finalize_incremental_export()
    log_file.close()
    
    if success:
        print(f'SUCCESS: Exported to {output_path}')
        if os.path.exists(output_path):
            size = os.path.getsize(output_path)
            print(f'File size: {size} bytes')
    else:
        print('ERROR: Export failed')
        sys.exit(1)
    
    return output_path

def take_screenshot(args, step_file):
    """使用FreeCAD截图"""
    test_number = args.test_number
    screenshot_dir = args.screenshot_dir
    freecad_path = args.freecad_path
    
    os.makedirs(screenshot_dir, exist_ok=True)
    output_image = os.path.join(screenshot_dir, f'test{test_number}.png')
    
    # 使用FreeCAD.exe（GUI模式）
    freecad_cmd = freecad_path
    freecad_dir = os.path.dirname(freecad_path)
    
    if not os.path.exists(freecad_cmd):
        print(f"ERROR: FreeCAD.exe not found at {freecad_cmd}")
        return False
    
    # 使用test_freedcad_screenshot.py
    script_dir = os.path.dirname(os.path.abspath(__file__))
    temp_script = os.path.join(script_dir, 'test_freedcad_screenshot.py')
    
    if not os.path.exists(temp_script):
        print(f"ERROR: test_freedcad_screenshot.py not found at {temp_script}")
        return False
    
    # 设置环境变量传递参数
    env = os.environ.copy()
    env['STEP_FILE'] = os.path.abspath(step_file)
    env['OUTPUT_IMAGE'] = os.path.abspath(output_image)
    env['IMAGE_WIDTH'] = '1920'
    env['IMAGE_HEIGHT'] = '1080'
    # 使用离屏渲染模式
    env['QT_QPA_PLATFORM'] = 'offscreen'
    
    cmd = [freecad_cmd, temp_script]
    
    print(f"Running FreeCAD screenshot")
    print(f"STEP file: {step_file}")
    print(f"Output image: {output_image}")
    
    import platform
    
    try:
        result = subprocess.run(
            cmd, 
            capture_output=True, 
            text=True, 
            timeout=60,
            env=env,
            cwd=freecad_dir
        )
        print(f"FreeCAD stdout: {result.stdout}")
        if result.stderr:
            print(f"FreeCAD stderr: {result.stderr}")
        
        if result.returncode == 0 and os.path.exists(output_image):
            print(f"SUCCESS: Screenshot saved to {output_image}")
            return True
        else:
            print(f"ERROR: FreeCAD returned code {result.returncode}")
            if not os.path.exists(output_image):
                print(f"ERROR: Output image not found: {output_image}")
            return False
    except subprocess.TimeoutExpired:
        print("WARNING: FreeCAD screenshot timed out, forcing close...")
        # 强制关闭FreeCAD进程
        if platform.system() == 'Windows':
            subprocess.run(['taskkill', '/F', '/IM', 'FreeCAD.exe'], capture_output=True)
        # 检查截图是否已经生成
        if os.path.exists(output_image):
            print(f"SUCCESS: Screenshot saved to {output_image} (after timeout)")
            return True
        return False
    except Exception as e:
        print(f"ERROR: Failed to run FreeCAD screenshot: {e}")
        return False

def main():
    args = parse_args()
    
    # 步骤1: 创建简单圆柱体
    print("=" * 60)
    print("Step 1: Creating simple cylinder")
    print("=" * 60)
    create_simple_cylinder()
    
    # 步骤2: 导出STEP
    print("=" * 60)
    print("Step 2: Exporting STEP file")
    print("=" * 60)
    step_file = export_step(args)
    
    # 步骤3: 截图
    if not args.skip_screenshot:
        print("=" * 60)
        print("Step 3: Taking screenshot with FreeCAD")
        print("=" * 60)
        success = take_screenshot(args, step_file)
        
        if success:
            print("=" * 60)
            print("TEST COMPLETED SUCCESSFULLY")
            print("=" * 60)
            print(f"STEP file: {step_file}")
            print(f"Screenshot: {os.path.join(args.screenshot_dir, f'test{args.test_number}.png')}")
        else:
            print("=" * 60)
            print("TEST COMPLETED (STEP OK, screenshot failed)")
            print("=" * 60)
    else:
        print("=" * 60)
        print("TEST COMPLETED (STEP export only)")
        print("=" * 60)
    
    print(f"STEP file: {step_file}")

if __name__ == '__main__':
    main()
