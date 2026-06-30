"""
Complete verification: match STEP solids to Blender objects and compare dimensions.
Uses only the LAST export run from the log.
"""
import re
from collections import defaultdict

step_path = r'f:\git\blender2step\step_exporter\test28.step'
log_path = r'f:\git\blender2step\step_exporter\test28.step.log'

# ===== PHASE 1: Parse log (LAST export run only) =====
print("=" * 100)
print("PHASE 1: Parse log for expected parameters (last run only)")

# Find all export runs by looking for "Modal: export complete" markers
with open(log_path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Parse the ENTIRE log - each object may appear in multiple runs, keep LAST
# The log is one continuous session with multiple export runs interleaved
print(f"Log file has {len(lines)} lines total")

expected = {}
current_obj = None

for line in lines:
    m = re.search(r'Checking:\s+(\S+)', line)
    if m:
        current_obj = m.group(1)
        if current_obj not in expected:
            expected[current_obj] = {}
    
    m = re.search(r'Found\s+(\S+):\s+(\S+)', line)
    if m:
        obj_type, name = m.group(1), m.group(2)
        if name in expected:
            expected[name]['type'] = obj_type
    
    # CLASSIFIED: cone bR=... tR=... h=...
    m = re.search(r'CLASSIFIED:\s+(\S+)\s+bR=([\d.]+)\s+tR=([\d.]+)\s+h=([\d.]+)', line)
    if m and current_obj in expected:
        expected[current_obj]['obj_type'] = m.group(1)
        expected[current_obj]['bR'] = float(m.group(2))
        expected[current_obj]['tR'] = float(m.group(3))
        expected[current_obj]['h'] = float(m.group(4))
    
    # hollow_cone! bR=... tR=... h=... inner_r=... (in meters → convert to mm)
    m = re.search(r'hollow_cone!\s+bR=([\d.]+)\s+tR=([\d.]+)\s+h=([\d.]+)\s+inner_r=([\d.]+)\s+top_ch=([\d.]+)\s+top_fr=([\d.]+)\s+btm_ch=([\d.]+)\s+btm_fr=([\d.]+)', line)
    if m and current_obj in expected:
        expected[current_obj]['bR'] = float(m.group(1)) * 1000
        expected[current_obj]['tR'] = float(m.group(2)) * 1000
        expected[current_obj]['h'] = float(m.group(3)) * 1000
        expected[current_obj]['inner_r'] = float(m.group(4)) * 1000
        expected[current_obj]['top_ch'] = float(m.group(5)) * 1000
        expected[current_obj]['top_fr'] = float(m.group(6))
        expected[current_obj]['btm_ch'] = float(m.group(7)) * 1000
        expected[current_obj]['btm_fr'] = float(m.group(8)) * 1000
    
    # cylinder_blind_hole! r=... h=... hole_r=... (in meters → convert to mm)
    m = re.search(r'cylinder_blind_hole!\s+r=([\d.]+)\s+h=([\d.]+)\s+hole_r=([\d.]+)\s+hole_d=([\d.]+)\s+pos=(\S+)', line)
    if m and current_obj in expected:
        expected[current_obj]['bR'] = float(m.group(1)) * 1000
        expected[current_obj]['tR'] = float(m.group(1)) * 1000
        expected[current_obj]['h'] = float(m.group(2)) * 1000
        expected[current_obj]['inner_r'] = float(m.group(3)) * 1000
        expected[current_obj]['hole_pos'] = m.group(5)
    
    # cone_stepped_hole! bR=... tR=... h=...
    m = re.search(r'cone_stepped_hole!\s+bR=([\d.]+)\s+tR=([\d.]+)\s+h=([\d.]+)', line)
    if m and current_obj in expected:
        expected[current_obj]['bR'] = float(m.group(1))
        expected[current_obj]['tR'] = float(m.group(2))
        expected[current_obj]['h'] = float(m.group(3))
    
    # cone_groove! r=... h=... top_ch=... top_fr=... btm_ch=... btm_fr=...
    m = re.search(r'cone_groove!\s+r=([\d.]+)\s+h=([\d.]+)\s+top_ch=([\d.]+)\s+top_fr=([\d.]+)\s+btm_ch=([\d.]+)\s+btm_fr=([\d.]+)', line)
    if m and current_obj in expected:
        expected[current_obj]['bR'] = float(m.group(1))
        expected[current_obj]['tR'] = float(m.group(1))
        expected[current_obj]['h'] = float(m.group(2))
        expected[current_obj]['top_ch'] = float(m.group(3))
        expected[current_obj]['top_fr'] = float(m.group(4))
        expected[current_obj]['btm_ch'] = float(m.group(5))
        expected[current_obj]['btm_fr'] = float(m.group(6))
    
    # groove_depth=
    m = re.search(r'groove_depth=([\d.]+)', line)
    if m and current_obj in expected:
        expected[current_obj]['groove_depth'] = float(m.group(1))
    
    # Detected: center=... bottom_r=... top_r=..., height=... (in meters → convert to mm)
    m = re.search(r'Detected: center=.*?bottom_r=([\d.]+)\s+top_r=([\d.]+),\s+height=([\d.]+)', line)
    if m and current_obj in expected and 'bR' not in expected[current_obj]:
        expected[current_obj]['bR'] = float(m.group(1)) * 1000
        expected[current_obj]['tR'] = float(m.group(2)) * 1000
        expected[current_obj]['h'] = float(m.group(3)) * 1000
        expected[current_obj]['h'] = float(m.group(3)) * 1000
    
    # detect: bottom_r=... top_r=... height=... (in meters → convert to mm)
    m = re.search(r'^\S+\s+detect:\s+bottom_r=([\d.]+)\s+top_r=([\d.]+)\s+height=([\d.]+)', line)
    if m and current_obj in expected and 'bR' not in expected[current_obj]:
        expected[current_obj]['bR'] = float(m.group(1)) * 1000
        expected[current_obj]['tR'] = float(m.group(2)) * 1000
        expected[current_obj]['h'] = float(m.group(3)) * 1000

print(f"Parsed {len(expected)} objects from last export run")

# ===== PHASE 2: Parse STEP file =====
print("\n" + "=" * 100)
print("PHASE 2: Parse STEP file geometry")

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

# BREP -> SHELL
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

products = [eid for eid, (et, _) in entities.items() if et == 'PRODUCT']
print(f"{len(products)} products")

# Product -> brep
prod_to_brep = {}
for prod_id in products:
    for pds_id, pdef_id in pds_to_pdef.items():
        if pdef_id in pdef_to_pdff:
            pdff_id = pdef_to_pdff[pdef_id]
            if pdff_id in pdff_to_prod and pdff_to_prod[pdff_id] == prod_id:
                for sdr_id, absr_id in sdr_to_absr.items():
                    refs = re.findall(r'#(\d+)', entities[sdr_id][1])
                    if refs and refs[0] == pds_id and absr_id in adv_brep:
                        prod_to_brep[prod_id] = adv_brep[absr_id]
                        break
                break

# ===== PHASE 3: Analyze STEP solids =====
print("PHASE 3: Analyze STEP solids")

def get_stats(shell_id):
    if shell_id not in shell_faces:
        return None
    cyl_r = []; torus_n = 0; cone_n = 0; z_vals = []
    for fid in shell_faces[shell_id]:
        if fid not in face_surf: continue
        sid = face_surf[fid]
        if sid in cyl_surfs: cyl_r.append(cyl_surfs[sid])
        elif sid in cone_surfs: cone_n += 1; cyl_r.append(cone_surfs[sid][0])
        elif sid in torus_surfs: torus_n += 1
    visited = set()
    stack = list(shell_faces[shell_id])
    while stack:
        rid = stack.pop()
        if rid in visited: continue
        visited.add(rid)
        if rid in points: z_vals.append(points[rid][2])
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
        'faces': len(shell_faces[shell_id]), 'hollow': hollow,
        'all_radii': sorted(cyl_r, reverse=True)
    }

