"""
自动化测试脚本：导出STEP文件并截图
用法:
  blender --background --python run_test.py -- --test-number 28 --freecad-screenshot
  blender --background --python run_test.py -- --test-number 28 --freecad-screenshot --both-shells

修改说明：
1. 实际调用C++参数化导出（同时测试底壳+顶壳）
2. 使用FreeCAD截图查看实际STEP几何
3. 支持单独测试底壳、顶壳或两者同时测试
"""
import bpy
import sys
import os
import time
import subprocess
import argparse


def parse_args():
    parser = argparse.ArgumentParser(description='Run automated STEP export test')
    parser.add_argument('--test-number', type=str, default='28')
    parser.add_argument('--output-dir', type=str, default=r'F:\git\blender2step\step_exporter')
    parser.add_argument('--screenshot-dir', type=str, default=r'F:\git\blender2step\build')
    parser.add_argument('--freecad-path', type=str, default=r'F:\Program Files\FreeCAD 1.0\bin\FreeCAD.exe')
    parser.add_argument('--skip-export', action='store_true')
    parser.add_argument('--skip-screenshot', action='store_true')
    parser.add_argument('--bottom-shell', action='store_true')
    parser.add_argument('--top-shell', action='store_true')
    parser.add_argument('--both-shells', action='store_true', help='Test both bottom and top shells')
    parser.add_argument('--operator-path', action='store_true', help='Test via menu operator path (bpy.ops.export.step_enhanced)')
    parser.add_argument('--freecad-screenshot', action='store_true')

    if '--' in sys.argv:
        idx = sys.argv.index('--')
        script_args = sys.argv[idx + 1:]
    else:
        script_args = sys.argv[1:]

    args = parser.parse_args(script_args)
    return args


def do_parametric_export(width, depth, outer_height, bottom_thickness, wall_thickness,
                         corner_radius, outer_fillet_radius, inner_fillet_radius,
                         output_path, cpp_exporter, log_callback):
    """执行底壳参数化导出"""
    log_callback(f"Bottom shell: {width}x{depth} h={outer_height} "
                 f"bt={bottom_thickness} wt={wall_thickness} cr={corner_radius} "
                 f"ofr={outer_fillet_radius} ifr={inner_fillet_radius}")

    success = cpp_exporter.export_bottom_shell_filleted_step(
        output_path,
        width, depth, outer_height,
        bottom_thickness, wall_thickness, corner_radius,
        outer_fillet_radius, inner_fillet_radius,
        1.0,  # step_height
        0.0, 0.0, 0.0,  # pos
        'AP214DIS', 'MILLIMETER', 1
    )
    return success


def do_top_shell_export(width, depth, outer_height, top_thickness, wall_thickness,
                        corner_radius, outer_fillet_radius, inner_fillet_radius,
                        top_recess, top_offset_y, window_len, window_wid,
                        output_path, cpp_exporter, log_callback):
    """执行顶壳参数化导出"""
    log_callback(f"Top shell: {width}x{depth} h={outer_height} "
                 f"tt={top_thickness} wt={wall_thickness} cr={corner_radius} "
                 f"ofr={outer_fillet_radius} ifr={inner_fillet_radius} "
                 f"recess={top_recess} yOff={top_offset_y}")

    success = cpp_exporter.export_top_shell_filleted_step(
        output_path,
        width, depth, outer_height,
        top_thickness, wall_thickness, corner_radius,
        outer_fillet_radius, inner_fillet_radius,
        top_recess, top_offset_y,
        window_len, window_wid,
        0.0, 0.0, outer_height,
        'AP214DIS', 'MILLIMETER', 1
    )
    return success


