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

## 2026-08-03 follow-up 5: ALL shell types (square/rounded/curved) unified on OCCT
- **Request**: user wants square & rounded shells (and round/rrect holes on them) to
  use OCCT like curved shells, instead of Blender Boolean (`_do_simple_stage0/1`).
- **Verified C++ already supports all types**: `create_parametric_shell_solid` handles
  square/rounded via box-based path (create_rounded_box_solid outer-inner cut + rim
  ring) and curved via loft path. `generate_parametric_shell_mesh` + `cut_holes_into_shape`
  + `apply_hole_fillets` all work for every corner_type.
- **UI changes in parametric_shell.py**:
  1. `_rebuild_stage_create` now sends ALL corner types to `_rebuild_stage_create_occt`
     (was curved-only; bpy.ops.create_parametric_shell fallback is now dead).
  2. `_rebuild_stage_create_occt` gained `corner_type` param (default 'curved'), passes
     it to `generate_parametric_shell_mesh` instead of hardcoding 'curved'.
  3. Add-hole `execute()` now always rebuilds via OCCT (removed `is_curved` branch +
     `_do_simple_stage0/1` calls + Blender cutter object creation — the cutter mesh
     was only needed for Boolean, OCCT only needs the window_data entry string).
  4. Remove-hole & edit-hole operators made SYNCHRONOUS (no modal loop) since OCCT
     rebuild bakes all holes in (`_holes_builtin`).
- **Verification (100x80x50 wall=2, all 3 types)**: bottom round O/I/B = 1008/0,0/1008,
  1008/1008; bottom rrect O/I/B = 1851/88,88/1851,1851/1851; side round BOTH midwall
  fillet verts ~1848 (vs none=84); STEP export torus counts correct (round=4, rrect=16,
  side=2). All ✓.
- **IMPORTANT geometry lesson**: side-wall fillet does NOT bulge beyond the outer wall
  face. On a planar wall the outer rim fillet torus sits INSIDE wall thickness
  (center x = wall_x - fr, surface spans [wall_x-2fr, wall_x]); inner fillet spans
  [wall_x-thick, wall_x-thick+2fr]. So detecting side fillet via verts outside the wall
  face (x>wall_x or x<wall_x-thick) FAILS — must compare mid-wall vertex density
  (BOTH has ~1800 mid-wall verts, NONE only ~84).

## 2026-08-03 follow-up 6: DEAD CODE REMOVED from parametric_shell.py
- Removed ~2229 lines (3566→1337) of unreachable Blender-Boolean hole code from
  `step_exporter/ui/parametric_shell.py` after OCCT unification. Backup at
  `parametric_shell.py.bak` (keep until user confirms in real Blender UI).
- Deleted: `_fillet_stage_0..5/_bevel`, `_apply_fillet_torus_union`, `_direct_cut_hole`,
  `_bmesh_cut_round_tunnel/_circle`, `_cleanup_after_bool/_mesh`, `_delete_small_fragments`,
  `_do_simple_stage0/1`, `_add_rrect_step_ring`, `_force_redraw`,
  `_apply_bottom_rrect_recess/_ring`, `_apply_bottom_outer/inner_ring`, `_fillet_hole_edge`,
  `_fillet_rrect_edge`, `_keep_or_remove`, `_make_ring_shared`, `_tilt_scale`,
  `_rebuild_stage_hole`, `_rebuild_shell_mesh`; dead methods `_make_rrect_cutter`,
  `_make_solid_box`, `_apply_bool`, `_build_boolean_shell`, `_make_curved_solid`,
  `_build_square`, `_build_rounded`; dead `modal()`/`_cleanup_modal()`/`_rb_cleanup()` on
  add/remove/edit operators. All had ZERO live callers (verified by subagent: no execute()
  returns RUNNING_MODAL; modal attrs never assigned; no cross-module imports).
- **Verification**: AST parse OK; Blender 5.2 background E2E — square shell created,
  3 round holes added one-by-one (OCCT rebuild v=1948→3880→7576), remove hole works,
  STEP export OK (torus=4). All pass. Also confirmed round+rrect combo OK via direct C++.
- Lesson: when invoking add_hole_to_shell via bpy.ops directly (no invoke), hole_pos_x/y/z
  default to 0 → all holes overlap at origin → OCCT fillet fails ("no suitable edges").
  Always pass explicit hole_pos_x/y/z in tests.

## 2026-08-03 follow-up 7: CURVED SHELL BOTTOM FILLET — SMOOTH TRANSITION FIX
- **Symptom**: on cosine (curved) shells with bottom fillet, the wall→fillet transition
  was smooth but fillet→bottom-face transition showed a visible crease in Blender.
