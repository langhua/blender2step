"""Verify 5-hole rrect scenario (user's report) in BOTH preview and STEP export.
3 bottom rrects (OUTER/INNER/BOTH) + 2 side rrects (OUTER/BOTH).
"""
import sys, os, math, tempfile

_lib = os.path.join(os.path.dirname(__file__), 'step_exporter', 'lib')
os.add_dll_directory(_lib); sys.path.insert(0, _lib)
import _step_exporter as cpp

WD_ALL = ("0,0,1,14,2,10,1.5,0.8,0,0;"     # x=0 bottom OUTER
          "-22,0,1,14,2,10,1.5,0.8,1,0;"  # x=-22 bottom INNER
          "22,0,1,14,2,10,1.5,0.8,2,0;"   # x=+22 bottom BOTH
          "45.5,0,22,12,2,8,1.5,0.8,0,3;" # right wall OUTER
          "45.5,-18,22,12,2,8,1.5,0.8,2,3") # right wall BOTH

def wall_x(z, inset):
    t = z/50.0
    cur = 50 - 10*(1 - (1+math.cos(math.pi*t))/2)
    return cur - inset

def count_bottom(verts, hx, hy):
    o = i = 0
    for (x, y, z) in verts:
        r = ((x-hx)**2 + (y-hy)**2)**0.5
        if 6.0 <= r <= 9.0:
            if z < 0.8: o += 1
            elif z > 1.2: i += 1
    return o, i

def count_side(verts, hy, hz):
    ox = wall_x(hz, 0.0); ix = wall_x(hz, 2.0)
    o = i = 0
    for (x, y, z) in verts:
        if abs(y-hy) > 10 or abs(z-hz) > 10: continue
        if x > ox + 0.3: o += 1
        elif x < ix - 0.3: i += 1
    return o, i

print("=== PREVIEW: 5 rrects combined ===")
r = cpp.generate_parametric_shell_mesh(
    100,80,50,2,2,'curved',5,'inside',1.5,1.0,'rect',1.0,2.0,0.5,0.0,WD_ALL,64)
print(f"  mesh: {'OK' if r else 'NONE'}")
if r:
    for hx, lbl in [(0,'BOT x=0 OUTER'),(-22,'BOT x=-22 INNER'),(22,'BOT x=+22 BOTH')]:
        o, i = count_bottom(r['vertices'], hx, 0)
        print(f"    {lbl}: outer={o} inner={i}")
    for hy, lbl in [(0,'SIDE y=0 OUTER'),(-18,'SIDE y=-18 BOTH')]:
        o, i = count_side(r['vertices'], hy, 22)
        print(f"    {lbl}: outer={o} inner={i}")

print("=== STEP EXPORT: 5 rrects combined ===")
out = os.path.join(tempfile.gettempdir(), 'test_rrect_5hole.step')
ok = cpp.export_parametric_shell_step(
    out, 100,80,50,2,2,5,'curved',0,0,0,'inside',1.5,1.0,'AP214IS','MILLIMETER',1,
    'rect',1.0,2.0,0.5,0.0,WD_ALL,0,0,0)
print(f"  export: {'OK' if ok else 'FAIL'}")
if ok and os.path.exists(out):
    print(f"  file: {out} ({os.path.getsize(out)} bytes)")
