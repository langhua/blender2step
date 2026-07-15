# Bottom Face Hole Strategy

## Core Principle
Bottom face holes on cosine-curved shells use Boolean modifier (NOT bmesh) because the bottom is a large N-gon that needs triangulation first.

## Key Steps (in order)
1. **Triangulate** all faces (`quads_convert_to_tris`) to break N-gon into triangles
2. **Dissolve coplanar** (`dissolve_limited`, angle=0.02 rad) to merge flat triangles and keep mesh simple
3. **Boolean DIFFERENCE** with FAST solver first, EXACT as fallback
4. After each hole, `remove_doubles(dist=0.00005)` for cleanup

## Why dissolve_limited is critical
Without it, each Boolean operation adds more triangles to the bottom face. Over many holes, the mesh becomes too complex for subsequent Boolean operations. Dissolving coplanar faces after each hole keeps complexity manageable.

## Ring approach (fillet)
- Outer ring: Boolean modifier UNION, positioned on outer surface
- Inner ring: Boolean modifier UNION, positioned on inner surface  
- Ring recess: DIFFERENCE with cylinder slightly larger than ring

## Success rate
~95% (19/20) with this approach. Remaining failures are typically holes near bottom fillet edges.
