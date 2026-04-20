"""
对比Blender模型与STEP导出模型的尺寸差异 - 改进版
用法: python compare_dimensions_v2.py <step_file> <log_file>
"""
import re
import sys

def parse_step_file(step_file):
    """解析STEP文件，提取每个对象的几何信息"""
    with open(step_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 查找所有ADVANCED_BREP_SHAPE_REPRESENTATION
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
        
        # 分析每个面的类型和几何参数
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
    
    # 分割每个对象的处理日志
    obj_sections = re.split(r'Processing object \d+/\d+:', content)
    
    objects = []
    for i, section in enumerate(obj_sections[1:], 1):  # 跳过第一个空段
        # 提取对象名称
        name_match = re.match(r'\s*(\S+)', section)
        if not name_match:
            continue
        obj_name = name_match.group(1)
        
        # 提取检测类型
        detected_type = "UNKNOWN"
        if 'Detected CONE:' in section:
            detected_type = "CONE"
        elif 'Detected CHAMFERED CYLINDER' in section:
            detected_type = "CHAMFERED_CYLINDER"
        elif 'Detected standard cylinder' in section:
            detected_type = "CYLINDER"
        elif 'Detected tapered cylinder with fillet/chamfer' in section:
            detected_type = "TAPERED_FILLET_CHAMFER"
        
        # 提取Tapered cylinder params
        tapered_match = re.search(r'Tapered cylinder params:.*?Bottom R:\s*([0-9.]+).*?Top R:\s*([0-9.]+).*?Height:\s*([0-9.]+).*?Fillet R:\s*([0-9.]+).*?Chamfer size:\s*([0-9.]+)', section, re.DOTALL)
        
        # 提取CONE参数
        cone_match = re.search(r'Detected CONE: top R=([0-9.]+) bottom R=([0-9.]+)', section)
        
        # 提取圆角
        fillet_match = re.search(r'Detected top fillet.*?radius=([0-9.]+)', section)
        
        # 提取倒角
        chamfer_match = re.search(r'Detected bottom chamfer.*?size=([0-9.]+)', section)
        
        objects.append({
            'name': obj_name,
            'detected_type': detected_type,
            'tapered_params': tapered_match.groups() if tapered_match else None,
            'cone_params': cone_match.groups() if cone_match else None,
            'fillet_radius': float(fillet_match.group(1)) if fillet_match else None,
            'chamfer_size': float(chamfer_match.group(1)) if chamfer_match else None
        })
    
    return objects

def main():
    if len(sys.argv) < 3:
        print("用法: python compare_dimensions_v2.py <step_file> <log_file>")
        sys.exit(1)
    
    step_file = sys.argv[1]
    log_file = sys.argv[2]
    
    step_objects = parse_step_file(step_file)
    log_objects = parse_log_file(log_file)
    
    print("=" * 120)
    print("Blender模型与STEP导出模型尺寸对比表")
    print("=" * 120)
    print()
    
    # 打印表头
    print(f"{'#':<3} {'对象名称':<35} {'检测类型':<25} {'Blender尺寸(mm)':<30} {'STEP面类型':<25}")
    print("-" * 120)
    
    for i, (log_obj, step_obj) in enumerate(zip(log_objects, step_objects)):
        obj_name = log_obj['name']
        detected_type = log_obj['detected_type']
        
        # Blender尺寸
        blender_dims = ""
        if log_obj['tapered_params']:
            params = log_obj['tapered_params']
            blender_dims = f"B={params[0]}, T={params[1]}, H={params[2]}"
            if float(params[3]) > 0:
                blender_dims += f", F={params[3]}"
            if float(params[4]) > 0:
                blender_dims += f", C={params[4]}"
        elif log_obj['cone_params']:
            cone = log_obj['cone_params']
            blender_dims = f"Top={cone[0]}, Bot={cone[1]}"
        
        # STEP面类型统计
        type_counts = {}
        for face in step_obj['face_details']:
            stype = face['surface_type']
            type_counts[stype] = type_counts.get(stype, 0) + 1
        
        step_faces = ", ".join([f"{k}:{v}" for k, v in type_counts.items()])
        
        # 提取STEP关键尺寸
        step_dims_parts = []
        for face in step_obj['face_details']:
            if face['surface_type'] == 'CYLINDRICAL' and 'radius' in face['params']:
                step_dims_parts.append(f"R={face['params']['radius']:.2f}")
            elif face['surface_type'] == 'CONICAL' and 'radius' in face['params']:
                step_dims_parts.append(f"R={face['params']['radius']:.2f}, A={face['params']['angle']:.4f}")
            elif face['surface_type'] == 'TOROIDAL' and 'minor_radius' in face['params']:
                step_dims_parts.append(f"F={face['params']['minor_radius']:.2f}")
        
        step_dims = ", ".join(step_dims_parts) if step_dims_parts else "N/A"
        
        print(f"{i+1:<3} {obj_name:<35} {detected_type:<25} {blender_dims:<30} {step_faces:<25}")
        if step_dims_parts:
            print(f"    {'':<63} STEP尺寸: {step_dims}")
        print()
    
    print("=" * 120)
    
    # 总结问题
    print("\n问题总结:")
    print("-" * 120)
    
    issues = []
    for i, (log_obj, step_obj) in enumerate(zip(log_objects, step_objects)):
        # 检查类型不匹配
        type_counts = {}
        for face in step_obj['face_details']:
            stype = face['surface_type']
            type_counts[stype] = type_counts.get(stype, 0) + 1
        
        detected = log_obj['detected_type']
        if detected == "CONE" and 'CONICAL' not in type_counts:
            issues.append(f"对象{i+1} ({log_obj['name']}): 检测为CONE但STEP中没有CONICAL面")
        elif detected == "CYLINDER" and 'CYLINDRICAL' not in type_counts:
            issues.append(f"对象{i+1} ({log_obj['name']}): 检测为CYLINDER但STEP中没有CYLINDRICAL面")
        elif detected == "TAPERED_FILLET_CHAMFER" and 'TOROIDAL' not in type_counts:
            issues.append(f"对象{i+1} ({log_obj['name']}): 检测为TAPERED_FILLET_CHAMFER但STEP中没有TOROIDAL面")
    
    if issues:
        for issue in issues:
            print(f"  ⚠ {issue}")
    else:
        print("  ✓ 所有对象类型匹配正确")
    
    print()

if __name__ == "__main__":
    main()
