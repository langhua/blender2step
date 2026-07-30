# Hole Edge Fillet Type Filter (updated 2026-07-30)

## Blender Side (UI + Geometry)
- Bottom face (face 0): all three types (0=outer, 1=inner, 2=both) supported for both round and rrect holes
- NURBS side walls (face 2-5): inner-only (type 1) unsupported due to OCCT limitation
- F9 redo panel disabled (`REGISTER` removed) to prevent accidental duplicate holes
- Edit dialog uses ring functions directly for curved shell rrect holes

## Implementation (module.cpp)

### 1. Edge collection (~line 3470)
Iterates ALL edges of resultSolid (not just non-Planar-adjacent). For each edge:
- **Proximity check**: distance to hole center in face plane + orthogonal side check (prevents cross-face matching)
- **Outer/Inner classification**: compares edgeCoord to KNOWN shell face positions, NOT hole center:
  - fc=0: outerC=pos_z, innerC=pos_z+thickness
  - fc=1: outerC=pos_z+height, innerC=pos_z+height-thickness
  - fc=2: outerC=pos_x-halfW, innerC=pos_x-halfW+thickness
  - fc=3: outerC=pos_x+halfW, innerC=pos_x+halfW-thickness
  - fc=4: outerC=pos_y-halfD, innerC=pos_y-halfD+thickness
  - fc=5: outerC=pos_y+halfD, innerC=pos_y+halfD-thickness
- isOuter = (fabs(edgeCoord - outerC) < thickness * 0.6)
- isInner = (fabs(edgeCoord - innerC) < thickness * 0.6)

### 2. Section supplement (~line 3540)
Same filter with wider proximity threshold (r*1.2 vs r*0.6).

### 3. Synthetic outer edge creation (~line 3690)
For ft=0/2 holes where no outer edge exists in resultSolid:
- Creates a gp_Circ at the outer face position, matching hole center + radius
- Uses BRepBuilderAPI_MakeEdge(circ) to create synthetic edge
- Adds to edgesToFillet; OCCT accepts it for fillet computation

## Why synthetic edges are needed
Boolean cut (BRepAlgoAPI_Cut with cylinder) does NOT produce edges at outer faces of curved-corner side walls. Bottom face (flat) edges ARE produced. Synthetic edges fill this gap.

## Orthogonal proximity check
Prevents right-face edges from matching left-face holes (and vice versa):
- fc=0: skip if ecz > pos_z + thickness + r*0.5
- fc=1: skip if ecz < pos_z + height - thickness - r*0.5
- fc=2: skip if ecx > pos_x + r*0.5
- fc=3: skip if ecx < pos_x - r*0.5
- fc=4: skip if ecy > pos_y + r*0.5
- fc=5: skip if ecy < pos_y - r*0.5
