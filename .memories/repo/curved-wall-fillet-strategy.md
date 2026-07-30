# Curved Side Wall Fillet Strategy (余弦曲面侧壁圆角) — updated 2026-07-30

## Overview
For cosine-curved shells (`corner_type == 'curved'`):
- **Side walls (face 2-5)**: use 6-stage modal with torus boolean union (unchanged)
- **Bottom face (face 0)**: use **synchronous** ring approach (2026-07-30 — no modal timer, prevents cutter lifecycle crashes)
- rrect holes on curved bottom: use `_apply_bottom_rrect_recess` + `_apply_bottom_rrect_ring` (same as round)

## Modal Stages (6-stage)

| Stage | Function | Operation | Solver |
|-------|----------|-----------|--------|
| 0 | `_fillet_stage_0` | Compute surface positions analytically | N/A |
| 1 | `_fillet_stage_1` | Through-hole cut (cylinder DIFFERENCE) | EXACT→FAST |
| 2 | `_fillet_stage_2` | Outer recess cut (cylinder DIFFERENCE) | EXACT |
| 3 | `_fillet_stage_3` | Outer ring UNION | `_safe_bool_union` (FAST) |
| 4 | `_fillet_stage_4` | Inner recess cut (cylinder DIFFERENCE) | EXACT |
| 5 | `_fillet_stage_5` | Inner ring UNION | `_safe_bool_union` (FAST) |

## Surface Position Computation (`_fillet_stage_0`)

Uses analytical cosine formula (NOT vertex sampling):
```
_inset(z_local) = total_inset_m * (1 - cos(π/2 * tf))
where tf = (hh - z_local) / (2 * hh), clipped to [0,1]
```

For face 4 (front): `sur_y = -(hd_m - inset * (hd_m / hw_m))`
For face 5 (back):  `sur_y = +(hd_m - inset * (hd_m / hw_m))`
For face 2 (left):  `sur_x = -(hw_m - inset)`
For face 3 (right): `sur_x = +(hw_m - inset)`

**Key outputs**: `outer_pos`, `inner_pos`, `euler_rot`, `euler_inner`, `world_thick`, `ox/oy/oz`

### Ring Rotation (`euler_rot`)
- Face 4: `(atan2(1, dinset_dz), 0, 0)` — ring local Z → world -Y (into front face)
- Face 5: `(atan2(-1, dinset_dz), 0, 0)` — ring local Z → world +Y (into back face)
- Face 2: `(0, atan2(1, dinset_dz), 0)` — ring local Z → world +X (into left face)
- Face 3: `(0, atan2(-1, dinset_dz), 0)` — ring local Z → world -X (into right face)

### Inner Ring Position
```python
inner_pos = (outer_pos[0] - ox, outer_pos[1] - oy, outer_pos[2] - oz)
```
This offsets from the outer surface inward by wall thickness. The old code `inner_pos = (px, py, pz)` was WRONG — it put the inner ring on the outer surface.

### Inner Ring Rotation
```python
# Faces 4,5,0,1: flip X rotation (add π)
euler_inner = (euler_rot[0] + π, euler_rot[1], euler_rot[2])
# Faces 2,3: flip Y rotation (add π)
euler_inner = (euler_rot[0], euler_rot[1] + π, euler_rot[2])
```

## Ring Geometry (`_make_ring_shared`)

Quarter-torus (90° arc from surface into hole):
- Inner radius: `hr - fr*0.02` (slightly inside hole for overlap)
- Outer radius: `hr + fr*2.02` (slightly oversized)
- Formula: `rc = (hr + fr) + fr * 1.02 * cos(ph)` where ph ∈ [π/2, π]
- Z extent: `zc = -fr + fr * sin(ph) - 0.00002` (local Z, 0 at surface to -fr at bottom)
- Segments: 24 angular × 6 profile

## Recess Cut Sizing
- Stage 2 recess radius: `max(hr, hole_r - fr * 0.05)`
- Stage 4 inner recess: same formula
- This makes the recess ~5% smaller than the ring's outer extent

## Ring Union (`_safe_bool_union`)
Simple Boolean modifier with FAST solver, no backup, no EXACT fallback:
```python
mod = obj.modifiers.new(name=name, type='BOOLEAN')
mod.object = ring_obj; mod.operation = 'UNION'; mod.solver = 'FAST'
bpy.ops.object.modifier_apply(modifier=name)
```
Returns vertex count delta. No mesh swapping, no restore logic.

## Known Issues & Stability

| Wall | Stability | Notes |
|------|-----------|-------|
| Back (face 5) | ✅ Stable | Original approach works well |
| Front (face 4) | ✅ Good | Left→right order recommended |
| Left (face 2) | ⚠️ Untested | atan2 sign fixed |
| Right (face 3) | ⚠️ Untested | atan2 sign fixed |

### Important: hole creation order
When creating adjacent holes on the same face, create left-to-right. Creating right-first then left can corrupt the right hole's ring due to Blender boolean solver asymmetry.

### Failed approaches
- **Bevel (`_fillet_hole_edge`)**: Edge detection uses flat-wall positions (`-hd`), misses edges on curved surfaces. Causes mesh corruption.
- **EXACT-first boolean**: Can reduce vertex count from 25000+ to <500 (mesh destroyed).
- **`intersect_boolean` in edit mode**: Produces "未发现交集" warnings, no visible result.

## Code Locations
- `step_exporter/ui/parametric_shell.py`
- Modal: `STEP_EXPORTER_OT_create_parametric_shell.modal()` (fillet mode, ~line 1490)
- `_fillet_stage_0`: line ~1556 — surface computation
- `_fillet_stage_1`: line ~1700 — through-hole
- `_fillet_stage_2`: line ~1745 — outer recess
- `_fillet_stage_3`: line ~1776 — outer ring union
- `_fillet_stage_4`: line ~1815 — inner recess
- `_fillet_stage_5`: line ~1845 — inner ring union
- `_make_ring_shared`: line ~1674 — ring mesh creation
- `_safe_bool_union`: line ~1668 — safe boolean with backup
