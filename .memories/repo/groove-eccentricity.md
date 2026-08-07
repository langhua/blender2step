# Groove Eccentricity (vertical offset)

Feature: `groove_eccentric` (% of height, -45..+45, 0=mid) moves the external groove up/down on cylinders & cones.

## Param flow
- UI: `groove_eccentric` FloatProperty (PERCENTAGE) in groove box → stored as `param_groove_eccentric`; loaded via `_load_params_from_object`.
- bmesh `_create_groove`: cutter Z += `height_m * ecc_pct/100`; stores `step_groove_offset` (mm) = `height * ecc/100`.
- Analysis `_groove_params` (cylinder.py): returns `groove_offset` = `H*ecc/100`.
  **CRITICAL**: MUST always compute from `param_groove_*` — do NOT use the `step_groove_*` fast path. `step_groove_*` are stored by `_create_groove` at creation time and go STALE when the user edits the object (`update_selected` only refreshes `param_groove_*`). Using stale `step_groove_*` caused: (a) wrong groove POSITION after editing eccentric (stale `step_groove_offset`), (b) wrong groove SIZE (bmesh `+0.0001` m margin adds 0.2mm to bottom width). The OCCT preview uses `param_groove_*` (build_cylinder_like_shape), so export MUST use the same computed path to match preview.
- staged_export.py: passes `cparams.get('groove_offset',0)` as LAST arg to all 11 groove export calls.
- C++ export wrappers (module.cpp): `groove_offset` appended as extra `d` (after groove_extrusion_length, before pos for required-groove funcs). ALL PyArg_ParseTuple format strings must exactly match pointer count/type — verify with alignment checker (see below).

## C++ create functions (cylinder_parametric.cpp)
- `apply_trapezoidal_groove`: +`double groove_offset`, shifts all 4 polygon Z coords.
- Cylinder fns (no radius change): blind_hole, dual_blind_holes, stepped_hole, tapered_stepped_hole, with_groove → pass groove_offset through.
- Cone fns: local radius adaptation `mid_r = bot_r + (top_r-bot_r)*(offset + h/2)/h` (cone centered at origin, bottom z=-h/2). Applies to: cone_with_groove, cone_with_blind_hole_and_groove, cone_stepped_hole_with_groove, hollow_cone_fillet_with_groove.
- Header decls (step_exporter_internal.h): `double groove_offset = 0.0` default.
- Preview: `build_cylinder_like_shape` +`groove_eccentric` param, computes `groove_offset = H*ecc/100`, passes to create fns. `generate_cylinder_mesh` format has `...idddddd` (groove_eccentric + deflection as last 2 d's).

## Verification
- Cylinder ecc=+20 (h=100): STEP floor z moves 0→+20 (FreeCAD face z∈[19,21]). Cone ecc=+20: floor z∈[19,21] too.
- Integration test in Blender: stored/analysis/export all show offset=8mm for h=40, ecc=20.
- NOTE: `shape_to_mesh_dict` caps triangulate rim-only (no interior verts, all at r=R) — mesh still CLOSED & volumetrically correct. Don't use "min radius per z" to locate groove in mesh for cones (picks top rim).
