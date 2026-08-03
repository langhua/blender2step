"""Analyze B-rep faces: wall angle at rim top (z~51) vs center. Verify rim edges vertical."""
import sys, math, io
sys.path.insert(0, r"f:\git\blender2step\step_exporter\lib")
import _step_exporter as m

LOG = r"f:\git\blender2step\_faces2.txt"
out = []
def analyze(corner, rtype, label):
    faces = m.analyze_shell_faces(100, 80, 50, 2, 2, corner, 5.0, rtype, 1.0, 1.0, 'rect', 1.0,
                                  0.0, 0.5, 0.0, '', 64, 0.5)
    if faces is None:
        out.append(f"{label}: FAILED"); return
    out.append(f"\n{label}: {len(faces)} faces  (tilt_center | tilt_top)")
    out.append(f"  {'type':<8} {'zmin':>7} {'zmax':>7} {'pt':>8} {'tiltC':>6} {'tiltT':>6}")
    for (t, zmin, zmax, px, py, pz, cx, cy, cz, tx, ty, tz, tc, tt) in faces:
        is_rim = zmax > 50.4
        mark = " <==RIM" if is_rim else ""
        out.append(f"  {t:<8} {zmin:>7.2f} {zmax:>7.2f} {px:>8.1f} {tc:>6.1f} {tt:>6.1f}{mark}")
    # Focus: bspline wall faces that reach the rim top (zmax>50.4) — their tilt at TOP
    out.append("\n  Wall faces reaching rim top (zmax>50.4):")
    for (t, zmin, zmax, px, py, pz, cx, cy, cz, tx, ty, tz, tc, tt) in faces:
        if t == 'bspline' and zmax > 50.4:
            out.append(f"    {t} z[{zmin:.1f},{zmax:.1f}] at pt=({px:.1f},{py:.1f})  tilt_center={tc:.1f}°  tilt_TOP={tt:.1f}°")

analyze('curved', 'outside', "CURVED outside rim")
analyze('curved', 'inside',  "CURVED inside rim")
analyze('rounded', 'outside', "ROUNDED outside rim (ref)")
with io.open(LOG,'w',encoding='utf-8') as f:
    f.write('\n'.join(out))
print("WROTE")
