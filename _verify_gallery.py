"""
Verification script: Compare STEP file geometry with Blender expected parameters.
Reads test28.step + test28.step.log and produces a comparison report.
"""
import re, os
from collections import defaultdict

step_path = r'f:\git\blender2step\step_exporter\test28.step'
log_path = r'f:\git\blender2step\step_exporter\test28.step.log'

# ========== PHASE 1: Parse log to get expected params ==========
print("=" * 80)
print("PHASE 1: Parsing STEP log for expected parameters...")
print("=" * 80)

expected = {}  # name -> {params}
current_obj = None

with open(log_path, 'r', encoding='utf-8') as f:
    for line in f:
        # Pick object name from "Checking: NAME" or "Found TYPE: NAME"
        m = re.search(r'Checking:\s+(\S+)', line)
        if m:
            current_obj = m.group(1)
            expected[current_obj] = {'name': current_obj, 'type': 'unknown'}
        
        m = re.search(r'Found\s+(\S+):\s+(\S+)', line)
        if m:
            obj_type, name = m.group(1), m.group(2)
            if name in expected:
                expected[name]['type'] = obj_type
        
        # Extract classification params
        m = re.search(r'CLASSIFIED:\s+cone\s+bR=([\d.]+)\s+tR=([\d.]+)\s+h=([\d.]+)', line)
        if m and current_obj:
            expected[current_obj]['bR'] = float(m.group(1))
            expected[current_obj]['tR'] = float(m.group(2))
            expected[current_obj]['h'] = float(m.group(3))
        
        # Extract hollow_cone params
        m = re.search(r'hollow_cone!\s+bR=([\d.]+)\s+tR=([\d.]+)\s+h=([\d.]+)\s+inner_r=([\d.]+)\s+top_ch=([\d.]+)\s+top_fr=([\d.]+)\s+btm_ch=([\d.]+)\s+btm_fr=([\d.]+)', line)
        if m and current_obj:
            expected[current_obj]['bR'] = float(m.group(1))
            expected[current_obj]['tR'] = float(m.group(2))
            expected[current_obj]['h'] = float(m.group(3))
            expected[current_obj]['inner_r'] = float(m.group(4))
            expected[current_obj]['top_ch'] = float(m.group(5))
            expected[current_obj]['top_fr'] = float(m.group(6))
            expected[current_obj]['btm_ch'] = float(m.group(7))
            expected[current_obj]['btm_fr'] = float(m.group(8))
        
        # Extract cone_blind_hole params (cylinder_blind_hole fallback)
        m = re.search(r'cylinder_blind_hole!\s+r=([\d.]+)\s+h=([\d.]+)\s+hole_r=([\d.]+)\s+hole_d=([\d.]+)', line)
        if m and current_obj:
            expected[current_obj]['bR'] = float(m.group(1))
            expected[current_obj]['tR'] = float(m.group(1))  # cylinder
            expected[current_obj]['h'] = float(m.group(2))
            expected[current_obj]['inner_r'] = float(m.group(3))
        
        # Extract groove params
        m = re.search(r'groove_depth=([\d.]+)', line)
        if m and current_obj:
            expected[current_obj]['groove_depth'] = float(m.group(1))
        
        # Extract tapered through-hole params
        m = re.search(r'tapered through-hole: inner_top=([\d.]+) inner_bot=([\d.]+)', line)
        if m and current_obj:
            expected[current_obj]['inner_top'] = float(m.group(1))
            expected[current_obj]['inner_bot'] = float(m.group(2))

print(f"Found {len(expected)} objects in log")

# ========== PHASE 2: Parse STEP file geometry ==========
print("\n" + "=" * 80)
print("PHASE 2: Parsing STEP file geometry...")
print("=" * 80)

