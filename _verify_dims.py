import re

with open(r'F:\git\blender2step\step_exporter\test28.step.log', 'r') as f:
    lines = f.readlines()

objects = []
current = None

for line in lines:
    # New object detection - match all types
    m = re.search(r'\[STEP Exporter\] Found (\S+): (\S+)', line)
    if m:
        if current:
            objects.append(current)
        current = {'type': m.group(1), 'name': m.group(2), 'outer': {}}
        continue
    
    if current is None:
        continue
    
    # Primary: CLASSIFIED line (most reliable for outer dimensions)
    m = re.search(r'CLASSIFIED: cone\S*\s+bR=([\d.]+)\s+tR=([\d.]+)\s+h=([\d.]+)', line)
    if m:
        current['outer']['bR'] = round(float(m.group(1)), 2)
        current['outer']['tR'] = round(float(m.group(2)), 2)
        current['outer']['h'] = round(float(m.group(3)), 2)
        continue
    
    # Grooved cone detected / Cone detected
    m = re.search(r'(?:Grooved )?[Cc]one detected \(bR=([\d.]+) tR=([\d.]+)', line)
    if m and 'bR' not in current['outer']:
        current['outer']['bR'] = round(float(m.group(1)), 2)
        current['outer']['tR'] = round(float(m.group(2)), 2)
        continue
    
    # Height from Detected: ... height=X
    m = re.search(r'height=([\d.]+)', line)
    if m and 'h' not in current['outer']:
        h = float(m.group(1))
        if h > 100:  # mm units
            h = h / 1000
        current['outer']['h'] = round(h, 2)
        # Height line often also has bottom_r/top_r
        m2 = re.search(r'bottom_r=([\d.]+) top_r=([\d.]+)', line)
        if m2 and 'bR' not in current['outer']:
            current['outer']['bR'] = round(float(m2.group(1)), 2)
            current['outer']['tR'] = round(float(m2.group(2)), 2)
        continue
    
    # Cone top/bottom radius corrected lines (use the corrected value)
    m = re.search(r'Cone top radius corrected.*?: [\d.]+ -> ([\d.]+)', line)
    if m and 'tR' in current['outer']:
        current['outer']['tR'] = round(float(m.group(1)), 2)
        continue
    m = re.search(r'Cone bottom radius corrected.*?: [\d.]+ -> ([\d.]+)', line)
    if m and 'bR' in current['outer']:
        current['outer']['bR'] = round(float(m.group(1)), 2)
        continue
    
    # Height: detected from any bR/tR/h pattern
    m = re.search(r'-> cone_stepped_hole! bR=([\d.]+) tR=([\d.]+) h=([\d.]+)', line)
    if m:
        current['outer']['bR'] = round(float(m.group(1)), 2)
        current['outer']['tR'] = round(float(m.group(2)), 2)
        current['outer']['h'] = round(float(m.group(3)), 2)
        continue
    
    # cone_groove (extract outer dims + chamfer/fillet)
    m = re.search(r'-> cone_groove! r=([\d.]+) h=([\d.]+) top_ch=([\d.]+) top_fr=([\d.]+) btm_ch=([\d.]+) btm_fr=([\d.]+)', line)
    if m:
        current['outer']['bR'] = round(float(m.group(1)), 2)
        current['outer']['tR'] = round(float(m.group(1)), 2)
        current['outer']['h'] = round(float(m.group(2)), 2)
        current['outer']['top_ch'] = round(float(m.group(3)), 2)
        current['outer']['top_fr'] = round(float(m.group(4)), 2)
        current['outer']['btm_ch'] = round(float(m.group(5)), 2)
        current['outer']['btm_fr'] = round(float(m.group(6)), 2)
        continue
    
    # hollow_cone
    m = re.search(r'-> hollow_cone! bR=([\d.]+) tR=([\d.]+) h=([\d.]+)', line)
    if m:
        current['outer']['bR'] = round(float(m.group(1)), 2)
        current['outer']['tR'] = round(float(m.group(2)), 2)
        current['outer']['h'] = round(float(m.group(3)), 2)
        m2 = re.search(r'top_ch=([\d.]+) top_fr=([\d.]+) btm_ch=([\d.]+) btm_fr=([\d.]+)', line)
        if m2:
            current['outer']['top_ch'] = round(float(m2.group(1)), 2)
            current['outer']['top_fr'] = round(float(m2.group(2)), 2)
            current['outer']['btm_ch'] = round(float(m2.group(3)), 2)
            current['outer']['btm_fr'] = round(float(m2.group(4)), 2)
        continue
    
    # cylinder_blind_hole for cone objects: skip outer dims (use CLASSIFIED instead)
    # but extract chamfer/fillet from surrounding context
    m = re.search(r'-> cylinder_blind_hole! r=([\d.]+) h=([\d.]+)', line)
    if m:
        # Don't overwrite outer dims - CLASSIFIED line is more accurate
        continue

# Add last object
if current:
    objects.append(current)

# Now group by outer dimensions
from collections import defaultdict

def norm(v):
    """Normalize: convert mm to m if needed"""
    if abs(v) > 100:
        return round(v / 1000, 2)
    return round(v, 2)

groups = defaultdict(list)
for obj in objects:
    o = obj['outer']
    bR = norm(o.get('bR', 0))
    tR = norm(o.get('tR', 0))
    h = norm(o.get('h', 0))
    tc = norm(o.get('top_ch', 0))
    tf = norm(o.get('top_fr', 0))
    bc = norm(o.get('btm_ch', 0))
    bf = norm(o.get('btm_fr', 0))
    key = f"bR={bR:.2f} tR={tR:.2f} h={h:.2f} tc={tc:.2f} tf={tf:.2f} bc={bc:.2f} bf={bf:.2f}"
    groups[key].append(obj['name'])

with open(r'F:\git\blender2step\_verify_dims.txt', 'w') as out:
    out.write(f"Total objects: {len(objects)}\n")
    out.write(f"Unique outer dimension groups: {len(groups)}\n\n")
    
    for i, (key, names) in enumerate(sorted(groups.items(), key=lambda x: -len(x[1]))):
        out.write(f"=== Group {i+1} ({len(names)} objects) ===\n")
        out.write(f"  Dimensions: {key}\n")
        out.write(f"  Objects: {', '.join(sorted(names))}\n\n")
    
    # Verify the 12-per-group pattern
    out.write("=== Group size verification ===\n")
    sizes = sorted([len(v) for v in groups.values()])
    out.write(f"Group sizes: {sizes}\n")
    all_12 = all(s == 12 for s in sizes)
    out.write(f"All groups have 12 objects: {all_12}\n")
    out.write(f"Expected 16 groups: {len(groups) == 16}\n")
    
    # Also write per-object details
    out.write("\n=== Per-object details ===\n")
    for obj in sorted(objects, key=lambda x: x['name']):
        o = obj['outer']
        out.write(f"{obj['name']:20s} {obj['type']:25s} bR={o.get('bR',0):.2f} tR={o.get('tR',0):.2f} h={o.get('h',0):.2f} tc={o.get('top_ch',0):.2f} tf={o.get('top_fr',0):.2f} bc={o.get('btm_ch',0):.2f} bf={o.get('btm_fr',0):.2f}\n")

print(f"Done. {len(objects)} objects, {len(groups)} unique groups.")
print(f"Group sizes: {sizes}")
