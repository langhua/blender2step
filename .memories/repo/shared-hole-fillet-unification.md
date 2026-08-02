# Shared Hole Fillet Unification (2026-08-02)

## Problem
Blender preview (inner fillet correct) vs STEP export (inner became BOTH sides).
Root cause: STEP export had its OWN old inline fillet logic (flat-wall midpoint
classification) while preview used shared `apply_hole_fillets` (single-best-edge,
distance band). On curved walls the old classification misclassified outer-rim
fragments as inner → filleted both rims.

## Fix
- STEP export now calls the SAME `apply_hole_fillets` as preview (guaranteed parity).
- Added file-scope `HoleFilletInfo` + forward declaration of `apply_hole_fillets`
  before `export_parametric_shell_step`; removed local struct + huge inline block.
- `apply_hole_fillets` now handles BOTH round and rrect holes:
  - **Round** (r>0.001): single best outer/inner edge per rim (dist band
    effR*0.5..1.6; outer=max|midCoord| except fc=0 bottom where outer=min|z|).
  - **Rrect** (r<0.001): collect ALL rim edges (8 edges/rim), split outer/inner
    by rim-band midpoint, fillet whole selected side (multi-edge rim).
- This also FIXED a latent crash: `TopOpeBRepDS_DataStructure::Point` on
  3-rrect-bottom-hole config (test30) — now works in both preview and export.

## Verification
- fc=2 round INNER: preview outer-rim=360/inner-rim=3027; STEP bspline=17 (1 fillet)
- fc=2 round BOTH: preview outer=952/inner=3223; STEP bspline=18 (2 fillets)
- test30 (3 rrect fc=0): exports OK, preview verts=11579

## 2026-08-02 follow-up: bottom-face (fc=0) round holes NOT cut through — FIXED
- **Symptom**: round through-holes on the bottom face were blocked by a residual
  floor (hole visible from inside only); side-wall and rrect bottom holes fine.
- **Root cause**: round cutter for fc=0/1 was `gp_Ax2(gp_Pnt(cx,cy,cz-0.5), dirZ)`
  — extends ONLY upward from cz-0.5. When cz>0.5 (user click slightly above the
  bottom face), the cylinder start is above the exterior bottom (z=0) → floor
  remains (rim at z=cz-0.5 instead of z=0).
- **Fix** (BOTH `export_parametric_shell_step` and `cut_holes_into_shape`):
  center the cylinder at the hole: `gp_Ax2(gp_Pnt(cx,cy,cz - cyl_len/2.0), dirZ)`.
  Now extends below z=0 for any cz. Side-wall cutters were already centered
  (`cx - cyl_len/2`); rrect bottom cutter already centered (`cz - cut_d/2`).
- **Verify**: cz=0..2 all give rim@z=0 (exterior), minz≈-16.88 (cutter below
  shell). STEP: rim@z0 present; PREVIEW: rim@z0=84. Fillets inner/outer/both OK.
- No regression: side-wall round INNER/BOTH/OUTER bspline 17/18/17; test30 full
  + bottom round inner exports OK.

## 2026-08-02 follow-up 2: bottom-face round fillets MISSING (curve midpoint fix)
- **Symptom**: 3 round bottom holes (outer/inner/both) had NO rim fillet at all
  (Blender preview AND STEP). Side walls + rrect fine. STEP bspline=16 (no fillet).
- **Root cause**: `apply_hole_fillets` computed edge dist from the **bounding-box
  midpoint**. On a PLANAR bottom face the boolean cut yields a CLEAN FULL circular
  rim edge whose bbox center is ON the hole axis → dist≈0 → wrongly excluded from
  the rim band [effR*0.5, effR*1.6]. Only cylinder seam edges (dist=effR, z=mid)
  were found → rimSep=0 → no fillet. Side walls worked because NURBS fragments the
  rim into arcs whose bbox midpoints sit near the rim.
- **Fix**: compute dist/midCoord from the edge's **actual curve midpoint**
  (`BRep_Tool::Curve` → `cv->Value((f0+f1)/2)`), which lies ON the circle at
  dist≈effR. Rim circles at z=0 and z=2 now both found → rimSep=2 → fillet applies.
- **Verify** (100x80x50 wall=2): STEP toroidal=4; PREVIEW OUTER outer-rim=504/
  inner-rim=84, INNER outer=84/inner=504, BOTH outer=504/inner=504. Regression:
  side INNER/BOTH/OUTER bspline 17/18/17, rrect toroidal=8, user test30 (3 round
  bottom + round side) toroidal=4, no-fillet toroidal=0.

