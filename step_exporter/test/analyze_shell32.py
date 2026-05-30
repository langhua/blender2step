import re

with open('f:\\git\\blender2step\\step_exporter\\test39.step', 'r', encoding='utf-8', errors='ignore') as f:
    content = f.read()

# Find shell #32
shell_pattern = r'#32\s*=\s*CLOSED_SHELL\s*\([^;]+\)\);'
match = re.search(shell_pattern, content, re.DOTALL)
if match:
    face_refs = [int(x) for x in re.findall(r'#(\d+)', match.group(0))]
    face_refs = [x for x in face_refs if x != 32]
    print(f"Shell #32 has {len(face_refs)} faces")
    
    # Analyze face types
    face_types = {}
    for face_id in face_refs:
        face_pattern = rf'#{face_id}\s*=\s*ADVANCED_FACE\s*\([^,]+,\s*\([^)]+\),\s*#(\d+)'
        face_match = re.search(face_pattern, content)
        if face_match:
            surface_id = int(face_match.group(1))
            # Check surface type
            surface_pattern = rf'#{surface_id}\s*=\s*(\w+)'
            surface_match = re.search(surface_pattern, content)
            if surface_match:
                surface_type = surface_match.group(1)
                face_types[surface_type] = face_types.get(surface_type, 0) + 1
    
    print(f"\nFace surface types:")
    for stype, count in face_types.items():
        print(f"  {stype}: {count}")
