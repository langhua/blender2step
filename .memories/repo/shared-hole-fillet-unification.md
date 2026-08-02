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
- Note: fc=0 bottom-face round fillet via OCCT preview doesn't change vert count
  (pre-existing; separate from this fix).

## Code locations (module.cpp)
- File-scope `HoleFilletInfo` struct + `apply_hole_fillets` fwd decl: ~line 3304
- STEP export fillet call: `shape = apply_hole_fillets(resultSolid, ...)` ~line 3650
- Shared `apply_hole_fillets` def: ~line 3790 (now rrect-aware)