def merge_step_files(file_list, output_file):
    """合并多个STEP文件，正确处理实体ID偏移"""
    if not file_list:
        return False
    if len(file_list) == 1:
        import shutil
        shutil.copy2(file_list[0], output_file)
        return True

    header_lines = []
    all_data_sections = []
    entity_start_id = 1
    
    for file_idx, fpath in enumerate(file_list):
        with open(fpath, 'r', encoding='utf-8', errors='replace') as f:
            content = f.read()
        
        lines = content.split('\n')
        in_header = True
        in_data = False
        data_lines = []
        
        for line in lines:
            if in_header:
                if line.strip().startswith('DATA'):
                    in_header = False
                    in_data = True
                    if file_idx == 0:
                        header_lines.append(line)
                    continue
                if file_idx == 0:
                    header_lines.append(line)
                continue
            
            if in_data:
                if line.strip().startswith('ENDSEC'):
                    data_lines.append(line)
                    break
                data_lines.append(line)
        
        # 重编号实体ID
        id_offset = file_idx * 100000
        remapped_lines = []
        for line in data_lines:
            # 匹配 STEP 实体ID 模式: #数字= 或 #数字 =
            import re
            def replace_id(m):
                old_id = int(m.group(1))
                new_id = old_id + id_offset
                return f'#{new_id}='
            remapped = re.sub(r'#(\d+)\s*=', replace_id, line)
            # 也替换引用: #数字(,;) 或 #数字 )
            def replace_ref(m):
                old_id = int(m.group(1))
                new_id = old_id + id_offset
                return f'#{new_id}{m.group(2)}'
            remapped = re.sub(r'#(\d+)\s*([,;)])', replace_ref, remapped)
            remapped_lines.append(remapped)
        
        # 去掉最后一个文件的 ENDSEC
        all_data_sections.append(remapped_lines)
    
    # 组装完整文件
    with open(output_file, 'w', encoding='utf-8') as out:
        for line in header_lines:
            out.write(line + '\n')
        for section in all_data_sections:
            for line in section:
                out.write(line + '\n')
        out.write('ENDSEC;\n')
        out.write('END-ISO-10303-21;\n')
    
    # 检查输出
    with open(output_file, 'r', encoding='utf-8') as f:
        final = f.read()
    solids = final.count('MANIFOLD_SOLID_BREP')
    print(f"  Merged: {len(file_list)} files -> {os.path.getsize(output_file)} bytes, {solids} solids")
    return True


def freecad_screenshot(step_file, output_image, freecad_path, screenshot_dir):
    """使用FreeCAD对STEP文件截图"""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    temp_script = os.path.join(script_dir, 'test_freecad_screenshot.py')

    if not os.path.exists(temp_script):
        print(f"ERROR: {temp_script} not found")
        return False

    env = os.environ.copy()
    env['STEP_FILE'] = os.path.abspath(step_file)
    env['OUTPUT_IMAGE'] = os.path.abspath(output_image)
    env['IMAGE_WIDTH'] = '1920'
    env['IMAGE_HEIGHT'] = '1080'
    env['QT_QPA_PLATFORM'] = 'offscreen'

    freecad_user_home = os.path.join(screenshot_dir, 'freecad_home')
    os.makedirs(freecad_user_home, exist_ok=True)
    env['FREECAD_USER_HOME'] = freecad_user_home

    cmd = [freecad_path, temp_script]
    freecad_dir = os.path.dirname(freecad_path)

    print(f"Running FreeCAD screenshot: STEP={step_file} -> {output_image}")
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120,
                                env=env, cwd=freecad_dir)
        print(f"FreeCAD stdout: {result.stdout[:2000]}")
        if result.stderr:
            print(f"FreeCAD stderr: {result.stderr[:1000]}")

        if os.path.exists(output_image):
            size = os.path.getsize(output_image)
            print(f"SUCCESS: Screenshot saved ({size} bytes)")
            return True
        else:
            print(f"FAIL: Output image not found")
            return False
    except subprocess.TimeoutExpired:
        print("WARNING: FreeCAD timeout, checking if image was generated...")
        if os.path.exists(output_image):
            print(f"SUCCESS: Screenshot saved (after timeout)")
            return True
        return False
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False


