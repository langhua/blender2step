"""TRIANGLE-based: rim raised-edge continuity at straight walls, curved vs rounded."""
import sys, math, io
sys.path.insert(0, r"f:\git\blender2step\step_exporter\lib")
import _step_exporter as m

LOG = r"f:\git\blender2step\_vert14.txt"
def tri_centroid(v0,v1,v2):
    return ((v0[0]+v1[0]+v2[0])/3,(v0[1]+v1[1]+v2[1])/3,(v0[2]+v1[2]+v2[2])/3)
def tri_normal(v0,v1,v2):
    u=(v1[0]-v0[0],v1[1]-v0[1],v1[2]-v0[2]); w=(v2[0]-v0[0],v2[1]-v0[1],v2[2]-v0[2])
    return (u[1]*w[2]-u[2]*w[1], u[2]*w[0]-u[0]*w[2], u[0]*w[1]-u[1]*w[0])

out = []
for corner in ('curved', 'rounded'):
    res = m.generate_parametric_shell_mesh(
        100, 80, 50, 2, 2, corner, 5.0, 'outside', 1.0, 1.0, 'rect', 1.0,
        0.0, 0.5, 0.0, '', 64, 0.5)
    vs, tris = res['vertices'], res['triangles']
    rim = []
    for (a,b,c) in tris:
        v0,v1,v2 = vs[a],vs[b],vs[c]
        cc = tri_centroid(v0,v1,v2)
        if 50.0 <= cc[2] <= 51.0:
            n = tri_normal(v0,v1,v2); mag=math.sqrt(n[0]**2+n[1]**2+n[2]**2)
            if mag<1e-12: continue
            rim.append((cc[0], cc[1], cc[2], n[0]/mag, n[1]/mag, n[2]/mag))
    out.append(f"\n{corner}: triangles in rim band z[50,51] = {len(rim)}")
    rw = [t for t in rim if t[0] > 48.0 and t[3] > 0.7]
    fw = [t for t in rim if t[1] > 38.0 and t[4] > 0.7]
    if rw:
        ys = sorted(t[1] for t in rw)
        gaps = [f"{ys[i]:.0f}-{ys[i+1]:.0f}" for i in range(len(ys)-1) if ys[i+1]-ys[i] > 3]
        out.append(f"  right-wall rim tris: {len(rw)}, y range [{min(ys):.0f},{max(ys):.0f}] gaps={gaps if gaps else 'NONE (continuous)'}")
    else:
        out.append("  right-wall rim tris: 0")
    if fw:
        xs = sorted(t[0] for t in fw)
        gaps = [f"{xs[i]:.0f}-{xs[i+1]:.0f}" for i in range(len(xs)-1) if xs[i+1]-xs[i] > 3]
        out.append(f"  front-wall rim tris: {len(fw)}, x range [{min(xs):.0f},{max(xs):.0f}] gaps={gaps if gaps else 'NONE (continuous)'}")
    else:
        out.append("  front-wall rim tris: 0")
with io.open(LOG,'w',encoding='utf-8') as f:
    f.write('\n'.join(out))
print("WROTE")