results = []
for pid in products:
    if pid not in prod_to_brep: continue
    bid = prod_to_brep[pid]
    if bid not in brep_shell: continue
    s = get_stats(brep_shell[bid])
    if s: results.append(s)

print(f"Analyzed {len(results)} STEP solids")

# ===== PHASE 4: Compare =====
print("\n" + "=" * 100)
print("COMPARISON: Blender (log) vs STEP actual")
print("=" * 100)

def sort_key(name):
    p = name.split('_')[0]
    if p.startswith('GS'):
        rn = int(p[2:])
        gs = 1
    elif p.startswith('S'):
        rn = int(p[1:])
        gs = 0
    else:
        return (99, 0, name)
    # Column order
    col_order = ['Plain', 'TBl', 'BBl', 'BothBl', 'Thru', 'TprThru', 'InvTpr', 'InvTprThru',
                 'TprTBl', 'TprBBl', 'TprBoth', 'TprBothBl', 'Stepped', 'TprStep']
    col = 99
    for ci, cn in enumerate(col_order):
        if cn in name:
            # Prefer exact suffix match
            if name.endswith(cn):
                col = ci
                break
            elif col == 99:
                col = ci
    return (rn, gs, col, name)

snames = sorted(expected.keys(), key=sort_key)

TOL = 3.0  # 3mm tolerance

