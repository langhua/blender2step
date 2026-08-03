"""Verify rim mating faces are VERTICAL. Only vertical triangles (tilt<30deg), y~0."""
import sys, math, io
sys.path.insert(0, r"f:\git\blender2step\step_exporter\lib")
import _step_exporter as m

LOG = r"f:\git\blender2step\_vert3.txt"
def tri_normal(v0,v1,v2):
    u=(v1[0]-v0[0],v1[1]-v0[1],v1[2]-v0[2]); w=(v2[0]-v0[0],v2[1]-v0[1],v2[2]-v0[2])
    return (u[1]*w[2]-u[2]*w[1], u[2]*w[0]-u[0]*w[2], u[0]*w[1]-u[1]*w[0])

out = []
def measure(corner, rtype, label, zlo=49.6, zhi=51.1):
    res = m.generate_parametric_shell_mesh(
        100, 80, 50, 2, 2, corner, 5.0, rtype, 1.0, 1.0, 'rect', 1.0,
        0.0, 0.5, 0.0, '', 64, 0.5)
    if res is None:
        out.append(f"{label}: FAILED"); return
    vs, tris = res['vertices'], res['triangles']
    bands = {}
    for (a,b,c) in tris:
        v0,v1,v2 = vs[a],vs[b],vs[c]
        cz = (v0[2]+v1[2]+v2[2])/3.0
        if cz < zlo or cz > zhi: continue
        cxx = (v0[0]+v1[0]+v2[0])/3.0
        cyy = (v0[1]+v1[1]+v2[1])/3.0
        if abs(cyy) > 5: continue
        if not (46.0 <= cxx <= 52.0): continue
        n = tri_normal(v0,v1,v2); mag = math.sqrt(n[0]**2+n[1]**2+n[2]**2)
        if mag < 1e-12: continue
        nx,ny,nz = n[0]/mag,n[1]/mag,n[2]/mag
        tilt = math.degrees(math.atan2(abs(nz), math.hypot(nx,ny)))
        if tilt > 30: continue
        key = round(cxx*4)/4
        b = bands.setdefault(key, [0.0,0])
        b[0]+=tilt; b[1]+=1
    out.append(f"\n{label}: VERTICAL faces tilt (z[{zlo},{zhi}], y~0, tilt<30)")
    out.append(f"  {'x':>6} {'n':>4} {'tilt':>7}  (0=perfectly vertical)")
    for x in sorted(bands):
        t,c = bands[x]
        out.append(f"  {x:>6.2f} {int(c):>4} {t/c:>7.3f}")

measure('curved', 'outside', "A: CURVED outside rim — raised edge")
measure('curved', 'inside',  "B: CURVED inside rim — raised edge")
measure('rounded', 'outside', "C: ROUNDED outside (ref)")
out.append("\n=== Wall verticality just below rim (z 49.0-49.5) ===")
measure('curved', 'outside', "A2: CURVED outside — wall below rim", zlo=49.0, zhi=49.5)
with io.open(LOG,'w',encoding='utf-8') as f:
    f.write('\n'.join(out))
print("WROTE")
