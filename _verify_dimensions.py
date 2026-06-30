import re

with open('F:/git/blender2step/step_exporter/test28.step.log', 'r', encoding='utf-8') as f:
    lines = f.readlines()

objects = []
current = {}
for line in lines:
    m = re.search(r'Checking:\s+(\S+)', line)
    if m:
        if current: objects.append(current)
        current = {'name': m.group(1)}
        continue
    if not current: continue
    
    m = re.search(r'CLASSIFIED:\s+cone(?:_chamfer)?\s+bR=([\d.]+)\s+tR=([\d.]+)\s+h=([\d.]+)', line)
    if m:
        current['bR'] = float(m.group(1)); current['tR'] = float(m.group(2)); current['h'] = float(m.group(3))
        continue
    m = re.search(r'CLASSIFIED:\s+cylinder\s+r=([\d.]+)\s+h=([\d.]+)', line)
    if m:
        current['bR'] = float(m.group(1)); current['tR'] = float(m.group(1)); current['h'] = float(m.group(2))
        continue
    m = re.search(r'->\s+cone_stepped_hole!\s+bR=([\d.]+)\s+tR=([\d.]+)\s+h=([\d.]+)', line)
    if m:
        current['bR'] = float(m.group(1)); current['tR'] = float(m.group(2)); current['h'] = float(m.group(3))
        continue
    m = re.search(r'->\s+cylinder_stepped_hole!\s+r=([\d.]+)\s+h=([\d.]+)', line)
    if m:
        current['bR'] = float(m.group(1)); current['tR'] = float(m.group(1)); current['h'] = float(m.group(2))
        continue
    m = re.search(r'->\s+hollow_cone!\s+bR=([\d.]+)\s+tR=([\d.]+)\s+h=([\d.]+)', line)
    if m:
        current['bR'] = float(m.group(1)); current['tR'] = float(m.group(2)); current['h'] = float(m.group(3))
        continue
    m = re.search(r'->\s+cylinder_blind_hole!\s+r=([\d.]+)\s+h=([\d.]+)', line)
    if m:
        current['bR'] = float(m.group(1)) * 1000; current['tR'] = float(m.group(1)) * 1000; current['h'] = float(m.group(2)) * 1000
        continue
    m = re.search(r'->\s+cone_groove!\s+r=([\d.]+)\s+h=([\d.]+)', line)
    if m:
        current['bR'] = float(m.group(1)); current['tR'] = float(m.group(1)); current['h'] = float(m.group(2))
        continue
    m = re.search(r'top_ch=([\d.]+)\s+top_fr=([\d.]+)\s+btm_ch=([\d.]+)\s+btm_fr=([\d.]+)', line)
    if m:
        current['top_ch'] = float(m.group(1)); current['top_fr'] = float(m.group(2))
        current['btm_ch'] = float(m.group(3)); current['btm_fr'] = float(m.group(4))
    m = re.search(r"top_feature=(\S+)\s+top_feature_size=([\d.]+)\s+bottom_feature=(\S+)\s+bottom_feature_size=([\d.]+)", line)
    if m and 'top_ch' not in current:
        tf, tfs = m.group(1), float(m.group(2))
        bf, bfs = m.group(3), float(m.group(4))
        if tf != 'None': current['top_ch' if tf=='chamfer' else 'top_fr'] = round(tfs * 1000, 1)
        if bf != 'None': current['btm_ch' if bf=='chamfer' else 'btm_fr'] = round(bfs * 1000, 1)

if current: objects.append(current)

# Group by object TYPE suffix
obj_types = ['Plain', 'TBl', 'BBl', 'BothBl', 'Thru', 'TprThru', 'InvTprThru', 
             'TprTBl', 'TprBBl', 'TprBothBl', 'Stepped', 'TprStep',
             'InvTpr', 'TprBoth']

