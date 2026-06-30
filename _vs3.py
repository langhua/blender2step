"""STEP analysis v3: better sorting + get radii from bbox vertices at zmin/zmax."""
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

print("Parsing...")
E = parse_all('F:/git/blender2step/step_exporter/test28.step')
print(f"Entities: {len(E)}")

S2S={}
for e,(t,r,n) in E.items():
    if t=='MANIFOLD_SOLID_BREP' and r: S2S[e]=r[0]

V2P={}
for e,(t,r,n) in E.items():
    if t=='VERTEX_POINT' and r: V2P[e]=r[0]

PTS={}
for e,(t,r,n) in E.items():
    if t=='CARTESIAN_POINT' and len(n)>=3: PTS[e]=(n[0],n[1],n[2])

print(f"Solids: {len(S2S)}, Points: {len(PTS)}")

solids=[]
for sid,sh in sorted(S2S.items()):
    ids=bfs_ids(sh,E)
    coords=[PTS[V2P[e]] for e in ids if e in V2P and V2P[e] in PTS]
    if not coords: continue
    xs=[c[0] for c in coords]; ys=[c[1] for c in coords]; zs=[c[2] for c in coords]
    zmin=min(zs); zmax=max(zs); ymax=max(ys)
    cx=(min(xs)+max(xs))/2; cy=(min(ys)+max(ys))/2
    
    # Get radii at zmin (bottom) and zmax (top) from vertices at those z levels
    eps=0.01
    bot_pts=[c for c in coords if abs(c[2]-zmin)<eps]
    top_pts=[c for c in coords if abs(c[2]-zmax)<eps]
    bot_r=max((math.hypot(c[0]-cx,c[1]-cy) for c in bot_pts), default=0)
    top_r=max((math.hypot(c[0]-cx,c[1]-cy) for c in top_pts), default=0)
    
    solids.append({'id':sid,'zmin':zmin,'zmax':zmax,'ymax':ymax,'cx':cx,'cy':cy,
                   'h':zmax-zmin,'botR':bot_r,'topR':top_r})

# Sort: group by Z row (round zmin to nearest 500), then Y- within row
solids.sort(key=lambda o:(round(o['zmin']/500)*500, -o['ymax']))
print(f"Sorted {len(solids)} solids")

for g in range(len(solids)//12):
    grp=solids[g*12:(g+1)*12]
    hs=set(round(o['h'],1) for o in grp)
    bs=set(round(o['botR'],1) for o in grp)
    ts=set(round(o['topR'],1) for o in grp)
    
    def fmt(s):
        vals=sorted(s)
        if len(s)==1: return f"✓ {vals[0]:.0f}"
        return f"✗ {vals}"
    
    print(f"G{g+1:2d}: H={fmt(hs)} BotR={fmt(bs)} TopR={fmt(ts)}")

print(f"\nTotal: {len(solids)} in {len(solids)//12} groups")
