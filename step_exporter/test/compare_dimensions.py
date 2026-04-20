"""
对比Blender模型与STEP导出模型的尺寸差异
用法: python compare_dimensions.py <step_file> <log_file>
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
                
                # 查找表面类型和参数
                surface_match = re.search(r'#' + surface_id + r'\s*=\s*(\w+)_SURFACE\([^)]+\)', content)
                if surface_match:
                    surface_type = surface_match.group(1)
                    surface_params = surface_match.group(0)
                    
                    # 提取关键参数
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
    """解析日志文件，提取Blender中的原始尺寸"""
    with open(log_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 查找所有Processing object和检测到的尺寸
    objects = []
    
    # 查找对象名称
    obj_names = re.findall(r'Processing object \d+/\d+: (\S+)', content)
    
    # 查找检测到的圆锥参数
    cone_patterns = re.findall(r'Detected CONE: top R=([0-9.]+) bottom R=([0-9.]+) diff=([0-9.]+)%', content)
    
    # 查找圆角半径
    fillet_patterns = re.findall(r'Detected top fillet on tapered cylinder, radius=([0-9.]+)', content)
    
    # 查找倒角尺寸
    chamfer_patterns = re.findall(r'Detected bottom chamfer on tapered cylinder, size=([0-9.]+)', content)
    
    # 查找Tapered cylinder params
    tapered_params = re.findall(r'Tapered cylinder params:.*?Bottom R:\s*([0-9.]+).*?Top R:\s*([0-9.]+).*?Height:\s*([0-9.]+).*?Fillet R:\s*([0-9.]+).*?Chamfer size:\s*([0-9.]+)', content, re.DOTALL)
    
    return {
        'obj_names': obj_names,
        'cone_patterns': cone_patterns,
        'fillet_patterns': fillet_patterns,
        'chamfer_patterns': chamfer_patterns,
        'tapered_params': tapered_params
    }

def main():
    if len(sys.argv) < 3:
        print("用法: python compare_dimensions.py <step_file> <log_file>")
        sys.exit(1)
    
    step_file = sys.argv[1]
    log_file = sys.argv[2]
    
    step_objects = parse_step_file(step_file)
    log_data = parse_log_file(log_file)
    
    print("=" * 100)
    print("Blender模型与STEP导出模型尺寸对比表")
    print("=" * 100)
    print()
    
    # 打印表头
    print(f"{'对象':<35} {'类型':<15} {'Blender尺寸':<25} {'STEP尺寸':<25} {'差异':<10}")
    print("-" * 100)
    
    for i, (obj_name, step_obj) in enumerate(zip(log_data['obj_names'], step_objects)):
        # 确定对象类型
        obj_type = "UNKNOWN"
        blender_dims = ""
        step_dims = ""
        diff = ""
        
        # 统计STEP中的面类型
        type_counts = {}
        for face in step_obj['face_details']:
            stype = face['surface_type']
            type_counts[stype] = type_counts.get(stype, 0) + 1
        
        if 'TOROIDAL' in type_counts and 'CONICAL' in type_counts:
            obj_type = "TAPERED_FILLET_CHAMFER"
        elif 'TOROIDAL' in type_counts:
            obj_type = "FILLET"
        elif 'CONICAL' in type_counts:
            obj_type = "CONE"
        elif 'CYLINDRICAL' in type_counts:
            obj_type = "CYLINDER"
        
        # 提取Blender尺寸
        if i < len(log_data['tapered_params']):
            params = log_data['tapered_params'][i]
            blender_dims = f"B={params[0]}, T={params[1]}, H={params[2]}, F={params[3]}, C={params[4]}"
        elif i < len(log_data['cone_patterns']):
            cone = log_data['cone_patterns'][i]
            blender_dims = f"Top={cone[0]}, Bot={cone[1]}"
        
        # 提取STEP尺寸
        step_dims_parts = []
        for face in step_obj['face_details']:
            if face['surface_type'] == 'CYLINDRICAL' and 'radius' in face['params']:
                step_dims_parts.append(f"R={face['params']['radius']:.2f}")
            elif face['surface_type'] == 'CONICAL' and 'radius' in face['params']:
                step_dims_parts.append(f"R={face['params']['radius']:.2f}, A={face['params']['angle']:.4f}")
            elif face['surface_type'] == 'TOROIDAL' and 'minor_radius' in face['params']:
                step_dims_parts.append(f"F={face['params']['minor_radius']:.2f}")
        
        step_dims = ", ".join(step_dims_parts) if step_dims_parts else "N/A"
        
        print(f"{obj_name:<35} {obj_type:<15} {blender_dims:<25} {step_dims:<25} {diff:<10}")
    
    print()
    print("=" * 100)

if __name__ == "__main__":
    main()