for otype in obj_types:
    matches = [o for o in objects if o['name'].endswith('_' + otype)]
    if not matches:
        matches = [o for o in objects if o['name'].split('_')[-1] == otype]
    if not matches: continue
    
    dims = {}
    for o in matches:
        br = round(o.get('bR', 0), 1)
        tr = round(o.get('tR', 0), 1)
        h = round(o.get('h', 0), 1)
        tc = round(o.get('top_ch', 0), 1)
        tf = round(o.get('top_fr', 0), 1)
        bc = round(o.get('btm_ch', 0), 1)
        bf = round(o.get('btm_fr', 0), 1)
        key = (br, tr, h, tc, tf, bc, bf)
        dims[key] = dims.get(key, []) + [o['name']]
    
    if len(dims) == 1:
        key = list(dims.keys())[0]
        status = '✓' if len(matches) >= 16 else f'({len(matches)})'
        print(f'{status:4s} {otype:14s} bR={key[0]:.0f} tR={key[1]:.0f} h={key[2]:.0f}  top_ch={key[3]:.1f} top_fr={key[4]:.1f} btm_ch={key[5]:.1f} btm_fr={key[6]:.1f}')
    else:
        print(f'✗    {otype:14s} {len(dims)} VARIATIONS ({len(matches)} objs):')
        for key, names in sorted(dims.items()):
            print(f'         bR={key[0]:.0f} tR={key[1]:.0f} h={key[2]:.0f} tc={key[3]:.1f} tf={key[4]:.1f} bc={key[5]:.1f} bf={key[6]:.1f} → {names}')
    m = re.search(r'Checking:\s+(\S+)', line)
    if m:
        if current:
            objects.append(current)
        current = {'name': m.group(1)}
        continue
    
    if not current:
        continue
    
    # Extract key classified dimensions (these are in mm after * S)
    # Cone plain: CLASSIFIED: cone bR=... tR=... h=...
    m = re.search(r'CLASSIFIED:\s+cone\s+bR=([\d.]+)\s+tR=([\d.]+)\s+h=([\d.]+)', line)
    if m:
        current['bR'] = float(m.group(1))
        current['tR'] = float(m.group(2))
        current['h'] = float(m.group(3))
        current['type'] = 'cone'
        continue
    
    # Cone chamfer: CLASSIFIED: cone_chamfer bR=... tR=... h=...
    m = re.search(r'CLASSIFIED:\s+cone_chamfer\s+bR=([\d.]+)\s+tR=([\d.]+)\s+h=([\d.]+)', line)
    if m:
        current['bR'] = float(m.group(1))
        current['tR'] = float(m.group(2))
        current['h'] = float(m.group(3))
        current['type'] = 'cone_chamfer'
        continue
    
    # Cylinder: CLASSIFIED: cylinder r=... h=...
    m = re.search(r'CLASSIFIED:\s+cylinder\s+r=([\d.]+)\s+h=([\d.]+)', line)
    if m:
        current['bR'] = float(m.group(1))
        current['tR'] = float(m.group(1))
        current['h'] = float(m.group(2))
        current['type'] = 'cylinder'
        continue
    
    # -> cone_stepped_hole! bR=... tR=... h=...
    m = re.search(r'->\s+cone_stepped_hole!\s+bR=([\d.]+)\s+tR=([\d.]+)\s+h=([\d.]+)', line)
    if m:
        current['bR'] = float(m.group(1))
        current['tR'] = float(m.group(2))
        current['h'] = float(m.group(3))
        continue
    
    # -> cylinder_stepped_hole! r=... h=...
    m = re.search(r'->\s+cylinder_stepped_hole!\s+r=([\d.]+)\s+h=([\d.]+)', line)
    if m:
        current['bR'] = float(m.group(1))
        current['tR'] = float(m.group(1))
        current['h'] = float(m.group(2))
        continue
    
    # -> hollow_cone! bR=... tR=... h=...
    m = re.search(r'->\s+hollow_cone!\s+bR=([\d.]+)\s+tR=([\d.]+)\s+h=([\d.]+)\s+inner_r=([\d.]+)', line)
    if m:
        current['bR'] = float(m.group(1))
        current['tR'] = float(m.group(2))
        current['h'] = float(m.group(3))
        continue
    
    # -> cylinder_blind_hole! r=... h=... (meters, need *1000)
    m = re.search(r'->\s+cylinder_blind_hole!\s+r=([\d.]+)\s+h=([\d.]+)', line)
    if m:
        current['bR'] = float(m.group(1)) * 1000
        current['tR'] = float(m.group(1)) * 1000
        current['h'] = float(m.group(2)) * 1000
        continue
    
    # -> cone_groove! r=... h=...
    m = re.search(r'->\s+cone_groove!\s+r=([\d.]+)\s+h=([\d.]+)', line)
    if m:
        current['bR'] = float(m.group(1))
        current['tR'] = float(m.group(1))
        current['h'] = float(m.group(2))
        continue
    
    # Detect chamfer/fillet sizes (mesh detected, in meters)
    m = re.search(r"detect:.*?\btop_feature=(\S+)\s+top_feature_size=([\d.]+)\s+bottom_feature=(\S+)\s+bottom_feature_size=([\d.]+)", line)
    if m and 'top_ch' not in current:
        tf = m.group(1); tfs = float(m.group(2))
        bf = m.group(3); bfs = float(m.group(4))
        if tf == 'chamfer': current['top_ch'] = round(tfs * 1000, 1)
        elif tf == 'fillet': current['top_fr'] = round(tfs * 1000, 1)
        if bf == 'chamfer': current['btm_ch'] = round(bfs * 1000, 1)
        elif bf == 'fillet': current['btm_fr'] = round(bfs * 1000, 1)
    
    # Stored chamfer/fillet from cone_groove path (already in mm)
    m = re.search(r'->\s+cone_groove!.*?\btop_ch=([\d.]+)\s+top_fr=([\d.]+)\s+btm_ch=([\d.]+)\s+btm_fr=([\d.]+)', line)
    if m:
        current['top_ch'] = float(m.group(1))
        current['top_fr'] = float(m.group(2))
        current['btm_ch'] = float(m.group(3))
        current['btm_fr'] = float(m.group(4))
    
    # cone_stepped_hole export chamfer/fillet (mm)
    m = re.search(r'cone_stepped_hole:\s+top_ch=([\d.]+)\s+top_fr=([\d.]+)\s+btm_ch=([\d.]+)\s+btm_fr=([\d.]+)', line)
    if m:
        current['top_ch'] = float(m.group(1))
        current['top_fr'] = float(m.group(2))
        current['btm_ch'] = float(m.group(3))
        current['btm_fr'] = float(m.group(4))

