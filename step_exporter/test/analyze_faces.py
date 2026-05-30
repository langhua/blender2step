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
    
    # Analyze first 5 faces in detail
    for face_id in face_refs[:5]:
        print(f"\n=== Face #{face_id} ===")
        face_pattern = rf'#{face_id}\s*=\s*ADVANCED_FACE\s*\([^,]*,\s*\(([^)]+)\),\s*#(\d+)'
        face_match = re.search(face_pattern, content)
        if face_match:
            bound_refs = face_match.group(1)
            surface_id = int(face_match.group(2))
            print(f"  Bound refs: {bound_refs}")
            print(f"  Surface ID: #{surface_id}")
            
            # Check surface type
            surface_pattern = rf'#{surface_id}\s*=\s*(\w+)'
            surface_match = re.search(surface_pattern, content)
            if surface_match:
                surface_type = surface_match.group(1)
                print(f"  Surface type: {surface_type}")
                
                # Get full surface definition
                surface_line_pattern = rf'#{surface_id}\s*=\s*{surface_type}[^;]*;'
                surface_line = re.search(surface_line_pattern, content)
                if surface_line:
                    print(f"  Surface def: {surface_line.group(0)[:100]}...")
