"""Quick test: parametric shell with round + rrect slots (partial depth)."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'step_exporter', 'lib'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'step_exporter'))

import _step_exporter as cpp
print("C++ version:", cpp.get_version())
print("has generate_parametric_shell_mesh:", hasattr(cpp, 'generate_parametric_shell_mesh'))
print("has export_parametric_shell_step:", hasattr(cpp, 'export_parametric_shell_step'))

# Shell: 100x80x50, wall=2mm, square corners
w, d, h, t, bt = 100.0, 80.0, 50.0, 2.0, 2.0

# No slots — baseline
res0 = cpp.generate_parametric_shell_mesh(
    w, d, h, t, bt, 'square', 0.0,
    'none', 0.0, 0.0, 'rect', 1.0,
    0.0, 0.5, 0.0, '', 64, 0.5, '')
print("baseline:", None if res0 is None else (len(res0['vertices']), len(res0['triangles'])))

# Round slot on RIGHT wall (+X): pos at (w/2, 0, h/2), r=5, depth=1.5mm (75% of 2mm)
# face_code 3 = right wall
slot_round = f"{w/2:.3f},{0:.3f},{h/2:.3f},{5.0:.3f},3,{1.5:.3f},3"
res1 = cpp.generate_parametric_shell_mesh(
    w, d, h, t, bt, 'square', 0.0,
    'none', 0.0, 0.0, 'rect', 1.0,
    0.0, 0.5, 0.0, '', 64, 0.5, slot_round)
print("round slot:", None if res1 is None else (len(res1['vertices']), len(res1['triangles'])))

# RRect slot on FRONT wall (-Y): pos at (0, -d/2, h/2), w=20, hh=10, cr=3, depth=1.6mm
# face_code 4 = front wall
slot_rrect = f"{0:.3f},{-d/2:.3f},{h/2:.3f},{20.0:.3f},4,{10.0:.3f},{3.0:.3f},{1.6:.3f},4"
res2 = cpp.generate_parametric_shell_mesh(
    w, d, h, t, bt, 'square', 0.0,
    'none', 0.0, 0.0, 'rect', 1.0,
    0.0, 0.5, 0.0, '', 64, 0.5, slot_rrect)
print("rrect slot:", None if res2 is None else (len(res2['vertices']), len(res2['triangles'])))

# Tapered round slot on LEFT wall (-X): r=6, depth=1.6, bottom_ratio=0.6 (60%)
# face_code 2 = left wall. New 8-field format: ...,radius,3,depth,bottom_ratio,face
slot_tapered = f"{-w/2:.3f},{0:.3f},{h/2:.3f},{6.0:.3f},3,{1.6:.3f},{0.6:.3f},2"
res_t = cpp.generate_parametric_shell_mesh(
    w, d, h, t, bt, 'square', 0.0,
    'none', 0.0, 0.0, 'rect', 1.0,
    0.0, 0.5, 0.0, '', 64, 0.5, slot_tapered)
print("tapered round slot:", None if res_t is None else (len(res_t['vertices']), len(res_t['triangles'])))

# Tapered rrect slot on RIGHT wall (fc=3): 20x10 cr3 depth1.6 ratio 0.5 → floor 10x5
# 10-field format: ...,w,4,h,cr,depth,bottom_ratio,face
slot_rrect_t = f"{w/2:.3f},{0:.3f},{h/2:.3f},{20.0:.3f},4,{10.0:.3f},{3.0:.3f},{1.6:.3f},{0.5:.3f},3"
res_rt = cpp.generate_parametric_shell_mesh(
    w, d, h, t, bt, 'square', 0.0,
    'none', 0.0, 0.0, 'rect', 1.0,
    0.0, 0.5, 0.0, '', 64, 0.5, slot_rrect_t)
print("tapered rrect slot:", None if res_rt is None else (len(res_rt['vertices']), len(res_rt['triangles'])))

# Both slots together
slots = slot_round + ';' + slot_rrect
res3 = cpp.generate_parametric_shell_mesh(
    w, d, h, t, bt, 'square', 0.0,
    'none', 0.0, 0.0, 'rect', 1.0,
    0.0, 0.5, 0.0, '', 64, 0.5, slots)
print("both slots:", None if res3 is None else (len(res3['vertices']), len(res3['triangles'])))

# INNER right-wall round slot (fc=9): inner surface at x = w/2 - t = 48mm
slot_inner = f"{(w/2-t):.3f},{0:.3f},{h/2:.3f},{5.0:.3f},3,{1.6:.3f},{1.0:.3f},9"
res_in = cpp.generate_parametric_shell_mesh(
    w, d, h, t, bt, 'square', 0.0,
    'none', 0.0, 0.0, 'rect', 1.0,
    0.0, 0.5, 0.0, '', 64, 0.5, slot_inner)
print("inner round slot:", None if res_in is None else (len(res_in['vertices']), len(res_in['triangles'])))

# Test export to STEP file (round + rrect + tapered round + tapered rrect + inner)
slots_all = slot_round + ';' + slot_rrect + ';' + slot_tapered + ';' + slot_rrect_t + ';' + slot_inner
out = os.path.join(os.path.dirname(__file__), 'test_slot_export.step')
ok = cpp.export_parametric_shell_step(
    out, w, d, h, t, bt, 0.0, 'square',
    0.0, 0.0, 0.0, 'none', 0.0, 0.0,
    'AP214IS', 'MILLIMETER', 0,
    'rect', 1.0, 0.0, 0.5, 0.0, '',
    0.0, 0.0, 0.0, 0.5, slots_all)
print("STEP export ok:", ok, "exists:", os.path.exists(out))
if os.path.exists(out):
    print("STEP file size:", os.path.getsize(out))
