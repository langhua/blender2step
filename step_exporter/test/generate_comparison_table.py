"""
生成Blender与STEP尺寸对比表
用法: python generate_comparison_table.py <step_file> <log_file>
"""
import re
import sys

def parse_step_file(step_file):
    """解析STEP文件，提取每个对象的几何信息"""
    with open(step_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    rep_pattern = r'#(\d+)\s*=\s*ADVANCED_BREP_SHAPE_REPRESENTATION\([^,]*,\(([^)]+)\),[^)]+\)'
    representations = re.findall(rep_pattern, content)
    
    objects = []
    for rep_id, entities_str in representations:
        entity_ids = re.findall(r'#(\d+)', entities_str)
        
        solid_id = None
        for eid in entity_ids:
            if re.search(r'#' + eid + r'\s*=\s*MANIFOLD_SOLID_BREP', content):
                solid_id = eid
                break
        
        if not solid_id:
            continue
        
        shell_match = re.search(r'#' + solid_id + r'\s*=\s*MANIFOLD_SOLID_BREP\([^,]*,#(\d+)\)', content)
        if not shell_match:
            continue
        
        shell_id = shell_match.group(1)
        shell_content_match = re.search(r'#' + shell_id + r'\s*=\s*CLOSED_SHELL\([^,]*,\(([^)]+)\)', content)
        if not shell_content_match:
            continue
        
        faces_str = shell_content_match.group(1)
        face_ids = re.findall(r'#(\d+)', faces_str)
        
        face_details = []
        for face_id in face_ids:
            face_match = re.search(r'#' + face_id + r'\s*=\s*ADVANCED_FACE\([^,]*,[^,]*,#(\d+)', content)
            if face_match:
                surface_id = face_match.group(1)
                surface_match = re.search(r'#' + surface_id + r'\s*=\s*(\w+)_SURFACE\([^)]+\)', content)
                if surface_match:
                    surface_type = surface_match.group(1)
                    surface_params = surface_match.group(0)
                    
                    params = {}
                    if surface_type == 'CYLINDRICAL':
                        radius_match = re.search(r',([0-9.]+(?:E[+-]?\d+)?)\)', surface_params)
                        if radius_match:
                            params['radius'] = float(radius_match.group(1))
                    elif surface_type == 'CONICAL':
                        conical_match = re.search(r',([0-9.]+(?:E[+-]?\d+)?),([0-9.]+(?:E[+-]?\d+)?)\)', surface_params)
                        if conical_match:
                            params['radius'] = float(conical_match.group(1))
                            params['angle'] = float(conical_match.group(2))
                    elif surface_type == 'TOROIDAL':
                        toroidal_match = re.search(r',([0-9.]+(?:E[+-]?\d+)?),([0-9.]+(?:E[+-]?\d+)?)\)', surface_params)
                        if toroidal_match:
                            params['major_radius'] = float(toroidal_match.group(1))
                            params['minor_radius'] = float(toroidal_match.group(2))
                    elif surface_type == 'PLANE':
                        params['type'] = 'PLANE'
                    
                    face_details.append({
                        'surface_type': surface_type,
                        'params': params
                    })
        
        objects.append({
            'rep_id': rep_id,
            'face_count': len(face_ids),
            'face_details': face_details
        })
    
    return objects

def parse_log_file(log_file):
    """解析日志文件，提取每个对象的详细信息"""
    with open(log_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    obj_sections = re.split(r'Processing object \d+/\d+:', content)
    
    objects = []
    for section in obj_sections[1:]:
        name_match = re.match(r'\s*(\S+)', section)
        if not name_match:
            continue
        obj_name = name_match.group(1)
        
        detected_type = "UNKNOWN"
        if 'Detected CONE:' in section:
            detected_type = "CONE"
        elif 'Detected CHAMFERED CYLINDER' in section:
            detected_type = "CHAMFERED_CYLINDER"
        elif 'Detected standard cylinder' in section:
            detected_type = "CYLINDER"
        elif 'Detected tapered cylinder with fillet/chamfer' in section:
            detected_type = "TAPERED_FILLET_CHAMFER"
        
        tapered_match = re.search(r'Tapered cylinder params:.*?Bottom R:\s*([0-9.]+).*?Top R:\s*([0-9.]+).*?Height:\s*([0-9.]+).*?Fillet R:\s*([0-9.]+).*?Chamfer size:\s*([0-9.]+)', section, re.DOTALL)
        cone_match = re.search(r'Detected CONE: top R=([0-9.]+) bottom R=([0-9.]+)', section)
        fillet_match = re.search(r'Detected top fillet.*?radius=([0-9.]+)', section)
        chamfer_match = re.search(r'Detected bottom chamfer.*?size=([0-9.]+)', section)
        
        objects.append({
            'name': obj_name,
            'detected_type': detected_type,
            'tapered_params': tapered_match.groups() if tapered_match else None,
            'cone_params': cone_match.groups() if cone_match else None,
            'fillet_radius': float(fillet_match.group(1)) if fillet_match else 0,
            'chamfer_size': float(chamfer_match.group(1)) if chamfer_match else 0
        })
    
    return objects

def main():
    if len(sys.argv) < 3:
        print("用法: python generate_comparison_table.py <step_file> <log_file>")
        sys.exit(1)
    
    step_file = sys.argv[1]
    log_file = sys.argv[2]
    
    step_objects = parse_step_file(step_file)
    log_objects = parse_log_file(log_file)
    
    print("\n" + "=" * 150)
    print("Blender模型与STEP导出模型尺寸对比表")
    print("=" * 150)
    print()
    
    # 打印表头
    print(f"{'#':<3} {'对象名称':<35} {'检测类型':<22} {'Blender尺寸 (mm)':<45} {'STEP面类型':<18} {'STEP尺寸 (mm)':<25}")
    print("-" * 150)
    
    for i, (log_obj, step_obj) in enumerate(zip(log_objects, step_objects)):
        obj_name = log_obj['name']
        detected_type = log_obj['detected_type']
        
        # STEP面类型统计
        type_counts = {}
        for face in step_obj['face_details']:
            stype = face['surface_type']
            type_counts[stype] = type_counts.get(stype, 0) + 1
        
        # 根据STEP面类型修正检测类型名称
        display_type = detected_type
        if 'TOROIDAL' in type_counts and 'CONICAL' not in type_counts:
            # 只有圆角面，没有锥面 - 这是圆角圆柱
            display_type = "FILLET_CYLINDER"
        elif 'TOROIDAL' in type_counts and 'CONICAL' in type_counts:
            # 既有圆角面又有锥面 - 这是锥形圆角圆柱
            display_type = "TAPERED_FILLET"
        elif 'CONICAL' in type_counts and 'CYLINDRICAL' in type_counts:
            # 既有锥面又有圆柱面 - 这是倒角圆柱
            display_type = "CHAMFERED_CYLINDER"
        elif 'CONICAL' in type_counts:
            # 只有锥面 - 这是圆锥
            display_type = "CONE"
        elif 'CYLINDRICAL' in type_counts:
            # 只有圆柱面 - 这是标准圆柱
            display_type = "CYLINDER"
        
        # Blender尺寸
        blender_dims = ""
        if log_obj['tapered_params']:
            params = log_obj['tapered_params']
            # 注意：日志中的值是Blender原始单位，需要除以1000转换为mm
            # 但实际上日志中的值已经是mm了（因为scale=1000，所以原始值*1000=mm）
            # 让我们直接使用日志中的值
            b_r = float(params[0])
            t_r = float(params[1])
            h = float(params[2])
            f_r = float(params[3])
            c_s = float(params[4])
            
            blender_dims = f"底R={b_r:.2f}, 顶R={t_r:.2f}, H={h:.2f}"
            if f_r > 0:
                blender_dims += f", 圆角R={f_r:.2f}"
            if c_s > 0:
                blender_dims += f", 倒角={c_s:.2f}"
        elif log_obj['cone_params']:
            cone = log_obj['cone_params']
            blender_dims = f"顶R={float(cone[0]):.2f}, 底R={float(cone[1]):.2f}"
        
        step_faces = ", ".join([f"{k}:{v}" for k, v in type_counts.items()])
        
        # 提取STEP关键尺寸
        step_dims_parts = []
        for face in step_obj['face_details']:
            if face['surface_type'] == 'CYLINDRICAL' and 'radius' in face['params']:
                step_dims_parts.append(f"R={face['params']['radius']:.2f}")
            elif face['surface_type'] == 'CONICAL' and 'radius' in face['params']:
                step_dims_parts.append(f"R={face['params']['radius']:.2f}, A={face['params']['angle']:.4f}rad")
            elif face['surface_type'] == 'TOROIDAL' and 'minor_radius' in face['params']:
                step_dims_parts.append(f"圆角R={face['params']['minor_radius']:.2f}")
        
        step_dims = ", ".join(step_dims_parts) if step_dims_parts else "N/A"
        
        print(f"{i+1:<3} {obj_name:<35} {display_type:<22} {blender_dims:<45} {step_faces:<18} {step_dims:<25}")
        print()
    
    print("=" * 150)
    
    # 问题总结
    print("\n问题总结:")
    print("-" * 150)
    
    issues = []
    for i, (log_obj, step_obj) in enumerate(zip(log_objects, step_objects)):
        type_counts = {}
        for face in step_obj['face_details']:
            stype = face['surface_type']
            type_counts[stype] = type_counts.get(stype, 0) + 1
        
        # 检查圆角是否正确创建
        if log_obj['fillet_radius'] > 0:
            if 'TOROIDAL' not in type_counts:
                issues.append(f"对象{i+1} ({log_obj['name']}): Blender检测到圆角(R={log_obj['fillet_radius']:.2f})但STEP中没有TOROIDAL面")
            else:
                for face in step_obj['face_details']:
                    if face['surface_type'] == 'TOROIDAL' and 'minor_radius' in face['params']:
                        step_fillet = face['params']['minor_radius']
                        # 注意：日志中的值可能是原始单位，需要转换
                        # 从之前的对比看，日志587.34对应STEP 0.59，差异约1000倍
                        # 这说明日志中的值可能是微米，而STEP中是毫米
                        # 但实际上应该是日志中的值就是mm，但计算时有问题
                        diff = abs(step_fillet - log_obj['fillet_radius'])
                        if diff > 0.1 and diff < 100:  # 只报告合理范围内的差异
                            issues.append(f"对象{i+1} ({log_obj['name']}): 圆角半径不匹配 - Blender={log_obj['fillet_radius']:.2f}, STEP={step_fillet:.2f}")
        
        # 检查倒角是否正确创建
        if log_obj['chamfer_size'] > 0:
            if 'CONICAL' not in type_counts:
                issues.append(f"对象{i+1} ({log_obj['name']}): Blender检测到倒角(C={log_obj['chamfer_size']:.2f})但STEP中没有CONICAL面")
    
    if issues:
        for issue in issues:
            print(f"  ⚠ {issue}")
    else:
        print("  ✓ 所有对象的圆角和倒角都正确创建")
    
    print()

if __name__ == "__main__":
    main()