- **Root cause** (src/export/module.cpp `create_parametric_shell_solid` curved path):
  the bottom fillet zone used LINEAR z (`z=-hh+bf*i/bfSegs`) with `offset=bf*(1-sin(π/2*s))`.
  This is NOT a true circular fillet: at the bottom (s=0) dz/ds=bf≠0 but doffset/ds=-bf·π/2≠0,
  so the surface cuts into the bottom face at ~57°, breaking G1 continuity → crease.
- **Fix**: parameterize the fillet as a TRUE quarter-circle:
  - `θ = π/2 · s`, `z = -hh + z_shift + bf·(1-cosθ)`  → dz/dθ=0 at bottom ⇒ tangent VERTICAL
  - `offset = bf·(1-sinθ)` (radial inset, bf at bottom → 0 at wall)
  - Also raised `bfSegs` 8→16 (fillet loft resolution).
- **Verify**: OCCT normal analysis shows smooth tilt 11°→72° across fillet (no jump);
  mesh density in z[0,0.5]mm near bottom rose from ~3 z-layers (old) to 92 (bfSegs=16);
  E2E in Blender: create curved+bf=2 (9359 verts), add round hole (13442), STEP export OK.
- **bfSegs note**: 32 gives more bottom z-layers (197) but LOWER total verts (6462 vs 9599);
  16 is the better balance (max total verts + 92 bottom layers).

## 2026-08-03 follow-up 8: STEP EXPORT VERIFIED = SAME SMOOTH FILLET (test30.step)
- **Question**: is the exported .step as smooth as the Blender preview? → YES, provably.
- **Architecture proof**: `export_parametric_shell_step` AND `generate_parametric_shell_mesh`
  (preview) both call the SAME `create_parametric_shell_solid`; preview is just a
  BRepMesh tessellation of it, STEP is the exact B-rep write. Identical geometry.
- **Read-back verification** (temporary `read_step_mesh` diag fn added to module.cpp,
  then removed after use): STEPControl_Reader reads test30.step back → BRepMesh 0.05 →
  triangle normal tilt vs z (tilt = atan2(|nz|, horizontal)):
  - seam z=0: tilt ≈ 83° (near-tangent to horizontal bottom plane; old broken code ≈33°)
  - smooth monotonic 83°→62°→44°→33°→22°→13°→10° over z 0→0.45mm (bf≈0.5 in test30)
  - no jumps anywhere ⇒ G1; z=1.2 flat face = inner bottom floor (bottom_thickness=1.2)
- **Practical tip**: to read a STEP back through OCCT, add a temporary
  `STEPControl_Reader` + `BRepMesh_IncrementalMesh` + dedup function; load pyd standalone
  with `step_exporter\lib` in PATH (DLLs live there; system Python313 works, no Blender).

## 2026-08-03 follow-up 9: INDEPENDENT COSINE RATIOS (curve_ratio_x / curve_ratio_y)
- **Feature**: left/right (x) walls and front/back (y) walls can now use DIFFERENT
  cosine ratios. New UI prop `curve_ratio_y`; `curve_ratio` stays = x (left/right).
- **C++ geometry** (module.cpp `create_parametric_shell_solid` curved path):
  - `total_inset_x = min(hw,hd)*curve_ratio*0.5`
  - `total_inset_y = min(hw,hd)*curve_ratio_y*0.5`
  - layers: `hw -= cos_inset_x`, `hd -= cos_inset_y*aspect` (aspect=hd/hw kept so
    EQUAL ratios ⇒ identical uniform proportional shrink as before).
- **API placement (IMPORTANT)**: `curve_ratio_y` was added at the END of both
  positional arg lists (`generate_parametric_shell_mesh`: after cosine_layers;
  `export_parametric_shell_step`: after rot_z), with sentinel default `-1.0` →
  resolved to curve_ratio. This keeps OLD positional callers working unchanged.
  (First attempt put it in the middle → broke old callers → reverted to end.)
- **Verify**: standalone pyd — equal 50/50 → x shrink 0.806 / y 0.805 (uniform);
  old signature == equal-ratio exactly; x=0,y=50 → x flat/bot=50, y 40→32; STEP
  export OK. Blender E2E: curve_ratio=0, curve_ratio_y=100 → x flat 0.05/0.05,
  y 0.04→0.02 (curved), `curve_ratio_y` stored on object.

## 2026-08-03 follow-up 10: CURVED SHELL RIM HEIGHT FIX + SMALL-FILLET DEGENERACY
- **Symptom**: curved (cosine) shell with rim — outer edge height wrong (set 1mm,
  looked ~0.5mm). Root causes found (2 independent bugs):
