import re

with open(r'f:\git\blender2step\step_exporter\test28.step.log', 'r', encoding='utf-8') as f:
    content = f.read()

# 查找Object 8的锥形参数
obj8_start = content.find('Processing object 8/11')
obj8_end = content.find('Processing object 9/11')
if obj8_start != -1 and obj8_end != -1:
    obj8_content = content[obj8_start:obj8_end]
    print("=== Cylinder_Tapered_Fillet_Chamfer (Object 8) ===")
    
    # 查找所有半径相关信息
    patterns = [
        'bottom R=',
        'top R=',
        'Bottom R:',
        'Top R:',
        'radius_bottom',
        'radius_top',
        'r_bottom',
        'r_top',
        'r_at_z_min',
        'r_at_z_max'
    ]
    
    for pattern in patterns:
        pos = 0
        while True:
            pos = obj8_content.find(pattern, pos)
            if pos == -1:
                break
            start = max(0, pos - 80)
            end = min(len(obj8_content), pos + 150)
            print(f"  {obj8_content[start:end].strip()}")
            print()
            pos += 1

# 查找Object 10的锥形空心圆柱参数
obj10_start = content.find('Processing object 10/11')
obj10_end = content.find('Processing object 11/11')
if obj10_start != -1 and obj10_end != -1:
    obj10_content = content[obj10_start:obj10_end]
    print("\n=== Cylinder_Tapered_Hollow (Object 10) ===")
    
    patterns = [
        'outer_radius_bottom',
        'outer_radius_top',
        'inner_radius_bottom',
        'inner_radius_top',
        'outer_bottom_radius',
        'outer_top_radius',
        'inner_bottom_radius',
        'inner_top_radius',
        'Created tapered hollow'
    ]
    
    for pattern in patterns:
        pos = 0
        while True:
            pos = obj10_content.find(pattern, pos)
            if pos == -1:
                break
            start = max(0, pos - 80)
            end = min(len(obj10_content), pos + 200)
            print(f"  {obj10_content[start:end].strip()}")
            print()
            pos += 1
