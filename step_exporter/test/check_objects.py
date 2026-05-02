import re

with open(r'f:\git\blender2step\step_exporter\test28.step.log', 'r', encoding='utf-8') as f:
    content = f.read()

# 查找Object 8 (Cylinder_Tapered_Fillet_Chamfer)
obj8_start = content.find('Processing object 8/11')
obj8_end = content.find('Processing object 9/11')
if obj8_start != -1 and obj8_end != -1:
    obj8_content = content[obj8_start:obj8_end]
    print("=" * 80)
    print("Object 8: Cylinder_Tapered_Fillet_Chamfer")
    print("=" * 80)
    
    # 查找锥形参数
    for keyword in ['bottom R=', 'top R=', 'Bottom R:', 'Top R:', 'Profile points:', 'Created tapered']:
        pos = 0
        while True:
            pos = obj8_content.find(keyword, pos)
            if pos == -1:
                break
            start = max(0, pos - 100)
            end = min(len(obj8_content), pos + 200)
            print(f"  {obj8_content[start:end].strip()}")
            print()
            pos += 1

# 查找Object 10 (Cylinder_Tapered_Hollow)
obj10_start = content.find('Processing object 10/11')
obj10_end = content.find('Processing object 11/11')
if obj10_start != -1 and obj10_end != -1:
    obj10_content = content[obj10_start:obj10_end]
    print("\n" + "=" * 80)
    print("Object 10: Cylinder_Tapered_Hollow")
    print("=" * 80)
    
    # 查找锥形空心圆柱参数
    for keyword in ['outer_radius', 'inner_radius', 'outer bottom', 'outer top', 'inner bottom', 'inner top', 'Creating tapered hollow', 'Created tapered hollow']:
        pos = 0
        while True:
            pos = obj10_content.find(keyword, pos)
            if pos == -1:
                break
            start = max(0, pos - 100)
            end = min(len(obj10_content), pos + 200)
            print(f"  {obj10_content[start:end].strip()}")
            print()
            pos += 1