with open(step_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Parse CARTESIAN_POINT
points = {}
for m in re.finditer(r'#(\d+)= CARTESIAN_POINT\(\'\',\(([^)]+)\)\);', content):
    coords = [float(x.strip()) for x in m.group(2).split(',')]
    points[m.group(1)] = coords

# Parse AXIS2_PLACEMENT_3D
axis_positions = {}
for m in re.finditer(r'#(\d+)= AXIS2_PLACEMENT_3D\(\'\',#(\d+),.*?\);', content):
    pt_id = m.group(2)
    if pt_id in points:
        axis_positions[m.group(1)] = points[pt_id]

# Parse MANIFOLD_SOLID_BREP -> CLOSED_SHELL
brep_to_shell = {}
for m in re.finditer(r'#(\d+)= MANIFOLD_SOLID_BREP\(\'\',#(\d+)\);', content):
    brep_to_shell[m.group(1)] = m.group(2)

# Parse CLOSED_SHELL -> face list
shell_to_faces = {}
for m in re.finditer(r'#(\d+)= CLOSED_SHELL\(\'\',\(([^)]+)\)\);', content):
    faces = [x.strip() for x in m.group(2).split(',')]
    shell_to_faces[m.group(1)] = faces

# Parse ADVANCED_FACE -> surface
face_to_surf = {}
for m in re.finditer(r'#(\d+)= ADVANCED_FACE\(\'\',(?:\([^)]*\),)?#(\d+),', content):
    face_to_surf[m.group(1)] = m.group(2)

# Parse CYLINDRICAL_SURFACE -> radius + axis
cylindrical = {}  # surface_id -> (radius, axis_pt)
for m in re.finditer(r'#(\d+)= CYLINDRICAL_SURFACE\(\'\',#(\d+),([\d.]+)\);', content):
    ax_id = m.group(2)
    r = float(m.group(3))
    if ax_id in axis_positions:
        cylindrical[m.group(1)] = (r, axis_positions[ax_id])

# Parse CONICAL_SURFACE -> radius at axis, semi-angle, axis_pt
conical = {}
for m in re.finditer(r'#(\d+)= CONICAL_SURFACE\(\'\',#(\d+),([\d.]+),([\d.]+)\);', content):
    ax_id = m.group(2)
    r = float(m.group(3))
    angle = float(m.group(4))
    if ax_id in axis_positions:
        conical[m.group(1)] = (r, angle, axis_positions[ax_id])

# Parse TOROIDAL_SURFACE
toroidal = {}
for m in re.finditer(r'#(\d+)= TOROIDAL_SURFACE\(\'\',#(\d+),([\d.]+),([\d.]+)\);', content):
    ax_id = m.group(2)
    toroidal[m.group(1)] = (float(m.group(3)), float(m.group(4)))

# Parse PLANE -> axis Z
planes = {}
for m in re.finditer(r'#(\d+)= PLANE\(\'\',#(\d+)\);', content):
    ax_id = m.group(2)
    if ax_id in axis_positions:
        planes[m.group(1)] = axis_positions[ax_id][2]  # Z coordinate

# Parse ADVANCED_BREP_SHAPE_REPRESENTATION
adv_brep = {}
for m in re.finditer(r'#(\d+)= ADVANCED_BREP_SHAPE_REPRESENTATION\(\'\',\(#(\d+),#(\d+)\)', content):
    adv_brep[m.group(1)] = (m.group(2), m.group(3))  # (axis_id, brep_id)

# Find SOLID index from PRODUCT
product_solids = []
for m in re.finditer(r'#(\d+)= PRODUCT\(\'Open CASCADE STEP translator ([^\']+)\'', content):
    product_solids.append((m.group(1), m.group(2)))

# Chain: PRODUCT -> PRODUCT_DEFINITION -> PRODUCT_DEFINITION_SHAPE -> SHAPE_DEFINITION_REPRESENTATION -> ADVANCED_BREP
pdef_to_prod = {}
for m in re.finditer(r'#(\d+)= PRODUCT_DEFINITION\(\'design\',\'\',#(\d+),', content):
    pdef_to_prod[m.group(1)] = m.group(2)

pds_to_pdef = {}
for m in re.finditer(r'#(\d+)= PRODUCT_DEFINITION_SHAPE\(\'\',\'\',#(\d+)\);', content):
    pds_to_pdef[m.group(1)] = m.group(2)

sdr_to_brep = {}
for m in re.finditer(r'#(\d+)= SHAPE_DEFINITION_REPRESENTATION\(#(\d+),#(\d+)\);', content):
    sdr_to_brep[m.group(1)] = m.group(3)

# Map product id -> brep id
prod_to_brep = {}
for prod_id, _ in product_solids:
    for pds_id, pdef_id in pds_to_pdef.items():
        if pdef_id in pdef_to_prod and pdef_to_prod[pdef_id] == prod_id:
            for sdr_id, brep in sdr_to_brep.items():
                # Find which SDR references this PDS
                for m in re.finditer(r'#(\d+)= SHAPE_DEFINITION_REPRESENTATION\(#(\d+),#(\d+)\);', content):
                    if m.group(2) == pds_id and m.group(3) in adv_brep:
                        _, brep_id = adv_brep[m.group(3)]
                        prod_to_brep[prod_id] = brep_id
                        break
            break
    if prod_id not in prod_to_brep:
        # Try direct
        for sdr_id, sdr_brep in sdr_to_brep.items():
            if sdr_brep in adv_brep:
                _, brep_id = adv_brep[sdr_brep]
                prod_to_brep[prod_id] = brep_id

print(f"Found {len(product_solids)} products in STEP file")

# ========== PHASE 3: Analyze each solid ==========
print("\n" + "=" * 80)
print("PHASE 3: Analyzing each STEP solid...")
print("=" * 80)

def get_shell_surfaces(shell_id):
    """Get all surface types for a shell."""
    if shell_id not in shell_to_faces:
        return {}
    surfs = defaultdict(list)
    for face_id in shell_to_faces[shell_id]:
        if face_id in face_to_surf:
            sid = face_to_surf[face_id]
            if sid in cylindrical:
                surfs['CYL'].append(cylindrical[sid])
            elif sid in conical:
                surfs['CONE'].append(conical[sid])
            elif sid in toroidal:
                surfs['TORUS'].append(toroidal[sid])
            # PLANE check separately
            if sid in planes:
                surfs['PLANE_Z'].append(planes[sid])
    return surfs

# For each solid, extract dimensions
solid_results = []
for idx, (prod_id, translator_name) in enumerate(product_solids):
    if prod_id not in prod_to_brep:
        continue
    brep_id = prod_to_brep[prod_id]
    if brep_id not in brep_to_shell:
        continue
    shell_id = brep_to_shell[brep_id]
    if shell_id not in shell_to_faces:
        continue
    
    surfs = get_shell_surfaces(shell_id)
    num_faces = len(shell_to_faces[shell_id])
    
    cyl_radii = sorted([s[0] for s in surfs.get('CYL', [])])
    cone_data = surfs.get('CONE', [])
    torus_data = surfs.get('TORUS', [])
    plane_zs = sorted(set(surfs.get('PLANE_Z', [])))
    
    # Determine outer radius: max of all cylindrical/conical surface radii
    all_radii = cyl_radii + [c[0] for c in cone_data]
    outer_r = max(all_radii) if all_radii else 0
    inner_r = min(all_radii) if len(all_radii) > 1 else 0
    
    # Height from plane extremes
    if len(plane_zs) >= 2:
        height = max(plane_zs) - min(plane_zs)
        btm_z = min(plane_zs)
        top_z = max(plane_zs)
    else:
        height = 0
        btm_z = top_z = 0
    
    # Detect features
    has_chamfer = len(torus_data) > 0
    has_cone = len(cone_data) > 0
    is_hollow = len(all_radii) > 1 and inner_r > 0 and inner_r < outer_r * 0.98
    
    solid_results.append({
        'idx': idx + 1,
        'translator': translator_name,
        'num_faces': num_faces,
        'outer_r': outer_r,
        'inner_r': inner_r if is_hollow else 0,
        'height': height,
        'btm_z': btm_z,
        'top_z': top_z,
        'has_chamfer': has_chamfer,
        'has_cone': has_cone,
        'is_hollow': is_hollow,
        'num_torus': len(torus_data),
        'cyl_count': len(cyl_radii),
        'cone_count': len(cone_data),
    })

# ========== PHASE 4: Match STEP solids to Blender objects ==========
print("\n" + "=" * 80)
print("PHASE 4: Matching STEP solids to Blender objects...")
print("=" * 80)

# Sort expected objects by name prefix (S1_, S2_, S3_, S4_, GS1_, GS2_)
def sort_key(name):
    parts = name.split('_')
    prefix = parts[0]
    # GS prefixes
    if prefix.startswith('GS'):
        return (int(prefix[2:]), name)
    # S prefixes
    if prefix.startswith('S'):
        return (int(prefix[1:]), name)
    return (99, name)

sorted_names = sorted(expected.keys(), key=sort_key)
print(f"Expected objects (from log): {len(sorted_names)}")
print(f"STEP solids: {len(solid_results)}")

# For each expected object, try to find the matching STEP solid
# STEP solids are in positional order matching the export order
# The export order should be the same as creation order

print("\n" + "=" * 80)
print("COMPARISON TABLE")
print("=" * 80)
print(f"{'#':>3} {'Object':<18} {'Type':<24} {'Expected':>30} {'STEP Actual':>30} {'Match':>8}")
print("-" * 130)

issues = []
matched = 0

for i, name in enumerate(sorted_names):
    exp = expected[name]
    obj_type = exp.get('type', '?')
    
    # Build expected description
    exp_desc = ""
    if 'bR' in exp:
        exp_desc = f"bR={exp['bR']:.0f} tR={exp.get('tR', exp['bR']):.0f} h={exp['h']:.0f}"
    if 'inner_r' in exp:
        exp_desc += f" hole={exp['inner_r']:.0f}"
    if 'top_ch' in exp and exp['top_ch'] > 0.001:
        exp_desc += f" top_ch={exp['top_ch']*1000:.0f}mm"
    if 'groove_depth' in exp:
        exp_desc += f" groove={exp['groove_depth']:.0f}mm"
    
    # Get corresponding STEP solid
    if i < len(solid_results):
        sr = solid_results[i]
        step_desc = f"R={sr['outer_r']:.0f} H={sr['height']:.0f}"
        if sr['is_hollow']:
            step_desc += f" hole={sr['inner_r']:.0f}"
        if sr['has_chamfer']:
            step_desc += f" chamf({sr['num_torus']})"
        if sr['has_cone']:
            step_desc += f" cone({sr['cone_count']})"
        
        # Compare key metrics (allow some tolerance)
        match = ""
        tolerance = 2.0  # 2mm tolerance
        has_issue = False
        
        if 'bR' in exp:
            # Convert expected from meters to mm (Blender internal units)
            exp_bR_mm = exp['bR'] * 1000
            if abs(exp_bR_mm - sr['outer_r']) > tolerance:
                match = f"❌ R diff"
                has_issue = True
            # Height check
            exp_h_mm = exp['h'] * 1000
            if abs(exp_h_mm - sr['height']) > tolerance:
                match += f" H diff({exp_h_mm:.0f} vs {sr['height']:.0f})"
                has_issue = True
            # Hollow check
            if 'inner_r' in exp and exp['inner_r'] > 0:
                if not sr['is_hollow']:
                    match += " MISSING HOLE"
                    has_issue = True
                elif sr['inner_r'] > 0 and abs(exp['inner_r'] * 1000 - sr['inner_r']) > 5:
                    match += f" hole_r diff"
                    has_issue = True
            elif sr['is_hollow']:
                match += " UNEXPECTED HOLE"
                has_issue = True
            # Chamfer check
            if 'top_ch' in exp and exp['top_ch'] > 0.001:
                if not sr['has_chamfer']:
                    match += " MISSING CHAMFER"
                    has_issue = True
        
        if not has_issue:
            match = "✅"
            matched += 1
        elif not match:
            match = "✅"
            matched += 1
        
        if has_issue:
            issues.append((i+1, name, obj_type, match))
        
        print(f"{i+1:>3} {name:<18} {obj_type:<24} {exp_desc:>30} {step_desc:>30} {match:>8}")
    else:
        print(f"{i+1:>3} {name:<18} {obj_type:<24} {exp_desc:>30} {'NO STEP SOLID':>30} {'❌':>8}")
        issues.append((i+1, name, obj_type, "NO STEP SOLID"))

# Summary
print("\n" + "=" * 80)
print("SUMMARY")
print("=" * 80)
print(f"Total objects in log: {len(sorted_names)}")
print(f"Total solids in STEP: {len(solid_results)}")
print(f"Matched OK: {matched}")
print(f"Issues found: {len(issues)}")

if issues:
    print("\n--- Issues ---")
    for idx, name, obj_type, desc in issues:
        print(f"  #{idx} {name} ({obj_type}): {desc}")

if len(sorted_names) != len(solid_results):
    print(f"\n⚠ Mismatch: {len(sorted_names)} expected vs {len(solid_results)} step solids")

print("\nDone.")
