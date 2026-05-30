import re

with open('f:\\git\\blender2step\\step_exporter\\test39.step', 'r', encoding='utf-8', errors='ignore') as f:
    content = f.read()

# Check surface types for all 90 faces
shell_pattern = r'#32\s*=\s*CLOSED_SHELL\s*\([^;]+\)\);'
match = re.search(shell_pattern, content, re.DOTALL)
if match:
    face_refs = [int(x) for x in re.findall(r'#(\d+)', match.group(0))]
    face_refs = [x for x in face_refs if x != 32]
    
    surface_types = {}
    for face_id in face_refs:
        face_pattern = rf'#{face_id}\s*=\s*ADVANCED_FACE\s*\([^,]*,\s*\([^)]+\),\s*#(\d+)'
        face_match = re.search(face_pattern, content)
        if face_match:
            surface_id = int(face_match.group(1))
            surface_pattern = rf'#{surface_id}\s*=\s*(\w+)'
            surface_match = re.search(surface_pattern, content)
            if surface_match:
                stype = surface_match.group(1)
                surface_types[stype] = surface_types.get(stype, 0) + 1
    
    print(f"Surface types in shell #32:")
    for stype, count in surface_types.items():
        print(f"  {stype}: {count}")
    
    # Show first few surface definitions
    print(f"\nFirst 5 surface definitions:")
    for face_id in face_refs[:5]:
        face_pattern = rf'#{face_id}\s*=\s*ADVANCED_FACE\s*\([^,]*,\s*\([^)]+\),\s*#(\d+)'
        face_match = re.search(face_pattern, content)
        if face_match:
            surface_id = int(face_match.group(1))
            surface_pattern = rf'#{surface_id}\s*=\s*\w+[^;]*;'
            surface_match = re.search(surface_pattern, content, re.DOTALL)
            if surface_match:
                print(f"  #{surface_id}: {surface_match.group(0)[:120]}...")
