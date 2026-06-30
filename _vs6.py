"""Cluster objects by outer dimensions to find natural groups."""
import re, sys, math
from collections import deque, defaultdict
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
    cx=(min(xs)+max(xs))/2; cy=(min(ys)+max(ys))/2
    eps=max(0.5, h*0.01)
    bot_pts=[c for c in coords if abs(c[2]-zmin)<eps]
    top_pts=[c for c in coords if abs(c[2]-zmax)<eps]
    bot_r=max((math.hypot(c[0]-cx,c[1]-cy) for c in bot_pts), default=0)
    top_r=max((math.hypot(c[0]-cx,c[1]-cy) for c in top_pts), default=0)
    solids.append({'ymax':ymax,'zmin':zmin,'h':h,'botR':round(bot_r,1),'topR':round(top_r,1)})

print(f"Valid solids: {len(solids)}")

# Cluster by (botR, topR, h) rounded to nearest 5 for botR/topR, nearest 10 for h
def key(s):
    return (round(s['botR']/5)*5, round(s['topR']/5)*5, round(s['h']/10)*10)

clusters = defaultdict(list)
for s in solids:
    clusters[key(s)].append(s)

print(f"\nDimension clusters ({len(clusters)} unique):")
for k in sorted(clusters.keys(), key=lambda k: (-clusters[k][0]['zmin'], clusters[k][0]['ymax'])):
    grp = clusters[k]
    print(f"  botR={k[0]:.0f} topR={k[1]:.0f} h~{k[2]:.0f}: {len(grp)} objects, z~{grp[0]['zmin']:.0f}, y~{grp[0]['ymax']:.0f}")

# Now check: are there exactly 12 objects per dimension cluster?
counts = Counter(len(v) for v in clusters.values())
print(f"\nCluster sizes: {dict(counts)}")