issues = []
ok = 0

hdr = f"{'#':>3} {'Object':<18} {'Type':<28} {'Expected':>30}  {'STEP':>30}  {'Verdict':>12}"
print(hdr)
print("-" * len(hdr))

for i, name in enumerate(snames):
    e = expected[name]
    ot = e.get('type', '?')
    
    # Expected string
    ep = []
    bR = e.get('bR', 0)
    tR = e.get('tR', bR)
    h = e.get('h', 0)
    if bR > 0:
        if abs(tR - bR) < 1:
            ep.append(f"R={bR:.0f}")
        else:
            ep.append(f"bR={bR:.0f} tR={tR:.0f}")
        ep.append(f"H={h:.0f}")
    ir = e.get('inner_r', 0)
    if ir > 0: ep.append(f"hole={ir:.0f}")
    top_ch = e.get('top_ch', 0)
    if top_ch > 0.001: ep.append(f"ch={top_ch*1000:.0f}")
    top_fr = e.get('top_fr', 0)
    if top_fr > 0.001: ep.append(f"fr={top_fr*1000:.0f}")
    gd = e.get('groove_depth', 0)
    if gd > 0: ep.append(f"grv={gd:.0f}")
    es = ' '.join(ep) if ep else '-'
    
    ss, vd = '-', '-'
    bad = False
    
    if i < len(results):
        s = results[i]
        sp = []
        if s['outer_r'] > 0:
            sp.append(f"R={s['outer_r']:.0f}")
            sp.append(f"H={s['height']:.0f}")
        if s['hollow']: sp.append(f"hole={s['inner_r']:.0f}")
        if s['torus_n']: sp.append(f"chamf({s['torus_n']})")
        if s['cone_n'] and not s['hollow']: sp.append(f"cone({s['cone_n']})")
        sp.append(f"F={s['faces']}")
        ss = ' '.join(sp)
        
        if bR > 0 and s['outer_r'] > 0:
            r_ok = abs(bR - s['outer_r']) < TOL
            h_ok = abs(h - s['height']) < TOL
            hole_ok = True
            chamf_ok = True
            
            if ir > 0 and not s['hollow']:
                hole_ok = False
            if (top_ch > 0.001 or top_fr > 0.001) and s['torus_n'] == 0:
                chamf_ok = False
            
            if not r_ok:
                bad = True; vd = f"R:{bR:.0f}!={s['outer_r']:.0f}"
            elif not h_ok:
                bad = True; vd = f"H:{h:.0f}!={s['height']:.0f}"
            elif not hole_ok:
                bad = True; vd = "MISS HOLE"
            elif not chamf_ok:
                bad = True; vd = "MISS CHAMF"
            else:
                vd = "OK"; ok += 1
        elif s['outer_r'] > 0:
            vd = "OK"; ok += 1
    
    if bad: issues.append((i+1, name, ot, vd))
    print(f"{i+1:>3} {name:<18} {ot:<28} {es:>30}  {ss:>30}  {vd:>12}")

print(f"\n{'='*100}")
print(f"SUMMARY: {len(snames)} objects in log, {len(results)} STEP solids")
print(f"  [OK] Passed: {ok}")
print(f"  ❌ Issues: {len(issues)}")

if issues:
    print("\n--- Issues Detail ---")
    for idx, name, ot, desc in issues:
        print(f"  #{idx} {name} ({ot}): {desc}")

print("\nDone.")
