import re

with open('f:\\git\\blender2step\\step_exporter\\test39.step', 'r', encoding='utf-8', errors='ignore') as f:
    content = f.read()

shell_pattern = r'#32\s*=\s*CLOSED_SHELL\s*\([^;]+\)\);'
match = re.search(shell_pattern, content, re.DOTALL)
if match:
    face_refs = [int(x) for x in re.findall(r'#(\d+)', match.group(0))]
    face_refs = [x for x in face_refs if x != 32]
    
    # Check all surface types
    surface_types = {}
    for face_id in face_refs:
        face_pattern = rf'#{face_id}\s*=\s*ADVANCED_FACE\s*\([^,]*,\s*\([^)]+\),\s*#(\d+)'
        face_match = re.search(face_pattern, content)
        if face_match:
            surface_id = int(face_match.group(1))
            # Get the full line for this surface
            surface_line_pattern = rf'#{surface_id}\s*=\s*([A-Z_]+)'
            surface_match = re.search(surface_line_pattern, content)
            if surface_match:
                stype = surface_match.group(1)
                surface_types[stype] = surface_types.get(stype, 0) + 1
    
    print(f"Surface types in shell #32:")
    for stype, count in surface_types.items():
        print(f"  {stype}: {count}")
