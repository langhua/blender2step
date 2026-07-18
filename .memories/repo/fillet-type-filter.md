# Hole Edge Fillet Type Filter

## Overview
When fillet_type is specified in window_data, edges are filtered based on their position:
- `ft=0` → outer edges only (same coordinate as hole center)
- `ft=1` → inner edges only (offset by ~thickness from hole center)
- `ft=2` → both outer and inner edges

## Implementation (module.cpp)
Two places apply the filter:

### 1. Cut-edge collection loop (~line 3490)
After proximity check (`dist < hf.r * 0.6`), checks edge position:
```cpp
isOuter = (fabs(edgeCoord - holeCoord) < hf.thick * 0.6);
isInner = !isOuter && (fabs(edgeCoord - holeCoord) < hf.thick * 1.5);
if (hf.type == 2 || (hf.type == 0 && isOuter) || (hf.type == 1 && isInner))
    edgesToFillet.push_back(edge);
```

### 2. Section supplement loop (~line 3540)
Same filter logic, with additional dedup check after filtering.

## Edge Classification
For each face code, edgeCoord is compared to holeCoord:
- fc=0/1 (Z faces): compare ecz vs hf.cz
- fc=2/3 (X faces): compare ecx vs hf.cx
- fc=4/5 (Y faces): compare ecy vs hf.cy

Outer edge = edge at same coordinate as hole center (hole is placed on outer face)
Inner edge = edge offset by ~thickness from hole center

## Known Limitation
Edges on NURBS/corner faces that pass proximity but are far from both outer and inner faces (isOuter=0, isInner=0) are excluded. These are corner artifacts, not genuine hole edges.
