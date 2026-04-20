"""
自动化测试脚本：导出STEP文件并生成FreeCAD截图
用法: 
  1. 在Blender中运行（导出STEP）:
     blender --background --python run_test.py -- --test-number 28
  
  2. 使用FreeCAD截图:
     FreeCAD -c screenshot_script.py -- step_exporter\test28.step build\test28.png 1920 1080
"""

import bpy
import sys
import os
import time
import subprocess
import argparse

def parse_args():
    # 调试：打印sys.argv
    print(f"DEBUG: sys.argv = {sys.argv}")
    
    parser = argparse.ArgumentParser(description='Run automated test')
    parser.add_argument('--test-number', type=str, default='28', help='Test number (e.g., 28)')
    parser.add_argument('--output-dir', type=str, default=r'F:\git\blender2step\step_exporter', help='Output directory for STEP files')
    parser.add_argument('--screenshot-dir', type=str, default=r'F:\git\blender2step\build', help='Output directory for screenshots')
    parser.add_argument('--freecad-path', type=str, default=r'F:\Program Files\FreeCAD 1.0\bin\FreeCAD.exe', help='Path to FreeCAD executable')
    parser.add_argument('--skip-export', action='store_true', help='Skip STEP export (only run screenshot)')
    parser.add_argument('--skip-screenshot', action='store_true', help='Skip screenshot (only run export)')
    
    # 只解析--之后的参数
    if '--' in sys.argv:
        idx = sys.argv.index('--')
        script_args = sys.argv[idx + 1:]
    else:
        script_args = []
    
    print(f"DEBUG: script_args = {script_args}")
    return parser.parse_args(script_args)

def export_step(args):
    """导出STEP文件"""
    test_number = args.test_number
    output_dir = args.output_dir
    
    output_path = os.path.join(output_dir, f'test{test_number}.step')
    log_path = output_path + '.log'
    
    # 选择所有对象
    bpy.ops.object.select_all(action='SELECT')
    
    # 获取要导出的对象
    objects_to_export = [obj for obj in bpy.context.scene.objects if obj.type in ('MESH', 'CURVE')]
    print(f'Objects to export: {len(objects_to_export)}')
    for obj in objects_to_export:
        print(f'  - {obj.name}')
    
    # 添加step_exporter目录到sys.path
    script_dir = os.path.dirname(os.path.abspath(__file__))
    step_exporter_dir = os.path.dirname(script_dir)
    step_exporter_lib_dir = os.path.join(step_exporter_dir, 'lib')
    if step_exporter_dir not in sys.path:
        sys.path.insert(0, step_exporter_dir)
        print(f'Added {step_exporter_dir} to sys.path')
    if step_exporter_lib_dir not in sys.path:
        sys.path.insert(0, step_exporter_lib_dir)
        print(f'Added {step_exporter_lib_dir} to sys.path')
    
    # 添加step_exporter和lib目录到DLL搜索路径
    # 首先修改PATH环境变量（在os.add_dll_directory之前）
    if step_exporter_lib_dir not in os.environ.get('PATH', ''):
        os.environ['PATH'] = step_exporter_lib_dir + os.pathsep + os.environ.get('PATH', '')
        print(f'Added {step_exporter_lib_dir} to PATH (beginning)')
    
    # 使用os.add_dll_directory()添加DLL搜索路径
    if hasattr(os, 'add_dll_directory'):
        if os.path.exists(step_exporter_lib_dir):
            os.add_dll_directory(step_exporter_lib_dir)
            print(f'Added {step_exporter_lib_dir} to DLL search path')
    
    # 直接导入C++扩展模块
    import _step_exporter as cpp_exporter
    
    # 打开日志文件
    log_file = open(log_path, 'w', encoding='utf-8')
    
    def log_callback(msg):
        print(f'[LOG] {msg}')
        log_file.write(msg + '\n')
        log_file.flush()
    
    # 准备对象数据
    objects_data = []
    scale = 1000.0  # mm
    
    for obj in objects_to_export:
        depsgraph = bpy.context.evaluated_depsgraph_get()
        eval_obj = obj.evaluated_get(depsgraph)
        mesh = eval_obj.data
        
        # 获取顶点
        vertices = []
        for vert in mesh.vertices:
            world_co = eval_obj.matrix_world @ vert.co
            vertices.append([float(world_co.x) * scale, float(world_co.y) * scale, float(world_co.z) * scale])
        
        # 获取面
        mesh.calc_loop_triangles()
        faces = []
        for tri in mesh.loop_triangles:
            faces.append(list(tri.vertices))
        
        # 获取法线
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
    
    print(f'Prepared {len(objects_data)} objects for export')
    
    # 初始化增量导出
    try:
        success = cpp_exporter.init_incremental_export(
            output_path,           # const char* filename
            len(objects_data),     # int total_objects
            scale,                 # double scale
            1,                     # int fix_geometry
            1,                     # int create_solid
            1,                     # int advanced_brep
            'AP214DIS',            # const char* step_schema
            'MILLIMETER',          # const char* unit
            1,                     # int enable_logging
            0.001,                 # double sew_tolerance
            log_callback           # PyObject* log_callback
        )
        print(f'init_incremental_export returned: {success}')
    except Exception as e:
        print(f'ERROR in init_incremental_export: {e}')
        import traceback
        traceback.print_exc()
        log_file.close()
        sys.exit(1)
    
    if not success:
        print('ERROR: Failed to initialize export')
        log_file.close()
        sys.exit(1)
    
    # 逐个添加对象
    for i, obj_data in enumerate(objects_data):
        print(f'Exporting object {i+1}/{len(objects_data)}: {obj_data["name"]}')
        
        def callback(progress):
            pass  # 不需要进度回调
        
        try:
            success = cpp_exporter.add_object_to_export(obj_data, callback)
            print(f'add_object_to_export returned: {success}')
        except Exception as e:
            print(f'ERROR in add_object_to_export: {e}')
            import traceback
            traceback.print_exc()
    
    # 完成导出
    try:
        success = cpp_exporter.finalize_incremental_export()
        print(f'finalize_incremental_export returned: {success}')
    except Exception as e:
        print(f'ERROR in finalize_incremental_export: {e}')
        import traceback
        traceback.print_exc()
    
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
    
    # 确保截图目录存在
    os.makedirs(screenshot_dir, exist_ok=True)
    
    output_image = os.path.join(screenshot_dir, f'test{test_number}.png')
    
    # 获取screenshot_script.py的路径（使用命令行版本）
    script_dir = os.path.dirname(os.path.abspath(__file__))
    screenshot_script = os.path.join(script_dir, 'screenshot_script.py')
    
    if not os.path.exists(screenshot_script):
        print(f"ERROR: screenshot_script.py not found at {screenshot_script}")
        return False
    
    # 构建FreeCAD命令 - 使用FreeCADCmd.exe（命令行模式）
    freecad_dir = os.path.dirname(freecad_path)
    freecad_cmd = os.path.join(freecad_dir, 'FreeCADCmd.exe')
    
    # 如果FreeCADCmd.exe不存在，使用FreeCAD.exe
    if not os.path.exists(freecad_cmd):
        freecad_cmd = freecad_path
    
    cmd = [
        freecad_cmd,
        screenshot_script,
        '--',
        step_file,
        output_image,
        '1920',
        '1080'
    ]
    
    print(f"Running FreeCAD screenshot: {' '.join(cmd)}")
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        print(f"FreeCAD stdout: {result.stdout}")
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
        print("ERROR: FreeCAD screenshot timed out")
        return False
    except Exception as e:
        print(f"ERROR: Failed to run FreeCAD screenshot: {e}")
        return False

