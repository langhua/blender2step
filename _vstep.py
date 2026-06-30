"""Analyze STEP - BFS vertex collection."""
import re, sys
from collections import deque
sys.setrecursionlimit(50000)

def parse_all(filename):
    with open(filename, 'r', encoding='utf-8', errors='replace') as f:
        content = f.read()
    entities = {}
    for match in re.finditer(r'#(\d+)\s*=\s*(\w+)\((.*?)\);', content, re.DOTALL):
        eid = int(match.group(1))
        etype = match.group(2)
        raw = match.group(3)
        refs = [int(m) for m in re.findall(r'#(\d+)', raw)]
        nums = [float(x) for x in re.findall(r'[-+]?\d*\.?\d+(?:[Ee][-+]?\d+)?', raw)]
        entities[eid] = (etype, refs, nums)
    return entities

def collect_vertices_bfs(start_id, entities, max_nodes=500000):
    """Return list of (vertex_id, cartesian_point_id) tuples."""
    vertices = []  # (vtx_id, cp_id)
    visited = set()
    queue = deque([start_id])
    count = 0
    while queue and count < max_nodes:
        count += 1
        eid = queue.popleft()
        if eid in visited: continue
        visited.add(eid)
        if eid not in entities: continue
        etype, refs, nums = entities[eid]
        if etype == 'VERTEX_POINT' and refs:
            vertices.append((eid, refs[0]))  # refs[0] = CARTESIAN_POINT id
        elif etype != 'CARTESIAN_POINT':
            for ref in refs:
                if ref not in visited:
                    queue.append(ref)
    return vertices

print("Parsing STEP...")
entities = parse_all('F:/git/blender2step/step_exporter/test28.step')
print(f"Entities: {len(entities)}")

solid_to_shell = {}
for eid, (etype, refs, nums) in entities.items():
    if etype == 'MANIFOLD_SOLID_BREP' and refs:
        solid_to_shell[eid] = refs[0]

points = {}
for eid, (etype, refs, nums) in entities.items():
    if etype == 'CARTESIAN_POINT' and len(nums) >= 3:
        points[eid] = (nums[0], nums[1], nums[2])

print(f"Solids: {len(solid_to_shell)}, Points: {len(points)}")

solids = []
for solid_id, shell_id in sorted(solid_to_shell.items()):
    vtx_cp_pairs = collect_vertices_bfs(shell_id, entities)
    coords = [points[cp_id] for _, cp_id in vtx_cp_pairs if cp_id in points]
    if coords:
        xs=[c[0] for c in coords]; ys=[c[1] for c in coords]; zs=[c[2] for c in coords]
        solids.append({'id':solid_id,'zmin':min(zs),'zmax':max(zs),'ymax':max(ys),
                       'height':max(zs)-min(zs),'r':max(max(abs(c[0]),abs(c[1])) for c in coords),'n':len(coords)})
    else:
        print(f"  Solid #{solid_id}: no coords ({len(vtx_cp_pairs)} verts->CP)")

print(f"\nExtracted {len(solids)} solids with bbox data")
solids.sort(key=lambda o: (o['zmin'], -o['ymax']))

for g in range(len(solids)//12):
    group = solids[g*12:(g+1)*12]
    hs=[round(o['height'],3) for o in group]
    rs=[round(o['r'],1) for o in group]
    h_ok="MATCH" if len(set(hs))==1 else f"MISMATCH:{set(hs)}"
    r_ok="MATCH" if len(set(rs))==1 else f"MISMATCH:{set(rs)}"
    print(f"G{g+1:2d}: h={hs[0]:.1f} r={rs[0]:.0f} Height:{h_ok} Radius:{r_ok}")

print(f"\nTotal: {len(solids)} solids in {len(solids)//12} groups")
