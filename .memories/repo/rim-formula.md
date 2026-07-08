# Rim Terminology & Formulas

## Terms
- **Rim Top (Shelf)**: horizontal visible surface at top edge
- **Rim Inner Wall (Step Face)**: vertical surface below the shelf
- **Rim Top Width (rtw)**: the visible shelf width — UI label "Rim Top Width"
- **Rim Height (rh)**: vertical depth of the rim step
- **t**: shell wall thickness

## Ring Formulas (ring wall = 2*t for boolean stability)
Ring height = rh*2, position = total_h/2 (outer local top). Blender 4.2.1: FAST solver only.

**Inside Rim Top** (shelf visible from cavity):
```
ring_inner = w - 2*(t - rtw)
ring_outer = w + 2*rtw
```

**Outside Rim Top** (shelf visible from outside):
```
ring_outer = w - 2*rtw
ring_inner = ring_outer - 2*t
```

Example (w=100, t=2, rtw=1):
- Inside: ring 98~102, shelf at 48~49 (inside)
- Outside: ring 94~98, shelf at 49~50 (outside)