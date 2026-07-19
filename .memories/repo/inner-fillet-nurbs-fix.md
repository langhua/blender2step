# Inner Fillet on NURBS Side Walls — KNOWN LIMITATION (2026-07-19)

## OCCT 7.8.1 硬限制

`BRepFilletAPI_MakeFillet` 不支持 NURBS/B-spline 曲面上的内侧圆角方向控制。

| fillet_type | NURBS (curved) | Planar (square/rounded) |
|-------------|----------------|------------------------|
| 0 (outer)   | ✅ 可用 | ✅ TOROIDAL_SURFACE |
| 1 (inner)   | ⚠️ 不可靠 | ✅ TOROIDAL_SURFACE |
| 2 (both)    | ✅ 可用 | ✅ TOROIDAL_SURFACE |

## Bug Fixes Applied
1. **Cross-assignment fix**: `ecx > pos` instead of `ecx > pos + r*0.5`
2. **Wall-midpoint classification**: `isInner = (coord > pos + thickness*0.5)`
3. **Per-hole fillet radius**: `hf.fr` instead of `holeFillets[0].fr`
4. **Best-edge-per-hole**: closest to ideal face position

## Key: corner_type string
- `'curved'` = cosine loft NURBS (what Blender uses)
- `'rounded'` = filleted corners (analytic)
- `'square'` = sharp corners (planar)
- `'curve'` = WRONG — treated as square!
