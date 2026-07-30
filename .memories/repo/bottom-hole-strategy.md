# Bottom Face Hole Strategy (updated 2026-07-30)

## Core Principle
Bottom face holes on cosine-curved shells use Boolean modifier (NOT bmesh) because the bottom is a large N-gon that needs triangulation first.

## Key Steps (in order)
1. **Triangulate** all faces (`quads_convert_to_tris`) to break N-gon into triangles
2. **Dissolve coplanar** (`dissolve_limited`, angle=0.02 rad) to merge flat triangles and keep mesh simple
3. **Boolean DIFFERENCE** with FLOAT solver first, EXACT as fallback (F9 redo disabled, no duplicate holes)
4. After each hole, `remove_doubles(dist=0.00005)` for cleanup

## Ring approach (fillet) — 2026-07-30 updated
- Outer ring: Boolean modifier UNION, `zc = +fr`, positioned on outer face
- Inner ring: **same construction as outer** (`zc = +fr`), extra 180° X flip, positioned on inner face
- Ring recess: DIFFERENCE with rrect/cylinder cutter, depth `fr*2.5` (was `fr*1.5`)
- Precision: `n_rows=16`, `ARC_SEG=16`, cutter `seg=16`
- Z micro-offset: `-0.00002` (prevents face-edge ridge, matching round-hole torus)
- Solver: always FLOAT first, EXACT as internal fallback

## Execution path (2026-07-30)
- Bottom-face holes: **synchronous** (no modal timer, prevents cutter lifecycle crashes)
- Side-wall curved holes: still use 6-stage modal (unchanged)
- Rebuild (edit): uses ring functions directly, with mesh validation + gc.collect()

## Success rate
~95% (19/20) with this approach. Remaining failures are typically holes near bottom fillet edges or cumulative boolean corruption after many operations.
