# Y-Axis Mirror Fix for Parametric Shell Export

## Problem
STEP export of parametric shells had holes appearing in "opposite" (mirrored) positions compared to Blender viewport.

## Root Cause
Blender uses Z-up / Y-forward coordinate convention, while STEP viewers often interpret Y-axis differently, causing mirrored hole positions.

## Fix (2026-07-25)
In `step_exporter/analysis/parametric_shell.py`:

1. **Line 72** — Negate `pos_y` in return dict:
   ```python
   'pos_y': -obj.location.y * scale,  # was: obj.location.y * scale
   ```

2. **Line 114** — Negate Y in window_data world conversion:
   ```python
   cy_w = -(cy + pos_y)  # was: cy + pos_y
   ```

Both shell position AND hole coordinates must be negated together to preserve relative positioning while mirroring across Y-axis.
