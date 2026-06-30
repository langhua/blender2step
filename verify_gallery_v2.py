"""
Verification script v2: Compare STEP file geometry with Blender expected parameters.
"""
import re, os
from collections import defaultdict

step_path = r'f:\git\blender2step\step_exporter\test28.step'
log_path = r'f:\git\blender2step\step_exporter\test28.step.log'

# ========== PHASE 1: Parse log ==========
print("=" * 80)
print("PHASE 1: Parsing log...")

expected = {}
current_obj = None
with open(log_path, 'r', encoding='utf-8') as f:
    for line in f:
        m = re.search(r'Checking:\s+(\S+)', line)
        if m:
            current_obj = m.group(1)
            if current_obj not in expected:
                expected[current_obj] = {}
        
        m = re.search(r'Found\s+(\S+):\s+(\S+)', line)
        if m:
            if m.group(2) in expected:
                expected[m.group(2)]['type'] = m.group(1)
        
        m = re.search(r'CLASSIFIED:\s+cone\s+bR=([\d.]+)\s+tR=([\d.]+)\s+h=([\d.]+)', line)
        if m and current_obj in expected:
            expected[current_obj]['bR'] = float(m.group(1))
            expected[current_obj]['tR'] = float(m.group(2))
            expected[current_obj]['h'] = float(m.group(3))
        
        m = re.search(r'hollow_cone!\s+bR=([\d.]+)\s+tR=([\d.]+)\s+h=([\d.]+)\s+inner_r=([\d.]+)\s+top_ch=([\d.]+)\s+top_fr=([\d.]+)\s+btm_ch=([\d.]+)\s+btm_fr=([\d.]+)', line)
        if m and current_obj in expected:
            expected[current_obj]['bR'] = float(m.group(1))
            expected[current_obj]['tR'] = float(m.group(2))
            expected[current_obj]['h'] = float(m.group(3))
            expected[current_obj]['inner_r'] = float(m.group(4))
            expected[current_obj]['top_ch'] = float(m.group(5))
            expected[current_obj]['btm_ch'] = float(m.group(7))
        
        m = re.search(r'cylinder_blind_hole!\s+r=([\d.]+)\s+h=([\d.]+)\s+hole_r=([\d.]+)', line)
        if m and current_obj in expected:
            expected[current_obj]['bR'] = float(m.group(1))
            expected[current_obj]['tR'] = float(m.group(1))
            expected[current_obj]['h'] = float(m.group(2))
            expected[current_obj]['inner_r'] = float(m.group(3))
        
        m = re.search(r'groove_depth=([\d.]+)', line)
        if m and current_obj in expected:
            expected[current_obj]['groove_depth'] = float(m.group(1))
        
        m = re.search(r'Detected: center=.*?bottom_r=([\d.]+)\s+top_r=([\d.]+),\s+height=([\d.]+)', line)
        if m and current_obj in expected and 'bR' not in expected[current_obj]:
            expected[current_obj]['bR'] = float(m.group(1))
            expected[current_obj]['tR'] = float(m.group(2))
            expected[current_obj]['h'] = float(m.group(3))

    # PHASE 1: Deduplicate - only keep objects with type set (last export pass)
    # Also filter to only real objects (80 unique: S1-S5 + GS1-GS5, 10-14 per row)
    real_expected = {k: v for k, v in expected.items() if 'type' in v}
    print(f"After dedup: {len(real_expected)} objects with type")
    expected = real_expected

# ========== PHASE 2: Parse STEP file ==========
print("\n" + "=" * 80)
print("PHASE 2: Parsing STEP file...")

with open(step_path, 'r', encoding='utf-8') as f:
    content = f.read()

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
            points[eid] = [float(x.strip()) for x in m.group(1).split(',')]

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

# BREP -> SHELL
brep_shell = {}
for eid, (etype, body) in entities.items():
    if etype == 'MANIFOLD_SOLID_BREP':
        m = re.search(r"#(\d+)", body)
        if m: brep_shell[eid] = m.group(1)

# ADVANCED_BREP_SHAPE_REPRESENTATION -> brep
adv_brep = {}
for eid, (etype, body) in entities.items():
    if etype == 'ADVANCED_BREP_SHAPE_REPRESENTATION':
        refs = re.findall(r'#(\d+)', body)
        if len(refs) >= 2: adv_brep[eid] = refs[1]

# SDR -> ABSR
sdr_to_absr = {}
for eid, (etype, body) in entities.items():
    if etype == 'SHAPE_DEFINITION_REPRESENTATION':
        refs = re.findall(r'#(\d+)', body)
        if refs: sdr_to_absr[eid] = refs[-1]

# PDS -> PD
pds_to_pdef = {}
for eid, (etype, body) in entities.items():
    if etype == 'PRODUCT_DEFINITION_SHAPE':
        refs = re.findall(r'#(\d+)', body)
        if refs: pds_to_pdef[eid] = refs[-1]

# PD -> PDFF
pdef_to_pdff = {}
for eid, (etype, body) in entities.items():
    if etype == 'PRODUCT_DEFINITION':
        refs = re.findall(r'#(\d+)', body)
        if refs: pdef_to_pdff[eid] = refs[0]

# PDFF -> PRODUCT
pdff_to_prod = {}
for eid, (etype, body) in entities.items():
    if etype == 'PRODUCT_DEFINITION_FORMATION':
        refs = re.findall(r'#(\d+)', body)
        if refs: pdff_to_prod[eid] = refs[0]

