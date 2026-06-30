"""Analyze STEP file by text parsing - no OCC Python needed."""
import re

def parse_step(filename):
    with open(filename, 'r') as f:
        content = f.read()
    entities = {}
    for match in re.finditer(r'#(\d+)\s*=\s*(\w+)\((.*?)\);', content, re.DOTALL):
        eid = int(match.group(1))
        etype = match.group(2)
        raw = ' '.join(match.group(3).split())
        entities[eid] = (etype, raw)
    return entities

def extract_points(entities):
    points = {}
    for eid, (etype, raw) in entities.items():
        if etype == 'CARTESIAN_POINT':
            m = re.search(r'\(([^)]*),([^)]*),([^)]*)\)', raw)
            if m:
                points[eid] = (float(m.group(1)), float(m.group(2)), float(m.group(3)))
    return points

def collect_all_vertex_refs(entities, shell_id, depth=0):
    """Recursively collect all VERTEX_POINT refs from a CLOSED_SHELL."""
    vertices = set()
    if shell_id not in entities:
        return vertices
    
    _, raw = entities[shell_id]
    # Find all #N references
    refs = [int(m) for m in re.findall(r'#(\d+)', raw)]
    
    for ref in refs:
        if ref in entities:
            etype, eraw = entities[ref]
            if etype == 'VERTEX_POINT':
                vertices.add(ref)
            elif etype == 'CARTESIAN_POINT':
                pass  # handled separately
            elif ref not in (shell_id,):  # avoid infinite recursion
                # Recursively collect from ADVANCED_FACE, FACE_BOUND, EDGE_LOOP, etc.
                sub_vertices = collect_all_vertex_refs(entities, ref, depth+1)
                vertices.update(sub_vertices)
    
    return vertices

print("Parsing STEP...")
entities = parse_step('F:/git/blender2step/step_exporter/test28.step')
print(f"Entities: {len(entities)}")
points = extract_points(entities)
print(f"Points: {len(points)}")

# Find all CLOSED_SHELL and MANIFOLD_SOLID_BREP
shells = {}
for eid, (etype, raw) in entities.items():
    if etype == 'CLOSED_SHELL':
        refs = [int(m) for m in re.findall(r'#(\d+)', raw)]
        shells[eid] = refs

solid_to_shell = {}
for eid, (etype, raw) in entities.items():
    if etype == 'MANIFOLD_SOLID_BREP':
        refs = [int(m) for m in re.findall(r'#(\d+)', raw)]
        if refs:
            solid_to_shell[eid] = refs[0]

print(f"Shells: {len(shells)}, Solids: {len(solid_to_shell)}")

# For each solid, find all vertices and compute bounding box
solids = []
for solid_id, shell_id in solid_to_shell.items():
    vert_ids = collect_all_vertex_refs(entities, shell_id)
    coords = [points[vid] for vid in vert_ids if vid in points]
    if coords:
        xs = [c[0] for c in coords]; ys = [c[1] for c in coords]; zs = [c[2] for c in coords]
        solids.append({
            'solid_id': solid_id,
            'xmin': min(xs), 'xmax': max(xs),
            'ymin': min(ys), 'ymax': max(ys),
            'zmin': min(zs), 'zmax': max(zs),
            'height': max(zs) - min(zs),
            'n_verts': len(coords),
        })

# Also find solids via ADVANCED_BREP_SHAPE_REPRESENTATION
if not solids:
    for eid, (etype, raw) in entities.items():
        if etype == 'ADVANCED_BREP_SHAPE_REPRESENTATION':
            refs = [int(m) for m in re.findall(r'#(\d+)', raw)]
            # First ref is AXIS2_PLACEMENT_3D, rest are MANIFOLD_SOLID_BREP
            for ref in refs[1:]:
                if ref in solid_to_shell:
                    shell_id = solid_to_shell[ref]
                    vert_ids = collect_all_vertex_refs(entities, shell_id)
                    coords = [points[vid] for vid in vert_ids if vid in points]
                    if coords:
                        xs = [c[0] for c in coords]; ys = [c[1] for c in coords]; zs = [c[2] for c in coords]
                        solids.append({
                            'solid_id': ref,
                            'xmin': min(xs), 'xmax': max(xs),
                            'ymin': min(ys), 'ymax': max(ys),
                            'zmin': min(zs), 'zmax': max(zs),
                            'height': max(zs) - min(zs),
                            'n_verts': len(coords),
                        })

print(f"Solids extracted: {len(solids)}")

if not solids:
    print("No solids found. Checking entity structure...")
    for eid, (etype, raw) in list(entities.items())[:20]:
        print(f"  #{eid}: {etype}")
    exit()

# Sort by Z-, then Y+
solids.sort(key=lambda o: (o['zmin'], -o['ymax']))
print(f"Sorted by Z-, Y+")

# Group 12 each, 16 groups
for g in range(min(16, len(solids)//12)):
    group = solids[g*12:(g+1)*12]
    heights = [round(o['height'], 3) for o in group]
    zmaxs = [round(o['zmax'], 1) for o in group]
    xranges = [round(o['xmax']-o['xmin'], 1) for o in group]
    
    h_set = set(heights)
    status = "✓ MATCH" if len(h_set) == 1 else f"✗ MISMATCH: {h_set}"
    print(f"Group {g+1:2d}: h={heights[0]:.1f} xRange~{xranges[0]:.0f} zTop~{zmaxs[0]:.0f} {status}")

print(f"\nTotal: {len(solids)} solids in {len(solids)//12} groups")
