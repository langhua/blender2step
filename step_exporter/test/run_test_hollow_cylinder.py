"""
测试螺孔圆柱的导出和截图
用法: 
  blender --background --python run_test_hollow_cylinder.py -- --test-number 59
"""

import bpy
import sys
import os
import time
import subprocess
import argparse

def parse_args():
    parser = argparse.ArgumentParser(description='Run hollow cylinder test')
    parser.add_argument('--test-number', type=str, default='59', help='Test number')
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

def create_hollow_cylinder():
    """创建螺孔圆柱"""
    # 清除场景
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)
    
    # 创建外圆柱体
    bpy.ops.mesh.primitive_cylinder_add(
        radius=25,
        depth=60,
        location=[0, 0, 0],
        vertices=64
    )
    
    outer_obj = bpy.context.active_object
    outer_obj.name = "Hollow_Cylinder_Outer"
    
    # 创建内圆柱体（孔）
    bpy.ops.mesh.primitive_cylinder_add(
        radius=10,
        depth=62,
        location=[0, 0, 0],
        vertices=64
    )
    
    inner_obj = bpy.context.active_object
    inner_obj.name = "Hole_Inner"
    
    # 使用布尔差集运算创建孔
    bpy.ops.object.select_all(action='DESELECT')
    outer_obj.select_set(True)
    bpy.context.view_layer.objects.active = outer_obj
    
    bool_mod = outer_obj.modifiers.new(name="Hole", type='BOOLEAN')
    bool_mod.operation = 'DIFFERENCE'
    bool_mod.object = inner_obj
    
    bpy.ops.object.modifier_apply(modifier=bool_mod.name)
    
    bpy.data.objects.remove(inner_obj, do_unlink=True)
    
    outer_obj.name = "Hollow_Cylinder"
    
    print(f"Created hollow cylinder: {outer_obj.name}")
    print(f"Outer radius: 25mm, Inner radius: 10mm, Height: 60mm")
    print(f"Vertices: {len(outer_obj.data.vertices)}")
    print(f"Faces: {len(outer_obj.data.polygons)}")
    
    return outer_obj

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
    
    # 添加路径（注意：step_exporter_dir必须先添加，以便优先加载新编译的pyd文件）
    script_dir = os.path.dirname(os.path.abspath(__file__))
    step_exporter_dir = os.path.dirname(script_dir)
    step_exporter_lib_dir = os.path.join(step_exporter_dir, 'lib')
    
    if step_exporter_lib_dir not in sys.path:
        sys.path.insert(0, step_exporter_lib_dir)
    if step_exporter_dir not in sys.path:
        sys.path.insert(0, step_exporter_dir)
    
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
    
    freecad_cmd = freecad_path
    freecad_dir = os.path.dirname(freecad_path)
    
    if not os.path.exists(freecad_cmd):
        print(f"ERROR: FreeCAD.exe not found at {freecad_cmd}")
        return False
    
    script_dir = os.path.dirname(os.path.abspath(__file__))
    temp_script = os.path.join(script_dir, 'test_freedcad_screenshot.py')
    
    if not os.path.exists(temp_script):
        print(f"ERROR: test_freedcad_screenshot.py not found at {temp_script}")
        return False
    
    env = os.environ.copy()
    env['STEP_FILE'] = os.path.abspath(step_file)
    env['OUTPUT_IMAGE'] = os.path.abspath(output_image)
    env['IMAGE_WIDTH'] = '1920'
    env['IMAGE_HEIGHT'] = '1080'
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
        if platform.system() == 'Windows':
            subprocess.run(['taskkill', '/F', '/IM', 'FreeCAD.exe'], capture_output=True)
        if os.path.exists(output_image):
            print(f"SUCCESS: Screenshot saved to {output_image} (after timeout)")
            return True
        return False

def main():
    args = parse_args()
    
    print("=" * 60)
    print(f"TEST {args.test_number}: Hollow Cylinder")
    print("=" * 60)
    
    print("\nStep 1: Creating hollow cylinder...")
    obj = create_hollow_cylinder()
    if not obj:
        print("ERROR: Failed to create hollow cylinder")
        sys.exit(1)
    
    print("\nStep 2: Exporting STEP...")
    step_file = export_step(args)
    
    if not args.skip_screenshot:
        print("\nStep 3: Taking screenshot with FreeCAD...")
        if not take_screenshot(args, step_file):
            print("WARNING: Screenshot failed")
            sys.exit(0)
    else:
        print("\nSkipping screenshot")
    
    print("\n" + "=" * 60)
    print(f"TEST {args.test_number} COMPLETED SUCCESSFULLY")
    print("=" * 60)
    print(f"STEP file: {step_file}")
    
    sys.exit(0)

if __name__ == "__main__":
    main()