## 2026-08-02 follow-up 3: rrect on cosine side wall + bottom — CONFIRMED OK
- **Symptom (false alarm)**: my own test showed side-wall rrect (fc=2) had NO
  fillet (toroidal=0, bspline=0) and no rim edges in x∈[48,50].
- **Root cause: TEST CONFIG ERROR.** I placed the side hole at cx=50 (assuming a
  planar right wall at x=50). But the COSINE (curved) shell's right wall at
  z=22 is actually at x≈[44.5,46.5] (wall=2). Cutter X∈[46,54] only pierced the
  outer half [46,46.5] → hole rim at x∈[46,47.29] = cutter end-face, no true rim.
  The code was fine all along.
- **Correct center for cosine wall tests**: at z, right wall outer = hw(z), inner
  = hw(z)-thickness; hw shrinks 50→40 from bottom to top (cosine inset
  total_inset=min(hw,hd)*curve_ratio*0.5=10). At z=22 outer≈46.5, inner≈44.5, so
  use cx≈45.5 for a side hole at z=22.
- **Verify (correct cx=45.5)**: bottom rrect torus 4/4/8/0 (O/I/B/N); side rrect
  bspline 24/24/32/16 (O/I/B/N). Both STEP + preview correct.
- **Lesson**: when testing holes on the curved (cosine) shell, hole center must
  be ON the wall, not at half-width/2. Verify rim by checking surface counts
  (torus for planar bottom, bspline for NURBS side), not by assuming wall at x=50.

## 2026-08-03 follow-up 4: MULTI-HOLE rrect crosstalk → all holes became BOTH-sides
- **Symptom**: Blender preview of a shell with 5 rrects (3 bottom O/I/B + 2 side)
  showed EVERY bottom rrect with BOTH-side rim fillet (single-hole tests were fine).
- **Root cause**: `apply_hole_fillets` collected rim edges with a WIDE radius band
  (`dist ∈ [effR*0.5, effR*1.6]`, effR=max(w,h)/1.2). With several holes on the
  same face, hole A's band captured hole B's rim edges too → each hole's outer/
  inner split picked up neighbors' rims → everything filleted both sides.
- **Fix**: rrect holes now use a TIGHT **contour-box membership** test instead of
  the radius band: edge belongs to hole i iff its curve-midpoint (dx,dy)/(dy,dz)/
  (dx,dz) lies within the rrect footprint (±w/2, ±h/2 + 0.7 tol) for that face,
  AND it's a true rim edge (endpoints move ALONG the contour; exclude through-wall
  edges whose deltas are ~0 in both in-plane axes). Round holes keep the wide band
  (single circular rim, no crosstalk).
- **ALSO FIXED**: preview `cut_holes_into_shape` rrect cutter used
  `create_rounded_box_solid(sx,sy,sz,rcr)` whose corner fillet is in the **XY**
  plane only → side-wall (fc=2/3, footprint in YZ) and front/back (fc=4/5, XZ)
  rrect holes came out as PLAIN RECTANGLES (corner radius on wrong plane). Replaced
  with shared `make_rrect_cutter_box(bx,by,bz,sx,sy,sz,rcr,edge_axis)` = plain box
  + fillet the 4 edges parallel to the through-wall axis (X/Y/Z), identical to the
  STEP export's construction. Also fixed fc=2/3 YZ mapping to Y=rw(宽),Z=rh(高) to
  match `_make_rrect_cutter` rotation + STEP export.
- **Verify (5-hole combo, 100x80x50 curved wall=2)**:
  - Preview bottom: x=0 OUTER 1848/88, x=-22 INNER 88/1936, x=+22 BOTH 1848/1936 ✓
  - Preview side:  y=0 OUTER 783/151, y=-18 BOTH 803/801 ✓
  - STEP export OK (2.3MB, B_SPLINE=120 TOROIDAL=16 CYLINDRICAL=40)
  - Round regression (3 round bottom O/I/B): 1008/0, 0/1008, 1008/1008 ✓
  - Side-wall INNER no longer fails ("no suitable edges")
- **UI**: removed the "RRect fillet forced Both-sides on curved side wall" override
  in `parametric_shell.py` draw() — side-wall rrect now shows outer/inner/both like
  bottom/top (OCCT limitation no longer applies).

## Code locations (module.cpp)
- File-scope `HoleFilletInfo` struct + `apply_hole_fillets` fwd decl: ~line 3304
- STEP export fillet call: `shape = apply_hole_fillets(resultSolid, ...)` ~line 3650
- Shared `apply_hole_fillets` def: ~line 3790 (now rrect-aware)
