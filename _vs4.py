"""Just show Z distribution of all 192 solids."""
import re, sys, math
from collections import deque
sys.setrecursionlimit(50000)

def parse_all(filename):
    with open(filename, 'r', encoding='utf-8', errors='replace') as f:
        content = f.read()
    entities = {}
    for match in re.finditer(r'#(\d+)\s*=\s*(\w+)\((.*?)\);', content, re.DOTALL):
        eid = int(match.group(1)); etype = match.group(2); raw = match.group(3)
        refs = [int(m) for m in re.findall(r'#(\d+)', raw)]
        nums = [float(x) for x in re.findall(r'[-+]?\d*\.?\d+(?:[Ee][-+]?\d+)?', raw)]
        entities[eid] = (etype, refs, nums)
    return entities

def bfs_ids(start, entities, mx=500000):
    ids=set(); vis=set(); q=deque([start]); c=0
    while q and c<mx:
        c+=1; eid=q.popleft()
        if eid in vis: continue; vis.add(eid)
        if eid not in entities: continue
        ids.add(eid)
        for r in entities[eid][1]:
            if r not in vis: q.append(r)
    return ids

E = parse_all('F:/git/blender2step/step_exporter/test28.step')

S2S={}
for e,(t,r,n) in E.items():
    if t=='MANIFOLD_SOLID_BREP' and r: S2S[e]=r[0]
V2P={}
for e,(t,r,n) in E.items():
    if t=='VERTEX_POINT' and r: V2P[e]=r[0]
PTS={}
for e,(t,r,n) in E.items():
    if t=='CARTESIAN_POINT' and len(n)>=3: PTS[e]=(n[0],n[1],n[2])

solids=[]
for sid,sh in sorted(S2S.items()):
    ids=bfs_ids(sh,E)
    coords=[PTS[V2P[e]] for e in ids if e in V2P and V2P[e] in PTS]
    if not coords: continue
    xs=[c[0] for c in coords]; ys=[c[1] for c in coords]; zs=[c[2] for c in coords]
    cx=(min(xs)+max(xs))/2; cy=(min(ys)+max(ys))/2
    solids.append({'zmin':min(zs),'zmax':max(zs),'ymax':max(ys),'cx':cx,'cy':cy,
                   'h':max(zs)-min(zs)})

# Sort by Z, then Y
solids.sort(key=lambda o:(o['zmin'],-o['ymax']))

print("First 30 solids (Z,Y positions):")
for i,s in enumerate(solids[:30]):
    print(f"  {i+1:3d}: zmin={s['zmin']:.1f} zmax={s['zmax']:.1f} h={s['h']:.1f} ymax={s['ymax']:.0f}")

print(f"\nUnique Z positions: {len(set(round(s['zmin'],1) for s in solids))}")
# Count per Z level
from collections import Counter
z_counts = Counter(round(s['zmin'],0) for s in solids)
for z,cnt in sorted(z_counts.items()):
    print(f"  z={z:.0f}: {cnt} objects")
