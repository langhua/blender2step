import re

with open(r'f:\git\blender2step\step_exporter\test28.step.log', 'r', encoding='utf-8') as f:
    content = f.read()

# 查找Cylinder_Tapered_Fillet_Chamfer (Object 8)
obj8_start = content.find('Processing object 8/11')
obj8_end = content.find('Processing object 9/11')
if obj8_start != -1 and obj8_end != -1:
    obj8_content = content[obj8_start:obj8_end]
    print("=== Cylinder_Tapered_Fillet_Chamfer (Object 8) ===")
    
    # 查找关键参数
    patterns = [
        'bottom R=.*top R=',
        'Bottom R:.*Top R:',
        'Profile points:',
        'p0\(.*p1\(.*p3\(',
        'Created tapered cylinder'
    ]
    
    for pattern in patterns:
        pos = 0
        while True:
            pos = obj8_content.find(pattern, pos)
            if pos == -1:
                break
            start = max(0, pos - 50)
            end = min(len(obj8_content), pos + 200)
            print(f"  {obj8_content[start:end].strip()}")
            print()
            pos += 1

# 查找Cylinder_Tapered_Hollow (Object 10)
obj10_start = content.find('Processing object 10/11')
obj10_end = content.find('Processing object 11/11')
if obj10_start != -1 and obj10_end != -1:
    obj10_content = content[obj10_start:obj10_end]
    print("\n=== Cylinder_Tapered_Hollow (Object 10) ===")
    
    patterns = [
        'TAPERED HOLLOW',
        'outer_radius_bottom=.*outer_radius_top=',
        'inner_radius_bottom=.*inner_radius_top=',
        'outer_bottom_radius.*outer_top_radius',
        'inner_bottom_radius.*inner_top_radius',
        'Created tapered hollow'
    ]
    
    for pattern in patterns:
        pos = 0
        while True:
            pos = obj10_content.find(pattern, pos)
            if pos == -1:
                break
            start = max(0, pos - 50)
            end = min(len(obj10_content), pos + 200)
            print(f"  {obj10_content[start:end].strip()}")
            print()
            pos += 1
