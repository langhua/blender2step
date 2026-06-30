"""STEP analysis v2: extract bbox + surface params."""
import re, sys
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
        if eid in vis: continue
        vis.add(eid)
        if eid not in entities: continue
        ids.add(eid)
        for r in entities[eid][1]:
            if r not in vis: q.append(r)
    return ids

print("Parsing...")
E = parse_all('F:/git/blender2step/step_exporter/test28.step')
print(f"Entities: {len(E)}")

# Solid -> Shell
S2S={}
for e,(t,r,n) in E.items():
    if t=='MANIFOLD_SOLID_BREP' and r: S2S[e]=r[0]

# VERTEX -> CARTESIAN_POINT
V2P={}
for e,(t,r,n) in E.items():
    if t=='VERTEX_POINT' and r: V2P[e]=r[0]

# CARTESIAN_POINT coords
PTS={}
for e,(t,r,n) in E.items():
    if t=='CARTESIAN_POINT' and len(n)>=3: PTS[e]=(n[0],n[1],n[2])

# Surface params
CONES={}; CYLS={}
for e,(t,r,n) in E.items():
    if t=='CONICAL_SURFACE' and len(n)>=2: CONES[e]=(n[0],n[1])
    elif t=='CYLINDRICAL_SURFACE' and len(n)>=1: CYLS[e]=n[0]

print(f"S:{len(S2S)} P:{len(PTS)} Cn:{len(CONES)} Cy:{len(CYLS)}")

solids=[]
for sid,sh in sorted(S2S.items()):
    ids=bfs_ids(sh,E)
    coords=[PTS[V2P[e]] for e in ids if e in V2P and V2P[e] in PTS]
    if not coords: continue
    xs=[c[0] for c in coords]; ys=[c[1] for c in coords]; zs=[c[2] for c in coords]
    cones=[CONES[e] for e in ids if e in CONES]
    cyls=[CYLS[e] for e in ids if e in CYLS]
    solids.append({'id':sid,'zmin':min(zs),'zmax':max(zs),'ymax':max(ys),
                   'h':max(zs)-min(zs),
                   'cones':sorted(cones,key=lambda x:-x[0]),
                   'cyls':sorted(cyls,key=lambda x:-x)})

solids.sort(key=lambda o:(o['zmin'],-o['ymax']))
print(f"Sorted {len(solids)} solids")

def outer_dims(o):
    """Return (height, botR, topR) in mm."""
    if o['cones']:
        return (round(o['h'],1), round(o['cones'][0][0],1), round(o['cones'][-1][0],1))
    elif o['cyls']:
        r=round(o['cyls'][0],1)
        return (round(o['h'],1), r, r)
    return (round(o['h'],1), 0, 0)

for g in range(len(solids)//12):
    grp=solids[g*12:(g+1)*12]
    dims=[outer_dims(o) for o in grp]
    hs=set(d[0] for d in dims); bs=set(d[1] for d in dims); ts=set(d[2] for d in dims)
    ok=lambda s:"✓" if len(s)==1 else f"✗{s}"
    print(f"G{g+1:2d}: h={list(hs)[0]:.0f} bR={list(bs)[0]:.0f} tR={list(ts)[0]:.0f}  H:{ok(hs)} Bot:{ok(bs)} Top:{ok(ts)}")

print(f"\nTotal: {len(solids)} in {len(solids)//12} groups")
