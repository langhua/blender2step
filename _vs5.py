"""STEP: filter h>10, get actual radii, group by Z row."""
import re, sys, math
from collections import deque, Counter
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
    if h<10: continue  # filter spurious
    zmin=min(zs); zmax=max(zs); ymax=max(ys)
    cx=(min(xs)+max(xs))/2; cy=(min(ys)+max(ys))/2
    
    eps=max(0.5, h*0.01)
    bot_pts=[c for c in coords if abs(c[2]-zmin)<eps]
    top_pts=[c for c in coords if abs(c[2]-zmax)<eps]
    bot_r=max((math.hypot(c[0]-cx,c[1]-cy) for c in bot_pts), default=0)
    top_r=max((math.hypot(c[0]-cx,c[1]-cy) for c in top_pts), default=0)
    
    solids.append({'zmin':zmin,'zmax':zmax,'ymax':ymax,'cx':cx,'cy':cy,
                   'h':h,'botR':bot_r,'topR':top_r})

print(f"Filtered solids: {len(solids)} (from {len(S2S)})")

# Sort by zmin, then ymax desc
solids.sort(key=lambda o:(o['zmin'],-o['ymax']))

# Show Z distribution
z_vals = [round(s['zmin'],-2) for s in solids]  # round to 100
zc = Counter(z_vals)
print("Z distribution:")
for z,cnt in sorted(zc.items()):
    print(f"  z~{z:.0f}: {cnt} objects")

# Group by Z row (nearest 2800)
zs = sorted(set(round(s['zmin'],-2) for s in solids))
print(f"\nUnique Z levels: {len(zs)}")

# For each Z level, group objects and show radii
for zl in zs:
    grp = [s for s in solids if abs(s['zmin']-zl)<100]
    grp.sort(key=lambda s:-s['ymax'])
    if len(grp)>=12:
        hs=[round(s['h'],1) for s in grp]
        bs=[round(s['botR'],1) for s in grp]
        ts=[round(s['topR'],1) for s in grp]
        h_ok="✓" if len(set(hs))==1 else f"MISMATCH:{sorted(set(hs))}"
        b_ok="✓" if len(set(bs))==1 else f"MISMATCH:{sorted(set(bs))}"
        t_ok="✓" if len(set(ts))==1 else f"MISMATCH:{sorted(set(ts))}"
        print(f"Z~{zl:.0f} ({len(grp)}obj): H={hs[0]:.0f} BotR={bs[0]:.0f} TopR={ts[0]:.0f}  H:{h_ok}  Bot:{b_ok}  Top:{t_ok}")
    else:
        print(f"Z~{zl:.0f} ({len(grp)}obj): too few objects")
