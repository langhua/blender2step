"""
Simple STEP solid analyzer: prints key properties of each solid in export order.
"""
import re
step_path = r'f:\git\blender2step\step_exporter\test28.step'

with open(step_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Parse all entities
entities = {}
for m in re.finditer(r'#(\d+)=\s*(\w+)\((.*?)\);', content, re.DOTALL):
    entities[m.group(1)] = (m.group(2), m.group(3))
print(f"Parsed {len(entities)} entities")

# Points
points = {}
for eid, (etype, body) in entities.items():
    if etype == 'CARTESIAN_POINT':
        m = re.match(r"''\s*,\s*\(([^)]+)\)", body)
        if m:
            pts = [float(x.strip()) for x in m.group(1).split(',')]
            if len(pts) >= 3:
                points[eid] = pts

# Surfaces
cyl_surfs = {}; cone_surfs = {}; torus_surfs = {}
for eid, (etype, body) in entities.items():
    if etype == 'CYLINDRICAL_SURFACE':
        m = re.match(r"''\s*,\s*#(\d+)\s*,\s*([\d.]+)", body)
        if m: cyl_surfs[eid] = float(m.group(2))
    elif etype == 'CONICAL_SURFACE':
        m = re.match(r"''\s*,\s*#(\d+)\s*,\s*([\d.]+)\s*,\s*([\d.]+)", body)
        if m: cone_surfs[eid] = (float(m.group(2)), float(m.group(3)))
    elif etype == 'TOROIDAL_SURFACE':
        m = re.match(r"''\s*,\s*#(\d+)\s*,\s*([\d.]+)\s*,\s*([\d.]+)", body)
        if m: torus_surfs[eid] = (float(m.group(2)), float(m.group(3)))

# CLOSED_SHELL -> faces
shell_faces = {}
for eid, (etype, body) in entities.items():
    if etype == 'CLOSED_SHELL':
        faces = re.findall(r'#(\d+)', body)
        if len(faces) > 1: shell_faces[eid] = faces[1:]

# ADVANCED_FACE -> surface
face_surf = {}
for eid, (etype, body) in entities.items():
    if etype == 'ADVANCED_FACE':
        m = re.search(r'#(\d+)\s*,\s*\.[TF]\.', body)
        if m: face_surf[eid] = m.group(1)

# SURFACE_CURVE / EDGE_CURVE -> for TORUS edges (chamfer detection)
# Count torus edges per shell
def analyze_shell(shell_id):
    if shell_id not in shell_faces:
        return "NOFACES"
    cyl_r = []; torus_n = 0; cone_n = 0; z_vals = []
    for fid in shell_faces[shell_id]:
        if fid not in face_surf:
            continue
        sid = face_surf[fid]
        if sid in cyl_surfs:
            cyl_r.append(cyl_surfs[sid])
        elif sid in cone_surfs:
            cone_n += 1; cyl_r.append(cone_surfs[sid][0])
        elif sid in torus_surfs:
            torus_n += 1
    # Z from points
    visited = set()
    stack = list(shell_faces[shell_id])
    while stack:
        rid = stack.pop()
        if rid in visited: continue
        visited.add(rid)
        if rid in points:
            z_vals.append(points[rid][2])
        elif rid in entities:
            for sr in re.findall(r'#(\d+)', entities[rid][1]):
                if sr not in visited: stack.append(sr)
    mn, mx = (min(z_vals), max(z_vals)) if z_vals else (0, 0)
    outer_r = max(cyl_r) if cyl_r else 0
    inner_r = min(cyl_r) if len(cyl_r) > 1 else 0
    hollow = len(cyl_r) > 1 and 0 < inner_r < outer_r * 0.95
    
    parts = [f"R={outer_r:.0f} H={mx-mn:.0f}"]
    if hollow: parts.append(f"hole={inner_r:.0f}")
    if torus_n: parts.append(f"chamf({torus_n})")
    if cone_n: parts.append(f"cone({cone_n})")
    parts.append(f"F={len(shell_faces[shell_id])}")
    return ' '.join(parts)

# Chain: PRODUCT -> ... -> BREP
# Build maps
brep_shell = {}
for eid, (et, body) in entities.items():
    if et == 'MANIFOLD_SOLID_BREP':
        m = re.search(r"#(\d+)", body)
        if m: brep_shell[eid] = m.group(1)

adv_brep = {}
for eid, (et, body) in entities.items():
    if et == 'ADVANCED_BREP_SHAPE_REPRESENTATION':
        refs = re.findall(r'#(\d+)', body)
        if len(refs) >= 2: adv_brep[eid] = refs[1]

sdr_to_absr = {}
for eid, (et, body) in entities.items():
    if et == 'SHAPE_DEFINITION_REPRESENTATION':
        refs = re.findall(r'#(\d+)', body)
        if refs: sdr_to_absr[eid] = refs[-1]

pds_to_pdef = {}
for eid, (et, body) in entities.items():
    if et == 'PRODUCT_DEFINITION_SHAPE':
        refs = re.findall(r'#(\d+)', body)
        if refs: pds_to_pdef[eid] = refs[-1]

pdef_to_pdff = {}
for eid, (et, body) in entities.items():
    if et == 'PRODUCT_DEFINITION':
        refs = re.findall(r'#(\d+)', body)
        if refs: pdef_to_pdff[eid] = refs[0]

pdff_to_prod = {}
for eid, (et, body) in entities.items():
    if et == 'PRODUCT_DEFINITION_FORMATION':
        refs = re.findall(r'#(\d+)', body)
        if refs: pdff_to_prod[eid] = refs[0]

products = [(eid, entities[eid][1]) for eid, (et, _) in entities.items() if et == 'PRODUCT']

print(f"\n{'='*80}")
print(f"STEP Solids in Export Order ({len(products)} products total)")
print(f"{'='*80}")
print(f"{'#':>4} {'Product ID':>10} {'Shell':>10} {'Properties'}")
print("-" * 80)

count = 0
for prod_id, body in products:
    # Find brep
    brep_id = None
    for pds_id, pdef_id in pds_to_pdef.items():
        if pdef_id in pdef_to_pdff:
            pdff_id = pdef_to_pdff[pdef_id]
            if pdff_id in pdff_to_prod and pdff_to_prod[pdff_id] == prod_id:
                for sdr_id, absr_id in sdr_to_absr.items():
                    refs = re.findall(r'#(\d+)', entities[sdr_id][1])
                    if refs and refs[0] == pds_id and absr_id in adv_brep:
                        brep_id = adv_brep[absr_id]
                        break
                break
    
    if brep_id and brep_id in brep_shell:
        shell_id = brep_shell[brep_id]
        props = analyze_shell(shell_id)
        count += 1
        print(f"{count:>4} {prod_id:>10} {shell_id:>10} {props}")
    elif brep_id:
        count += 1
        print(f"{count:>4} {prod_id:>10} {'?':>10} NO SHELL (brep={brep_id})")

print(f"\nTotal analyzed: {count}")
print("Done.")
