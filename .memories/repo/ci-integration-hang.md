# CI integration test hang (fillet 5552-face mesh) — FIXED

## Root cause
`ci_integration_test.py` `_export_sync` used the incremental MESH path:
`_get_mesh_data_enhanced` + `add_object_to_export`. The fillet preview mesh
(2778 verts / 5552 tris) goes through `create_solid_from_mesh` →
`BRepBuilderAPI_Sewing.Perform()` which NEVER returns on high-poly meshes.
Real parametric export is analytic (BRepPrimAPI/BRepFilletAPI, NO mesh sewing).

## Key facts learned
- `init_incremental_export` redirects std::cout/cerr to `g_log_buf` and
  LOG_INCREMENTAL goes to `g_py_log_callback`. If the test passes
  `enable_logging=0` + `lambda msg: None`, ALL C++ export logs are swallowed —
  so "no output" after a [SYNC] marker does NOT mean hang is before C++.
- `context.evaluated_depsgraph_get()` CAN hang in `--background --python`
  (fixed earlier with `apply_modifiers=False`).
- `_analyze_cylinder_from_mesh` FIRST calls `_analyze_from_stored_params(obj, scale)`
  which reads `param_*` props (stored by addon at creation) — NO depsgraph, NO mesh
  analysis. Only plain meshes (no param_*) reach depsgraph/mesh detection.

## Fix
`_export_sync` now: `_analyze_cylinder_from_mesh` (stored params) →
`_export_cylinder_staged(cpp_exporter, filepath, cparams, data)` (analytic C++).
data dict needs keys: step_schema, step_unit, enable_logging, fix_geometry,
create_solid, advanced_brep (only for mesh-fallback branch).
`_export_cylinder_staged` handles ALL obj_types incl cylinder_stepped_hole,
cylinder_tapered_stepped_hole, grooved_cylinder (sync_export.py does NOT handle
cylinder_stepped_hole). Each test = 1 object → export straight to filepath, no merge.

## Test param mapping (operator → param_*)
- stepped_large_height (percent) → param_stepped_large_height_pct
- stepped_large_radius → param_stepped_large_radius
- stepped_small_radius → param_stepped_small_radius
