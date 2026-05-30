import re

with open('f:\\git\\blender2step\\step_exporter\\test39.step', 'r', encoding='utf-8', errors='ignore') as f:
    content = f.read()

shell_pattern = r'#32\s*=\s*CLOSED_SHELL\s*\([^;]+\)\);'
match = re.search(shell_pattern, content, re.DOTALL)
if match:
    face_refs = [int(x) for x in re.findall(r'#(\d+)', match.group(0))]
    face_refs = [x for x in face_refs if x != 32]
    
    print(f"Total faces: {len(face_refs)}")
    
    # Check first 10 faces
    matched = 0
    unmatched = 0
    for face_id in face_refs[:10]:
        face_pattern = rf'#{face_id}\s*=\s*ADVANCED_FACE\s*\([^,]*,\s*\([^)]+\),\s*#(\d+)'
        face_match = re.search(face_pattern, content)
        if face_match:
            surface_id = int(face_match.group(1))
            surface_line_pattern = rf'#{surface_id}\s*=\s*([A-Z_]+)'
            surface_match = re.search(surface_line_pattern, content)
            if surface_match:
                matched += 1
            else:
                unmatched += 1
                print(f"  Face #{face_id} -> Surface #{surface_id}: NO MATCH")
                # Show what's at this ID
                id_pattern = rf'#{surface_id}\s*=\s*([^\n;]+)'
                id_match = re.search(id_pattern, content)
                if id_match:
                    print(f"    Actual: {id_match.group(1)[:80]}")
        else:
            print(f"  Face #{face_id}: NO FACE MATCH")
    
    print(f"\nMatched: {matched}, Unmatched: {unmatched}")