if current:
    objects.append(current)

# Sort by name: Z-level prefix, then Y position, then object number
def sort_key(obj):
    name = obj.get('name', '')
    # Extract prefix (S1, S2, ..., GS1, ...) and number
    m = re.match(r'([A-Z]*\d+)_?(.*)', name)
    if m:
        prefix = m.group(1)
        rest = m.group(2)
        # Sort GS after S (groove variants)
        order = 0 if prefix.startswith('S') else (1 if prefix.startswith('GS') else 2)
        # Extract numeric part
        num = int(re.search(r'\d+', prefix).group())
        return (order, num, rest)
    return (0, 0, name)

objects.sort(key=sort_key)

print(f'Total objects: {len(objects)}')
print()

# Group into groups of 12
for group_idx in range(16):
    start = group_idx * 12
    end = start + 12
    group = objects[start:end]
    
    if not group:
        break
    
    # Collect unique dimensional signatures
    sigs = set()
    for obj in group:
        br = obj.get('bR', 0)
        tr = obj.get('tR', 0)
        h = obj.get('h', 0)
        tc = obj.get('top_ch', 0)
        tf = obj.get('top_fr', 0)
        bc = obj.get('btm_ch', 0)
        bf = obj.get('btm_fr', 0)
        sig = (round(br, 1), round(tr, 1), round(h, 1), round(tc, 1), round(tf, 1), round(bc, 1), round(bf, 1))
        sigs.add(sig)
    
    names = [o['name'] for o in group]
    
    if len(sigs) == 1:
        sig = list(sigs)[0]
        print(f'Group {group_idx+1:2d} ({start+1:3d}-{end:3d}): ✓ UNIFORM  bR={sig[0]:.0f} tR={sig[1]:.0f} h={sig[2]:.0f}  top_ch={sig[3]:.1f} top_fr={sig[4]:.1f} btm_ch={sig[5]:.1f} btm_fr={sig[6]:.1f}')
    else:
        print(f'Group {group_idx+1:2d} ({start+1:3d}-{end:3d}): ✗ MISMATCH! {len(sigs)} variations:')
        for sig in sorted(sigs):
            objs = [o['name'] for o in group if (round(o.get('bR',0),1), round(o.get('tR',0),1), round(o.get('h',0),1), round(o.get('top_ch',0),1), round(o.get('top_fr',0),1), round(o.get('btm_ch',0),1), round(o.get('btm_fr',0),1)) == sig]
            print(f'          bR={sig[0]:.0f} tR={sig[1]:.0f} h={sig[2]:.0f} tc={sig[3]:.1f} tf={sig[4]:.1f} bc={sig[5]:.1f} bf={sig[6]:.1f} → {objs}')

print()
# Also check: do all objects have bR/tR/h?
missing = [o['name'] for o in objects if 'bR' not in o or 'h' not in o]
if missing:
    print(f'Objects missing dimensions: {len(missing)} → {missing[:20]}...')
