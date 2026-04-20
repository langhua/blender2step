"""
分析STEP文件中每个对象的尺寸
用法: python analyze_step_dimensions.py <step_file>
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
                        # CYLINDRICAL_SURFACE('',#axis,radius)
                        radius_match = re.search(r',([0-9.]+(?:E[+-]?\d+)?)\)', surface_params)
                        if radius_match:
                            params['radius'] = float(radius_match.group(1))
                    elif surface_type == 'CONICAL':
                        # CONICAL_SURFACE('',#axis,radius,angle)
                        conical_match = re.search(r',([0-9.]+(?:E[+-]?\d+)?),([0-9.]+(?:E[+-]?\d+)?)\)', surface_params)
                        if conical_match:
                            params['radius'] = float(conical_match.group(1))
                            params['angle'] = float(conical_match.group(2))
                    elif surface_type == 'TOROIDAL':
                        # TOROIDAL_SURFACE('',#axis,major_radius,minor_radius)
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

def main():
    if len(sys.argv) < 2:
        print("用法: python analyze_step_dimensions.py <step_file>")
        sys.exit(1)
    
    step_file = sys.argv[1]
    objects = parse_step_file(step_file)
    
    print(f"STEP文件: {step_file}")
    print(f"对象数量: {len(objects)}")
    print()
    print("=" * 80)
    
    for i, obj in enumerate(objects):
        print(f"\n对象 {i+1}:")
        print(f"  面数量: {obj['face_count']}")
        
        # 统计面类型
        type_counts = {}
        for face in obj['face_details']:
            stype = face['surface_type']
            type_counts[stype] = type_counts.get(stype, 0) + 1
        
        print(f"  面类型分布: {', '.join([f'{k}: {v}' for k, v in type_counts.items()])}")
        
        # 显示关键参数
        for j, face in enumerate(obj['face_details']):
            if face['params']:
                print(f"    面{j} ({face['surface_type']}): {face['params']}")
        
        print()

if __name__ == "__main__":
    main()