# All PRODUCTs
products = [eid for eid, (et, _) in entities.items() if et == 'PRODUCT']

# Product -> brep
prod_to_brep = {}
for prod_id in products:
    for pds_id, pdef_id in pds_to_pdef.items():
        if pdef_id in pdef_to_pdff:
            pdff_id = pdef_to_pdff[pdef_id]
            if pdff_id in pdff_to_prod and pdff_to_prod[pdff_id] == prod_id:
                for sdr_id, absr_id in sdr_to_absr.items():
                    body = entities[sdr_id][1]
                    refs = re.findall(r'#(\d+)', body)
                    if refs and refs[0] == pds_id and absr_id in adv_brep:
                        prod_to_brep[prod_id] = adv_brep[absr_id]
                        break
                break

print(f"{len(products)} products, {len(prod_to_brep)} with geometry")

# ========== PHASE 3: Analyze solids ==========
print("\n" + "=" * 80)
print("PHASE 3: Analyzing STEP solids...")

def get_stats(shell_id):
    if shell_id not in shell_faces:
        return None
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
    # Z values via traversal
    visited = set()
    stack = list(shell_faces[shell_id])
    while stack:
        rid = stack.pop()
        if rid in visited: continue
        visited.add(rid)
        if rid in points:
            pt = points[rid]
            if len(pt) >= 3:
                z_vals.append(pt[2])
        elif rid in entities:
            for sr in re.findall(r'#(\d+)', entities[rid][1]):
                if sr not in visited: stack.append(sr)
    mn, mx = (min(z_vals), max(z_vals)) if z_vals else (0, 0)
    outer_r = max(cyl_r) if cyl_r else 0
    inner_r = min(cyl_r) if len(cyl_r) > 1 else 0
    hollow = len(cyl_r) > 1 and 0 < inner_r < outer_r * 0.95
    return {
        'outer_r': outer_r, 'inner_r': inner_r if hollow else 0,
        'height': mx - mn, 'torus_n': torus_n, 'cone_n': cone_n,
        'faces': len(shell_faces[shell_id]), 'hollow': hollow
    }

results = []
for pid in products:
    if pid not in prod_to_brep: continue
    bid = prod_to_brep[pid]
    if bid not in brep_shell: continue
    s = get_stats(brep_shell[bid])
    if s: results.append(s)

print(f"Analyzed {len(results)} solids")

# ========== PHASE 4: Compare ==========
print("\n" + "=" * 80)
print("COMPARISON TABLE")
print("=" * 80)

def sort_key(name):
    p = name.split('_')[0]
    rn = int(p[2:]) if p.startswith('GS') else (int(p[1:]) if p.startswith('S') else 99)
    gs = 1 if p.startswith('GS') else 0
    return (rn, gs, name)

snames = sorted(expected.keys(), key=sort_key)

hdr = f"{'#':>3} {'Object':<18} {'Type':<26} {'Expected(mm)':>35} {'STEP(mm)':>35} {'Verdict':>12}"
print(hdr)
print("-" * len(hdr))

issues = []; ok = 0
for i, name in enumerate(snames):
    e = expected[name]; ot = e.get('type','?')
    ep = []
    if 'bR' in e: ep.append(f"bR={e['bR']:.0f} tR={e.get('tR',e['bR']):.0f} H={e['h']:.0f}")
    if e.get('inner_r',0)>0: ep.append(f"hole={e['inner_r']:.0f}")
    if e.get('top_ch',0)>0.001: ep.append(f"ch={e['top_ch']*1000:.0f}")
    if 'groove_depth' in e: ep.append(f"grv={e['groove_depth']:.0f}")
    es = ' '.join(ep) if ep else '-'
    
    ss, vd, bad = '-', '-', False
    if i < len(results):
        s = results[i]
        sp = [f"R={s['outer_r']:.0f} H={s['height']:.0f}"]
        if s['hollow']: sp.append(f"hole={s['inner_r']:.0f}")
        if s['torus_n']: sp.append(f"chamf({s['torus_n']})")
        sp.append(f"F={s['faces']}")
        ss = ' '.join(sp)
        
        if 'bR' in e and e['bR']>0 and s['outer_r']>0:
            T=2.0
            if abs(e['bR']-s['outer_r'])>T: bad=True; vd=f"R diff"
            elif abs(e['h']-s['height'])>T: bad=True; vd=f"H diff"
            elif e.get('inner_r',0)>0 and not s['hollow']: bad=True; vd="NO HOLE"
            elif e.get('top_ch',0)>0.001 and s['torus_n']==0: bad=True; vd="NO CHAMFER"
            else: vd="OK"; ok+=1
        elif s['outer_r']>0: vd="OK"; ok+=1
    
    if bad: issues.append((i+1, name, ot, vd))
    print(f"{i+1:>3} {name:<18} {ot:<26} {es:>35} {ss:>35} {vd:>12}")

print(f"\n{'='*80}")
print(f"SUMMARY: {len(snames)} objects, {len(results)} solids, {ok} OK, {len(issues)} issues")
if issues:
    print("\nIssues:")
    for idx, name, ot, desc in issues:
        print(f"  #{idx} {name} ({ot}): {desc}")
print("Done.")
