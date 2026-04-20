"""
分析STEP文件中每个对象的尺寸
"""
import re
import sys

def parse_step_file(step_file):
    """解析STEP文件，提取每个对象的几何信息"""
    with open(step_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 查找所有ADVANCED_BREP_SHAPE_REPRESENTATION
    # 格式: #10 = ADVANCED_BREP_SHAPE_REPRESENTATION('',(#11,#15),#113);
    rep_pattern = r'#(\d+)\s*=\s*ADVANCED_BREP_SHAPE_REPRESENTATION\([^,]*,\(([^)]+)\),[^)]+\)'
    representations = re.findall(rep_pattern, content)
    
    objects = []
    for rep_id, entities_str in representations:
        # 提取实体ID列表
        entity_ids = re.findall(r'#(\d+)', entities_str)
        
        # 找到MANIFOLD_SOLID_BREP的ID（通常是第二个实体）
        solid_id = None
        for eid in entity_ids:
            if re.search(r'#' + eid + r'\s*=\s*MANIFOLD_SOLID_BREP', content):
                solid_id = eid
                break
        
        if not solid_id:
            continue
        
        # 查找CLOSED_SHELL
        shell_match = re.search(r'#' + solid_id + r'\s*=\s*MANIFOLD_SOLID_BREP\([^,]*,#(\d+)\)', content)
        if not shell_match:
            continue
        
        shell_id = shell_match.group(1)
        shell_content_match = re.search(r'#' + shell_id + r'\s*=\s*CLOSED_SHELL\([^,]*,\(([^)]+)\)', content)
        if not shell_content_match:
            continue
        
        faces_str = shell_content_match.group(1)
        face_ids = re.findall(r'#(\d+)', faces_str)
        
        # 分析每个面的类型
        face_types = []
        for face_id in face_ids:
            # 查找ADVANCED_FACE引用的surface ID
            face_match = re.search(r'#' + face_id + r'\s*=\s*ADVANCED_FACE\([^,]*,[^,]*,#(\d+)', content)
            if face_match:
                surface_id = face_match.group(1)
                # 查找表面类型
                surface_match = re.search(r'#' + surface_id + r'\s*=\s*(\w+)_SURFACE', content)
                if surface_match:
                    face_types.append(surface_match.group(1))
                else:
                    face_types.append("UNKNOWN")
        
        objects.append({
            'rep_id': rep_id,
            'face_count': len(face_ids),
            'face_types': face_types
        })
    
    return objects

def main():
    if len(sys.argv) < 2:
        print("用法: python analyze_step.py <step_file>")
        sys.exit(1)
    
    step_file = sys.argv[1]
    objects = parse_step_file(step_file)
    
    print(f"STEP文件: {step_file}")
    print(f"对象数量: {len(objects)}")
    print()
    
    for i, obj in enumerate(objects):
        print(f"对象 {i+1}:")
        print(f"  面数量: {obj['face_count']}")
        print(f"  面类型: {', '.join(obj['face_types'])}")
        print()

if __name__ == "__main__":
    main()