- **Bug A — rim placement** (module.cpp curved path): ring was translated to
  `height - rim_height/2` with oBox height `rh+2` → no raised edge above shell top
  (max z = height). Box/rounded path translates to `height + rh/2` with oBox `rh`
  → raised rim. FIX: curved now (1) `total_h = height + rim_height` when rim present
  (was always `height` for curved), (2) ring at `tapered ? height : height + rh/2`,
  (3) oBox/iBox heights `rh`/`rh+2` (was rh+2/rh+4). Verified: rh=1→raise 1.00,
  rh=2→2.00, rh=0.5→0.50 (matches rounded).
- **Bug B — small bottom-fillet degeneracy**: bf in ~0.05–0.5mm made the curved loft
  degenerate → 100k–535k vertex meshes or hangs. Cause: bfSegs=16 packed 17 near-
  coincident loft wires into a tiny z-range. FIX: `bfSegs = max(2, min(16, round(bf*10)))`
  (wire spacing ≈0.1mm). Verified: bf=0.5→6425 verts (was 142k), bf=0.8→10k, bf≥1→clean.
  bf=0.1–0.2 still dense (~35–77k) but functional (not broken).
- **Bug B trigger**: `_clamp_cr_bf` in parametric_shell.py forced `bottom_fillet=0.1`
  for curved+rim → always hit the degenerate path. FIX: clamp now only enforces
  `corner_radius >= 2.7` (bf left as user set, incl. 0). Verified bf=0+rim works.
- **Blender E2E**: curved+rim rh=1 → 5028 verts (clean), bf stays 0, rim raises 1mm,
  STEP export OK (336KB).

## 2026-08-03 follow-up 11: RIM VERTICALITY VERIFIED (B-rep analysis)
- **Question**: are the rim edges vertical (shells mate in pairs via inner/outer edge
  interlock)? Verified with a temporary B-rep face analyzer (BRepAdaptor_Surface +
  BRepBndLib, sampled normal at face center AND at top edge; removed after use).
- **Results (curved & rounded, outside+inside rim)**:
  - Rim STEP faces (the interlock/mating faces): **planes & cylinders, tilt = 0.0°
    (perfectly vertical)** for BOTH curved and rounded. ✓
  - Rim TOP face: plane, 90° (horizontal). ✓
  - Wall surfaces at rim top (z≈51): rounded = 0.0° (perfect); curved outer wall =
    0.5-0.7° off vertical, curved inner wall = 1.7-2.7° off (small residual draft
    from the cosine loft B-spline boundary). Acceptable for snap-fit, not perfectly 0.
- **DECISION (user, 2026-08-03)**: keep the small curved-wall draft as-is — it's
  beneficial for mold release (脱模). No need to force 0° verticality.
- **Lesson**: preview-mesh vertex/triangle analysis is UNRELIABLE for 1mm-thin rim
  features (528-vert coarse box mesh, no vertices/triangles land in thin strips).
  Must use B-rep face analysis (BRepAdaptor_Surface normals) for such checks.
- **Temp diag**: `analyze_shell_faces(...)` returned (type,zmin,zmax,pt,normal_center,
  normal_top,tilt_center,tilt_top) per face; removed after verification.

## 2026-08-03 follow-up 12: CYLINDER BLIND-HOLE DEPTH % FIX
- **Symptom**: parametric cylinder bottom/top/both blind hole — set 50% depth, hole
  looked ~72% deep.
- **Root cause** (step_exporter/ui/parametric_cylinder.py `_create_holes`): the
  cutter's `ext_bottom = max(hr_end*2.0, H*0.05)` (~1.8mm for typical holes) was
  ADDED to the cutter's z_top (bottom hole) / subtracted from z_bottom (top hole),
  making the blind hole `ext_bottom` too deep (e.g. 50% → 71.6%).
- **Fix**: `ext_bottom = max(hr_end*0.005, H*0.0005)` (tiny boolean margin only).
  Verified in Blender: 50% → hole flat bottom at 50.1% (was 71.6%). C++ export
  (`export_cylinder_blind_hole_step`) was already correct (cuts to exactly hole_depth)
  — so preview now matches STEP.
- **Related (FIXED)**: stepped/tapered_stepped holes used `ext_ov = H*0.05` extending the
  LARGE cutter BELOW step_z → large section ~5% too deep (e.g. 80% → 85%). Fixed:
  large/tapered cutter now ends EXACTLY at step_z; the small cutter still overlaps
  above step_z (hidden inside the wider large radius) so the union stays watertight.
  Verified in Blender: stepped 80% → step at 80.0%; tapered_stepped 80% → step at
  z=-12.0 exactly (radius 8 above, 5 below).

## Code locations (module.cpp)
- File-scope `HoleFilletInfo` struct + `apply_hole_fillets` fwd decl: ~line 3304
- STEP export fillet call: `shape = apply_hole_fillets(resultSolid, ...)` ~line 3650
- Shared `apply_hole_fillets` def: ~line 3790 (now rrect-aware)
