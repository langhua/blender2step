import re

with open(r'f:\git\blender2step\step_exporter\test28.step.log', 'r', encoding='utf-8') as f:
    content = f.read()

# Find Object 8 section
obj8_start = content.find('Processing object 8/11')
obj8_end = content.find('Processing object 9/11')
if obj8_start == -1 or obj8_end == -1:
    print('Object 8 not found')
else:
    obj8_content = content[obj8_start:obj8_end]
    
    # Search for cone detection messages
    patterns = [
        'Detected top fillet',
        'Detected bottom chamfer',
        'is_fillet',
        'is_chamfered',
        'Analyzing cone features',
        'Tapered cylinder features',
        'Fillet radius calculation'
    ]
    
    for pattern in patterns:
        positions = []
        pos = 0
        while True:
            pos = obj8_content.find(pattern, pos)
            if pos == -1:
                break
            positions.append(pos)
            pos += 1
        
        if positions:
            print(f'\n=== Found "{pattern}" at {len(positions)} positions ===')
            for pos in positions[:3]:  # Show first 3 occurrences
                start = max(0, pos - 50)
                end = min(len(obj8_content), pos + 150)
                print(f'  ...{obj8_content[start:end]}...')
                print()
