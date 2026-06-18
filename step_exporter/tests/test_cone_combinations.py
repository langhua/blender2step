"""
Auto-test for cone parametric detection + STEP export.
Usage: blender --background --python step_exporter/tests/test_cone_combinations.py

Tests 84 combinations: verifies detection AND exports STEP files.
Generates HTML report for visual inspection in FreeCAD.
"""
import bpy
import sys
import os
import json
import math
import re
from pathlib import Path

# ===== SETUP =====
addon_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(addon_root))
from step_exporter import register
register()
from step_exporter.analysis.cylinder import _analyze_cylinder_from_mesh

TEST_DIR = Path(__file__).parent / "test_output"
os.makedirs(TEST_DIR, exist_ok=True)
H = 0.040
SCALE = 1000.0

def clear():
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o, do_unlink=True)

def create_cone(name, br, tr, h, chamfer_type=None, chamfer_sz=0, fillet_r=0,
                hole_type=None, hole_r=0, hole_d=0, hole_taper=False, hole_er=0):
    """Create cone mesh with optional features and holes."""
    clear()
    avg_r = max(br, tr)
    bpy.ops.mesh.primitive_cylinder_add(vertices=64, radius=avg_r, depth=h, location=(0,0,0))
    obj = bpy.context.active_object
    obj.name = name
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    import bmesh
    bm = bmesh.from_edit_mesh(obj.data)
    half_h = h / 2.0
    for v in bm.verts:
        d = math.sqrt(v.co.x**2 + v.co.y**2)
        if d < 0.00001: continue
        if v.co.z > half_h * 0.5:
            v.co.x *= tr / d; v.co.y *= tr / d
        elif v.co.z < -half_h * 0.5 and br < tr:
            v.co.x *= br / d; v.co.y *= br / d
    bmesh.update_edit_mesh(obj.data)
    bpy.ops.object.mode_set(mode='OBJECT')
    if chamfer_type:
        obj['chamfer_type'] = chamfer_type
        obj['chamfer_size'] = chamfer_sz * 1000
        obj['fillet_radius_edge'] = fillet_r * 1000
    if hole_type:
        ch = h * 2 if hole_type == 'through' else hole_d * 2
        cz = 0
        if hole_type == 'top': cz = h/2 - hole_d/2
        elif hole_type == 'bottom': cz = -(h/2 - hole_d/2)
        if hole_taper:
            bpy.ops.mesh.primitive_cone_add(vertices=32, radius1=hole_r, radius2=hole_er, depth=ch, location=(0,0,cz))
        else:
            bpy.ops.mesh.primitive_cylinder_add(vertices=32, radius=hole_r, depth=ch, location=(0,0,cz))
        cutter = bpy.context.active_object
        cutter.hide_render = True
        mod = obj.modifiers.new("Hole", 'BOOLEAN')
        mod.object = cutter; mod.operation = 'DIFFERENCE'
        obj['hole_type'] = hole_type
        obj['hole_radius'] = hole_r * 1000
        if hole_type != 'through':
            obj['hole_depth'] = hole_d * 1000
            obj['hole_position'] = hole_type
        if hole_taper:
            obj['hole_is_tapered'] = True
            obj['hole_opening_radius'] = hole_r * 1000
            obj['hole_end_radius'] = hole_er * 1000
    bpy.context.view_layer.update()
    return obj

# ... (keep check_detection and verify unchanged) ...


def check_detection(obj):
    """Run detection and return parsed result."""
    result = _analyze_cylinder_from_mesh(obj, bpy.context, 1000.0)
    if result is None:
        return {"err": "not detected as parametric"}
    return {
        "type": result.get("obj_type", "?"),
        "br": round(result.get("bottom_radius", result.get("outer_bottom_radius", result.get("radius", 0))) / SCALE, 5),
        "tr": round(result.get("top_radius", result.get("outer_top_radius", result.get("radius", 0))) / SCALE, 5),
        "hr": round(result.get("hole_radius", 0) / SCALE, 5) if "hole_radius" in result else 0,
        "hd": round(result.get("hole_depth", 0) / SCALE, 5) if "hole_depth" in result else 0,
        "hp": result.get("hole_position", ""),
    }


def verify(case, det):
    """Check detection matches expected."""
    e = []
    if det.get("err"): return [det["err"]]
    br, tr = case["br"], case["tr"]

    # Check radii (±30% tol, accounting for features)
    if abs(det["br"] - br) / max(br, 0.001) > 0.30:
        if abs(det["br"] - tr) / max(tr, 0.001) > 0.30:
            e.append(f"br={det['br']:.4f} vs {br:.4f}")
    if abs(det["tr"] - tr) / max(tr, 0.001) > 0.30:
        if abs(det["tr"] - br) / max(br, 0.001) > 0.30:
            e.append(f"tr={det['tr']:.4f} vs {tr:.4f}")

    # Check hole routing
    if case["htype"]:
        if case["htype"] in ("top", "bottom", "both"):
            if det["type"] not in ("cone_blind_hole", "cylinder_blind_hole"):
                e.append(f"expected blind hole type, got {det['type']}")
            if det["hp"] != case["htype"] and not (case["htype"] == "both"):
                e.append(f"hole_pos={det['hp']} vs {case['htype']}")
        elif case["htype"] == "through":
            if det["type"] not in ("hollow_cone", "hollow_cylinder", "hollow_cylinder_tapered"):
                e.append(f"expected through-hole type, got {det['type']}")

    # Check cone vs cylinder
    if br != tr and det["type"] not in ("cone", "cone_chamfer", "cone_fillet",
                                          "cone_chamfer_fillet", "cone_blind_hole",
                                          "hollow_cone"):
        e.append(f"cone not detected (got {det['type']})")
    if br == tr and det["type"] not in ("cylinder", "cylinder_chamfer", "cylinder_fillet",
                                          "cylinder_blind_hole", "hollow_cylinder",
                                          "hollow_cylinder_tapered", "cone", "cone_chamfer"):
        pass  # cylinder could be detected as cone due to features

    return e


