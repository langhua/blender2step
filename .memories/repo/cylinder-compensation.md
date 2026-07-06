# Cylinder Radius Compensation Design

## Architecture Decision (2026-06-29)
**C++ must NOT compensate cylinder radii.** Python pre-compensates via `cylinder_original_radius`.

### How it works:
1. Blender stores `cylinder_original_radius` (pre-bevel radius in mm) as custom property
2. Python analysis (`cylinder.py`) reads `stored_orig_r` and sets `body_radius_for_export = stored_orig_r * 0.001`
3. C++ uses the provided radius AS-IS for cylinders (`if (!is_cyl) { ... }` — only compensates cones)

### Key files:
- `src/cylinder/cylinder_parametric.cpp` — 11 compensation blocks, all use `if (!is_cyl)` pattern
- `step_exporter/analysis/cylinder.py` — lines ~1640, ~1700: `body_radius_for_export = stored_orig_r * 0.001`
- `step_exporter/ui/parametric_cylinder.py` — line ~379: stores `cylinder_original_radius`

### Why no C++ compensation:
Python passes the pre-bevel radius AND chamfer/fillet sizes separately. C++ applies chamfer/fillet geometry using those sizes but must NOT add them to the radius. Double compensation caused GC6_Thru (r=460 instead of 400), GC6_TprThru, GC6_InvTprThru to have oversized diameters.