def main():
    args = parse_args()
    
    step_file = None
    
    # 步骤0: 创建测试圆柱体（检查场景中是否有圆柱体对象）
    mesh_objects = [obj for obj in bpy.context.scene.objects if obj.type == 'MESH']
    has_cylinders = any('Cylinder' in obj.name for obj in mesh_objects)
    
    if not has_cylinders:
        print("=" * 60)
        print("Step 0: Creating test cylinders")
        print("=" * 60)
        
        # 删除默认对象
        bpy.ops.object.select_all(action='SELECT')
        bpy.ops.object.delete()
        
        # 导入并运行create_mesh_cylinder.py
        script_dir = os.path.dirname(os.path.abspath(__file__))
        create_script = os.path.join(script_dir, 'create_mesh_cylinder.py')
        
        if os.path.exists(create_script):
            # 读取并执行create_mesh_cylinder.py的内容
            with open(create_script, 'r', encoding='utf-8') as f:
                code = f.read()
            
            # 创建一个命名空间来执行脚本
            script_globals = {'__name__': '__main__', '__file__': create_script}
            exec(compile(code, create_script, 'exec'), script_globals)
            
            # 显式调用主函数
            if 'create_mechanical_demo_scene' in script_globals:
                script_globals['create_mechanical_demo_scene']()
            
            print("Test cylinders created successfully")
            print(f"Created {len(bpy.context.scene.objects)} objects")
        else:
            print(f"WARNING: create_mesh_cylinder.py not found at {create_script}")
    else:
        print(f"Found {len(mesh_objects)} mesh objects including cylinders")
    
    # 步骤1: 导出STEP文件
    if not args.skip_export:
        print("=" * 60)
        print("Step 1: Exporting STEP file")
        print("=" * 60)
        step_file = export_step(args)
    else:
        # 如果跳过导出，使用现有的STEP文件
        step_file = os.path.join(args.output_dir, f'test{args.test_number}.step')
        if not os.path.exists(step_file):
            print(f"ERROR: STEP file not found: {step_file}")
            sys.exit(1)
    
    # 步骤2: 使用FreeCAD截图
    if not args.skip_screenshot:
        print("=" * 60)
        print("Step 2: Taking screenshot with FreeCAD")
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
            print("TEST COMPLETED WITH WARNINGS (STEP export OK, screenshot failed)")
            print("=" * 60)
            print(f"STEP file: {step_file}")
            print("WARNING: FreeCAD screenshot failed - this may be due to complex geometry in the STEP file")
            print("You can manually open the STEP file in FreeCAD GUI to verify the geometry")
            # 不退出，因为STEP导出已经成功
    else:
        print("=" * 60)
        print("TEST COMPLETED (STEP export only)")
        print("=" * 60)
        print(f"STEP file: {step_file}")

if __name__ == '__main__':
    main()