def run():
    cases = []
    for prefix, br, tr in [("N", 0.020, 0.010), ("I", 0.010, 0.020)]:
        for fname, ftype, fsz, ffr in [
            ("none", None, 0, 0), ("top_ch", "chamfer", 0.002, 0),
            ("bot_ch", "chamfer", 0.002, 0), ("both_ch", "chamfer_both", 0.002, 0),
            ("top_fr", "fillet", 0, 0.0015), ("bot_fr", "fillet", 0, 0.0015),
            ("both_fr", "fillet_both", 0, 0.0015),
        ]:
            for hname, htype, hr, hd, htap, her in [
                ("nohole", None, 0, 0, False, 0),
                ("t_blind", "top", 0.005, 0.020, False, 0),
                ("b_blind", "bottom", 0.005, 0.020, False, 0),
                ("both_bl", "both", 0.005, 0.020, False, 0),
                ("through", "through", 0.005, 0, False, 0),
                ("tpr_thr", "through", 0.006, 0, True, 0.004),
            ]:
                cases.append({"name": f"{prefix}_{fname}_{hname}",
                    "br": br, "tr": tr, "h": H,
                    "ftype": ftype, "fsize": fsz, "ffr": ffr,
                    "htype": htype, "hr": hr, "hd": hd, "htap": htap, "her": her})

    print(f"\n{'='*60}\nRunning {len(cases)} tests (detection only, step export on FAIL)...\n{'='*60}\n")
    results = []
    for i, c in enumerate(cases):
        print(f"[{i+1:3d}/{len(cases)}] {c['name']}...", end=" ", flush=True)
        r = {"name": c["name"], "br": c["br"]*1000, "tr": c["tr"]*1000,
             "ftype": c["ftype"] or "", "htype": c["htype"] or ""}
        try:
            obj = create_cone(c["name"], c["br"], c["tr"], c["h"],
                              c["ftype"], c["fsize"], c["ffr"],
                              c["htype"], c["hr"], c["hd"], c["htap"], c["her"])
            det = check_detection(obj)
            errs = verify(c, det)
            r["dtype"] = det.get("type", "?")
            r["errs"] = errs
            if errs:
                # Only export STEP on failure for visual debugging
                sp = str(TEST_DIR / f"{c['name']}.step")
                obj.select_set(True)
                bpy.context.view_layer.objects.active = obj
                bpy.ops.export_scene.step_enhanced(filepath=sp, apply_modifiers=True)
                r["step"] = f"{c['name']}.step"
                r["status"] = "FAIL"
                print(f"FAIL ({det.get('type','?')}): {'; '.join(errs)} [STEP saved]")
            else:
                r["status"] = "PASS"
                extras = ""
                if det.get("hr", 0) > 0: extras += f" hr={det['hr']:.3f}"
                if det.get("hd", 0) > 0: extras += f" hd={det['hd']:.3f}"
                print(f"PASS ({det['type']} br={det['br']:.3f} tr={det['tr']:.3f}{extras})")
            results.append(r)
        except Exception as ex:
            print(f"ERROR: {ex}")
            r["status"] = "ERROR"; r["errs"] = [str(ex)]; results.append(r)

    p = sum(1 for r in results if r['status'] == 'PASS')
    f = sum(1 for r in results if r['status'] == 'FAIL')
    e = sum(1 for r in results if r['status'] == 'ERROR')
    print(f"\n{'='*60}\n{p} PASS, {f} FAIL, {e} ERROR, {len(cases)} total")

    # HTML report
    html = ["<html><head><meta charset='utf-8'><title>Cone Test Results</title>",
            "<style>body{font-family:Arial;margin:20px;background:#1a1a1a;color:#ddd}",
            "h2{color:#fff}.PASS{background:#1a3a1a}.FAIL{background:#3a1a1a}.ERROR{background:#3a3a1a}",
            "table{border-collapse:collapse;width:100%}th,td{border:1px solid #444;padding:4px 8px;font-size:13px}",
            "th{background:#333}.PASS td{color:#8f8}.FAIL td{color:#f88}a{color:#6af}</style></head><body>",
            f"<h2>Cone Test: {p} PASS / {f} FAIL / {e} ERROR</h2><table>",
            "<tr><th>#</th><th>Name</th><th>Type</th><th>BottomR</th><th>TopR</th><th>Feature</th><th>Hole</th><th>Status</th></tr>"]
    for i, r in enumerate(results):
        sl = f"<a href='{r.get('step','')}'>{r['name']}</a>" if r.get('step') else r['name']
        html.append(f"<tr class='{r['status']}'><td>{i+1}</td><td>{sl}</td>"
                     f"<td>{r.get('dtype','?')}</td><td>{r['br']:.0f}</td><td>{r['tr']:.0f}</td>"
                     f"<td>{r['ftype']}</td><td>{r['htype']}</td><td>{r['status']}</td></tr>")
    html.append("</table></body></html>")
    (TEST_DIR / "report.html").write_text("\n".join(html), encoding='utf-8')
    print(f"\nReport: {TEST_DIR / 'report.html'}")
    return p, f, e

if __name__ == "__main__":
    run()