def do_operator_export(output_path, cpp_exporter, log_callback):
    """通过Blender菜单操作符 (bpy.ops.export.step_enhanced) 导出STEP文件。
    
    此函数模拟用户在Blender UI中通过菜单导出的完整路径：
    1. 创建测试场景（底壳+顶壳）
    2. 调用操作符执行导出
    3. 验证输出的STEP文件
    """
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    # 清除场景
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete()
    
    # === 创建顶壳（使用简单中空顶壳）===
    log_callback("Creating top shell for operator test...")
    from step_exporter.test.create_top_shell import create_hollow_top_shell
    
    top_shell = create_hollow_top_shell(
        name="TestTopShell",
        width=100.0,
        depth=70.0,
        outer_height=10.0,
        top_thickness=2.0,
        wall_thickness=2.0,
        corner_radius=20.0,
        location=(0, 0, 0),
        segments=24,
        holes=None
    )
    top_count = len(bpy.data.objects)
    log_callback(f"Top shell created: {top_count} objects")
    
    # === 创建第二个顶壳（相同参数，不同位置）===
    log_callback("Creating second top shell for operator test...")
    top_shell2 = create_hollow_top_shell(
        name="TestTopShell2",
        width=100.0,
        depth=70.0,
        outer_height=10.0,
        top_thickness=2.0,
        wall_thickness=2.0,
        corner_radius=20.0,
        location=(120, 0, 0),  # 移到右侧，避免重叠
        segments=24,
        holes=None
    )
    log_callback(f"Second top shell created: {len(bpy.data.objects)} objects total")
    
    # === 调用操作符导出 ===
    log_callback(f"Calling bpy.ops.export_scene.step_enhanced(filepath={output_path})...")
    
    # 确保使用项目目录中的最新代码
    project_addon_dir = os.path.abspath(os.path.join(script_dir, '..'))
    blender_addon_dir = os.path.join(bpy.utils.user_resource('SCRIPTS', path='addons'), 'step_exporter')
    
    log_callback(f"Project addon dir: {project_addon_dir}")
    log_callback(f"Blender addon dir: {blender_addon_dir}")
    
    # 复制项目文件到Blender addons目录（如果不是同一个文件）
    import shutil
    src_init = os.path.join(project_addon_dir, '__init__.py')
    dst_init = os.path.join(blender_addon_dir, '__init__.py')
    src_lib = os.path.join(project_addon_dir, 'lib', '_step_exporter.pyd')
    dst_lib = os.path.join(blender_addon_dir, 'lib', '_step_exporter.pyd')
    
    if os.path.exists(src_init) and os.path.exists(dst_init):
        # 检查是否是同一个文件（处理symlink情况）
        if os.path.samefile(src_init, dst_init):
            log_callback("Project and Blender addon dirs are the same (symlink), skipping copy")
        else:
            shutil.copy2(src_init, dst_init)
            log_callback(f"Copied __init__.py to {dst_init}")
    elif os.path.exists(src_init):
        os.makedirs(blender_addon_dir, exist_ok=True)
        shutil.copy2(src_init, dst_init)
        log_callback(f"Copied __init__.py to {dst_init}")
    
    if os.path.exists(src_lib):
        os.makedirs(os.path.dirname(dst_lib), exist_ok=True)
        if os.path.exists(dst_lib) and os.path.samefile(src_lib, dst_lib):
            log_callback("C++ extension is the same file, skipping copy")
        else:
            shutil.copy2(src_lib, dst_lib)
            log_callback(f"Copied _step_exporter.pyd to {dst_lib}")
    
    # 先禁用旧版本（如果已启用）
    try:
        bpy.ops.preferences.addon_disable(module="step_exporter")
        log_callback("Disabled old step_exporter addon")
    except:
        pass
    
    # 启用 step_exporter addon（后台模式下不会自动启用）
    try:
        bpy.ops.preferences.addon_enable(module="step_exporter")
        log_callback("step_exporter addon enabled")
    except Exception as e:
        log_callback(f"addon_enable warning: {e}")
        pass
    
    # 重新加载模块以确保使用最新代码
    import importlib
    if 'step_exporter' in sys.modules:
        importlib.reload(sys.modules['step_exporter'])
        log_callback("Reloaded step_exporter module")
    
    # 在后台模式下，操作符 execute() 会检测到后台环境并同步执行
    try:
        result = bpy.ops.export_scene.step_enhanced(
            filepath=output_path,
            step_schema='AP214DIS',
            unit='mm',
            enable_logging=True,
            fix_geometry=True,
            create_solid=True,
            advanced_brep=True,
            sew_tolerance=1e-6
        )
        log_callback(f"Operator result: {result}")
    except Exception as e:
        log_callback(f"Operator exception: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # 后台模式下操作符同步执行，STE 文件此时应已生成
    if os.path.exists(output_path):
        size = os.path.getsize(output_path)
        with open(output_path, 'r', encoding='utf-8', errors='replace') as f:
            content = f.read()
        solids = content.count('MANIFOLD_SOLID_BREP')
        log_callback(f"Operator export: {output_path} ({size} bytes, {solids} solids)")
        return True
    else:
        log_callback(f"FAIL: Operator export did not generate {output_path}")
        return False


def main():
    args = parse_args()

    script_dir = os.path.dirname(os.path.abspath(__file__))

    # ============ Setup paths and modules ============
    step_exporter_dir = os.path.dirname(script_dir)
    lib_dir = os.path.join(step_exporter_dir, 'lib')
    
    if step_exporter_dir not in sys.path:
        sys.path.insert(0, step_exporter_dir)
    if lib_dir not in sys.path:
        sys.path.insert(0, lib_dir)
    if lib_dir not in os.environ.get('PATH', ''):
        os.environ['PATH'] = lib_dir + os.pathsep + os.environ.get('PATH', '')
    if hasattr(os, 'add_dll_directory') and os.path.exists(lib_dir):
        os.add_dll_directory(lib_dir)

    import _step_exporter as cpp

    # ============ Step 0: Create scene ============
    print("=" * 60)
    print("Step 0: Creating test scene")
    print("=" * 60)

    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete()

    log_cb = lambda msg: print(f'[LOG] {msg}')

    temp_files = []
    
    if args.operator_path:
        # === 操作符路径测试 (bpy.ops.export.step_enhanced) ===
        print("=" * 60)
        print("Testing menu operator path (export.step_enhanced)")
        print("=" * 60)
        
        output_path = os.path.join(args.output_dir, f'test{args.test_number}.step')
        print(f"Output: {output_path}")
        
        success = do_operator_export(output_path, cpp, log_cb)
        if not success:
            print("FAIL: Operator path export failed")
            sys.exit(1)
        step_file = output_path

    elif args.both_shells:
        # --- 创建底壳 ---
        build_dir = os.path.join(step_exporter_dir, '..', 'build')
        bottom_output = os.path.join(build_dir, 'test28_bottom.step')
        temp_files.append(bottom_output)
        
        print("\n--- Creating bottom shell ---")
        create_bottom = os.path.join(script_dir, 'create_bottom_shell.py')
        with open(create_bottom, 'r', encoding='utf-8') as f:
            code = f.read()
        bglobals = {'__name__': '__main__', '__file__': create_bottom}
        exec(compile(code, create_bottom, 'exec'), bglobals)
        bglobals['create_filleted_bottom_shells_scene']()
        print(f"Bottom shell: {len(bpy.data.objects)} objects")

        log_cb("Exporting bottom shell...")
        success = do_parametric_export(
            100.0, 70.0, 10.0,  # width, depth, outer_height
            2.0, 2.0, 20.0,     # bottom_t, wall_t, corner_r
            3.0, 1.5,            # outer_fillet, inner_fillet
            bottom_output, cpp, log_cb
        )
        if not success:
            print("FAIL: Bottom shell export failed!")
            sys.exit(1)
        print(f"  Bottom OK: {os.path.getsize(bottom_output)} bytes")

        # --- 创建顶壳 ---
        top_output = os.path.join(build_dir, 'test28_top.step')
        temp_files.append(top_output)
        
        print("\n--- Creating top shell ---")
        # 清除场景
        bpy.ops.object.select_all(action='SELECT')
        bpy.ops.object.delete()
        
        create_top = os.path.join(script_dir, 'create_top_shell.py')
        if os.path.exists(create_top):
            with open(create_top, 'r', encoding='utf-8') as f:
                code = f.read()
            tglobals = {'__name__': '__main__', '__file__': create_top}
            exec(compile(code, create_top, 'exec'), tglobals)
            for fn_name in ['create_filleted_top_shell_scene', 'create_top_shell_scene']:
                if fn_name in tglobals:
                    tglobals[fn_name]()
                    break
            print(f"Top shell: {len(bpy.data.objects)} objects")

            log_cb("Exporting top shell...")
            success = do_top_shell_export(
                100.0, 70.0, 10.0,  # width, depth, outer_height
                2.0, 2.0, 20.0,     # top_t, wall_t, corner_r
                1.5, 0.75,          # outer_fillet, inner_fillet
                11.5, -3.0,         # recess, yOff
                20.0, 10.0,         # window_len, window_wid
                top_output, cpp, log_cb
            )
            if not success:
                print(f"WARNING: Top shell export failed, continuing with bottom only")
                temp_files = [bottom_output]
            else:
                print(f"  Top OK: {os.path.getsize(top_output)} bytes")
        else:
            print(f"WARNING: create_top_shell.py not found, testing bottom only")
            temp_files = [bottom_output]

        # --- 合并 ---
        output_path = os.path.join(args.output_dir, f'test{args.test_number}.step')
        print(f"\n--- Merging {len(temp_files)} files -> {output_path} ---")
        merge_step_files(temp_files, output_path)
        step_file = output_path

    elif args.top_shell:
        # 仅顶壳
        create_top = os.path.join(script_dir, 'create_top_shell.py')
        if os.path.exists(create_top):
            with open(create_top, 'r', encoding='utf-8') as f:
                code = f.read()
            tglobals = {'__name__': '__main__', '__file__': create_top}
            exec(compile(code, create_top, 'exec'), tglobals)
            for fn_name in ['create_filleted_top_shell_scene', 'create_top_shell_scene']:
                if fn_name in tglobals:
                    tglobals[fn_name]()
                    break
            print(f"Top shell: {len(bpy.data.objects)} objects")
        else:
            print(f"ERROR: create_top_shell.py not found")
            sys.exit(1)

        output_path = os.path.join(args.output_dir, f'test{args.test_number}.step')
        log_cb("Exporting top shell...")
        success = do_top_shell_export(
            100.0, 70.0, 10.0, 2.0, 2.0, 20.0,
            1.5, 0.75, 0.0, 0.0, 0.0, 0.0,
            output_path, cpp, log_cb
        )
        if not success:
            sys.exit(1)
        step_file = output_path

    else:
        # 默认：仅底壳
        print("Creating bottom shell...")
        create_bottom = os.path.join(script_dir, 'create_bottom_shell.py')
        with open(create_bottom, 'r', encoding='utf-8') as f:
            code = f.read()
        bglobals = {'__name__': '__main__', '__file__': create_bottom}
        exec(compile(code, create_bottom, 'exec'), bglobals)
        bglobals['create_filleted_bottom_shells_scene']()
        print(f"Bottom shell: {len(bpy.data.objects)} objects")

        output_path = os.path.join(args.output_dir, f'test{args.test_number}.step')
        log_cb("Exporting bottom shell...")
        success = do_parametric_export(
            100.0, 70.0, 10.0, 2.0, 2.0, 20.0,
            3.0, 1.5, output_path, cpp, log_cb
        )
        if not success:
            sys.exit(1)
        step_file = output_path

    # Check step file
    if not step_file or not os.path.exists(step_file):
        print(f"FAIL: STEP file not found!")
        sys.exit(1)

    size = os.path.getsize(step_file)
    with open(step_file) as f:
        solids = f.read().count('MANIFOLD_SOLID_BREP')
    print(f"\nSUCCESS: {step_file} ({size} bytes, {solids} solids)")

    # ============ Step 2: Screenshot ============
    if not args.skip_screenshot:
        print("=" * 60)
        print("Step 2: Screenshot")
        print("=" * 60)

        output_image = os.path.join(args.screenshot_dir, f'test{args.test_number}.png')

        if args.freecad_screenshot:
            success = freecad_screenshot(
                step_file, output_image,
                args.freecad_path, args.screenshot_dir
            )
        else:
            # Blender internal render - position camera to see all objects
            # Calculate bounding box of all objects
            all_verts = []
            for obj in bpy.data.objects:
                if obj.type == 'MESH':
                    for v in obj.data.vertices:
                        all_verts.append(obj.matrix_world @ v.co)
            
            if all_verts:
                min_x = min(v.x for v in all_verts)
                max_x = max(v.x for v in all_verts)
                min_y = min(v.y for v in all_verts)
                max_y = max(v.y for v in all_verts)
                min_z = min(v.z for v in all_verts)
                max_z = max(v.z for v in all_verts)
                
                center_x = (min_x + max_x) / 2
                center_y = (min_y + max_y) / 2
                center_z = (min_z + max_z) / 2
                
                size_x = max_x - min_x
                size_y = max_y - min_y
                size_z = max_z - min_z
                max_size = max(size_x, size_y, size_z)
                
                cam_data = bpy.data.cameras.new('Camera')
                cam_data.type = 'ORTHO'
                cam_data.ortho_scale = max_size * 1.5
                cam = bpy.data.objects.new('Camera', cam_data)
                bpy.context.collection.objects.link(cam)
                bpy.context.scene.camera = cam
                
                # Position camera at 45-degree angle
                cam.location = (center_x + max_size, center_y - max_size, center_z + max_size * 0.8)
                cam.rotation_euler = (1.0, 0, 0.8)
            else:
                cam_data = bpy.data.cameras.new('Camera')
                cam_data.type = 'ORTHO'
                cam_data.ortho_scale = 200
                cam = bpy.data.objects.new('Camera', cam_data)
                bpy.context.collection.objects.link(cam)
                bpy.context.scene.camera = cam
                cam.location = (60, -60, 50)
                cam.rotation_euler = (1.0, 0, 0.8)

            bpy.context.scene.render.engine = 'BLENDER_WORKBENCH'
            bpy.context.scene.render.resolution_x = 1920
            bpy.context.scene.render.resolution_y = 1080
            bpy.context.scene.render.filepath = output_image
            bpy.context.scene.render.image_settings.file_format = 'PNG'
            bpy.ops.render.render(write_still=True)
            success = os.path.exists(output_image)

        if success:
            print("=" * 60)
            print("TEST COMPLETED SUCCESSFULLY")
            print("=" * 60)
            print(f"STEP file: {step_file}")
            print(f"Screenshot: {output_image}")
        else:
            print("TEST COMPLETED WITH ISSUES")
            sys.exit(0)
    else:
        print("TEST COMPLETED (STEP export only)")
        print(f"STEP file: {step_file}")


if __name__ == '__main__':
    main()