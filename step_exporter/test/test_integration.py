"""
测试：创建真实的底壳/顶壳场景，检测并导出
"""
import sys, os, shutil

script_dir = os.path.dirname(os.path.abspath(__file__))
proj_dir = os.path.dirname(script_dir)
if proj_dir not in sys.path:
    sys.path.insert(0, proj_dir)

# DLL路径
lib_dir = os.path.join(proj_dir, 'lib')
if lib_dir not in os.environ.get('PATH', ''):
    os.environ['PATH'] = lib_dir + os.pathsep + os.environ.get('PATH', '')
if hasattr(os, 'add_dll_directory') and os.path.exists(lib_dir):
    os.add_dll_directory(lib_dir)

import bpy
import step_exporter as se
import _step_exporter as cpp


def merge_step_files(output, inputs):
    """简单STEP文件合并"""
    all_data_lines = []
    
    for file_idx, fpath in enumerate(inputs):
        if not os.path.exists(fpath):
            continue
        entity_offset = file_idx * 100000
        
        with open(fpath, 'r') as f:
            content = f.read()
        
        in_data = False
        for line in content.split('\n'):
            s = line.strip()
            if s == 'DATA;':
                in_data = True
                continue
            if s == 'ENDSEC;' and in_data:
                break
            if in_data and s:
                if s.startswith('#'):
                    eq_pos = s.find('=')
                    if eq_pos > 1:
                        import re
                        old_id = int(s[1:eq_pos])
                        new_id = old_id + entity_offset
                        rest = s[eq_pos+1:]
                        new_rest = re.sub(r'#(\d+)',
                            lambda m, off=entity_offset: '#' + str(int(m.group(1)) + off),
                            rest)
                        all_data_lines.append('#' + str(new_id) + '=' + new_rest)
    
    with open(output, 'w') as f:
        f.write("ISO-10303-21;\n")
        f.write("HEADER;\n")
        f.write("FILE_DESCRIPTION(('Test Merged'),'2;1');\n")
        f.write("FILE_NAME('Test','2026-01-01',('Author'),('OCCT'),'OCCT 7.8','OCCT 7.8','Unknown');\n")
        f.write("FILE_SCHEMA(('AUTOMOTIVE_DESIGN { 1 0 10303 214 1 1 1 1 }'));\n")
        f.write("ENDSEC;\n")
        f.write("DATA;\n")
        for line in all_data_lines:
            f.write(line + '\n')
        f.write("ENDSEC;\n")
        f.write("END-ISO-10303-21;\n")
    
    return len(all_data_lines)


def main():
    print("=" * 60)
    print("Scene Detection + Parametric Export Test")
    print("=" * 60)
    
    # 清除场景
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)
    for m in list(bpy.data.meshes):
        bpy.data.meshes.remove(m)
    
    # 创建真实的底壳
    sys.path.insert(0, script_dir)
    import create_bottom_shell as cbs
    
    print("\n[1] Creating real filleted bottom shells...")
    cbs.create_filleted_bottom_shells_scene()
    
    objects = list(bpy.data.objects)
    print(f"[1] Created {len(objects)} objects:")
    for o in objects:
        nv = len(o.data.vertices) if o.type == 'MESH' else 0
        print(f"    - {o.name} ({o.type}, {nv} verts)")
    
    # 检测底壳
    print("\n[2] Detecting parametric objects...")
    bottom_shells = []
    
    for obj in bpy.data.objects:
        if obj.type != 'MESH':
            continue
        sp = se._analyze_bottom_shell_from_mesh(obj, bpy.context, 1000.0)
        if sp:
            bottom_shells.append((obj.name, sp))
            print(f"    Bottom shell: {obj.name} has_holes={sp.get('has_holes')}")
    
    print(f"[2] Results: {len(bottom_shells)} bottom shells detected")
    
    if not bottom_shells:
        print("[2] FAIL: No bottom shells detected!")
        return 1
    
    # 导出底壳（使用正确的API）
    print("\n[3] Exporting bottom shells parametrically...")
    
    temp_files = []
    for idx, (name, params) in enumerate(bottom_shells):
        has_holes = params.get('has_holes', False)
        temp_file = os.path.join(script_dir, f'test_export_temp{idx}.step')
        temp_files.append(temp_file)
        
        print(f"[3] Exporting '{name}' {'(with holes)' if has_holes else '(no holes)'}...")
        
        try:
            if has_holes:
                success = cpp.export_bottom_shell_filleted_with_holes_step(
                    temp_file,
                    params['width'], params['depth'], params['outer_height'],
                    params['bottom_thickness'], params['wall_thickness'],
                    params['corner_radius'], params['outer_fillet_radius'],
                    params['inner_fillet_radius'],
                    params.get('step_height', 1.0),
                    params.get('hole_radius', 1.5),
                    params.get('hole_offset_x', 25.0),
                    params.get('hole_offset_y', 20.0),
                    0.0, 0.0, 0.0,
                    'AP214DIS', 'MILLIMETER', 1
                )
            else:
                success = cpp.export_bottom_shell_filleted_step(
                    temp_file,
                    params['width'], params['depth'], params['outer_height'],
                    params['bottom_thickness'], params['wall_thickness'],
                    params['corner_radius'], params['outer_fillet_radius'],
                    params['inner_fillet_radius'],
                    params.get('step_height', 1.0),
                    0.0, 0.0, 0.0,
                    'AP214DIS', 'MILLIMETER', 1
                )
            
            if success:
                size = os.path.getsize(temp_file) if os.path.exists(temp_file) else 0
                with open(temp_file) as f:
                    solids = f.read().count('MANIFOLD_SOLID_BREP')
                print(f"    OK: {size} bytes, {solids} solids")
            else:
                print(f"    FAIL: C++ returned False")
        except Exception as e:
            print(f"    ERROR: {e}")
            import traceback
            traceback.print_exc()
    
    # 合并
    successful = [tf for tf in temp_files if os.path.exists(tf)]
    print(f"\n[4] Merging {len(successful)}/{len(temp_files)} temp files...")
    
    merged_file = os.path.join(script_dir, 'test_scene_merged.step')
    lines = merge_step_files(merged_file, successful)
    print(f"[4] Merged: {lines} lines")
    
    with open(merged_file) as f:
        solids = f.read().count('MANIFOLD_SOLID_BREP')
    
    print(f"\n[5] Final: {solids} solids in merged file, {os.path.getsize(merged_file)} bytes")
    
    if solids == len(successful):
        print("\n" + "=" * 60)
        print("ALL TESTS PASSED")
        return 0
    else:
        print(f"\n[5] WARNING: expected {len(successful)} solids, got {solids}")
        return 1


if __name__ == '__main__':
    sys.exit(main())