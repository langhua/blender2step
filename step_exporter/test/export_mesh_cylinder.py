import bpy
import sys
import os
import time
import argparse

def parse_args():
    parser = argparse.ArgumentParser(description='Export mesh cylinders to STEP')
    parser.add_argument('--test-number', type=str, default='28', help='Test number (e.g., 28)')
    parser.add_argument('--output-dir', type=str, default=r'F:\git\blender2step\step_exporter', help='Output directory')
    return parser.parse_known_args()[0]

def main():
    args = parse_args()
    
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
    
    # 初始化增量导出 - 注意参数顺序和类型
    # C++签名: "sid|iiissidO" -> (str, int, double, int, int, int, str, str, int, double, callable)
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

if __name__ == '__main__':
    main()
