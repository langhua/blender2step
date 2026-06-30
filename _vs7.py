"""Cluster by dimension using x-range/2 for radii (position-independent)."""
import re, sys, math
from collections import deque, defaultdict, Counter
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

print("Parsing...")
E = parse_all('F:/git/blender2step/step_exporter/test28.step')
S2S={}; V2P={}; PTS={}
for e,(t,r,n) in E.items():
    if t=='MANIFOLD_SOLID_BREP' and r: S2S[e]=r[0]
    elif t=='VERTEX_POINT' and r: V2P[e]=r[0]
    elif t=='CARTESIAN_POINT' and len(n)>=3: PTS[e]=(n[0],n[1],n[2])

solids=[]
for sid,sh in sorted(S2S.items()):
    ids=bfs_ids(sh,E)
    coords=[PTS[V2P[e]] for e in ids if e in V2P and V2P[e] in PTS]
    if not coords: continue
    xs=[c[0] for c in coords]; ys=[c[1] for c in coords]; zs=[c[2] for c in coords]
    h=max(zs)-min(zs)
    if h<10: continue
    zmin=min(zs); zmax=max(zs); ymax=max(ys)
    
    # Radius = half the X range at that Z level (cones are axis-aligned)
    eps=max(0.5, h*0.02)
    bot_pts=[c[0] for c in coords if abs(c[2]-zmin)<eps]
    top_pts=[c[0] for c in coords if abs(c[2]-zmax)<eps]
    bot_r = (max(bot_pts)-min(bot_pts))/2 if bot_pts else 0
    top_r = (max(top_pts)-min(top_pts))/2 if top_pts else 0
    
    solids.append({'ymax':ymax,'zmin':zmin,'h':h,'botR':round(bot_r,1),'topR':round(top_r,1)})

print(f"Valid solids: {len(solids)}")

# Cluster by (botR, topR, h) - round to nearest 1mm
def key(s):
    return (round(s['botR']), round(s['topR']), round(s['h']))

clusters = defaultdict(list)
for s in solids:
    clusters[key(s)].append(s)

print(f"\n{len(clusters)} unique dimension groups:")
for k in sorted(clusters.keys(), key=lambda k: -clusters[k][0]['zmin']):
    grp = clusters[k]
    print(f"  botR={k[0]} topR={k[1]} h={k[2]}: {len(grp)} objects")

sizes = Counter(len(v) for v in clusters.values())
print(f"\nGroup sizes: {dict(sorted(sizes.items()))}")

# Are there exactly 16 groups of 12?
twelves = sum(1 for v in clusters.values() if len(v)==12)
print(f"Groups with 12 objects: {twelves}")
print(f"Groups with other counts: {sum(1 for v in clusters.values() if len(v)!=12)}")
