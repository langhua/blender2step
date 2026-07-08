# Rim Terminology & Formulas

## Terms
- **Rim Top (Shelf)**: horizontal visible surface at top edge
- **Rim Inner Wall (Step Face)**: vertical surface below the shelf
- **Rim Top Width (rtw)**: the visible shelf width — UI label "Rim Top Width"
- **Rim Height (rh)**: vertical depth of the rim step
- **t**: shell wall thickness

## Ring Formulas (ring wall = 2*t for boolean stability)
Ring height = rh*2, position = total_h (top of shell, per Z=0 rule). Blender 4.2.1: FAST solver only.

**Inside Rim Top** (shelf visible from cavity):
```
ring_outer = w + 2*rtw
ring_inner = w - 2*t + 2*rtw    // inner wall + shelf (inward)
```

**Outside Rim Top** (shelf visible from outside):
```
ring_outer = w - 2*rtw
ring_inner = ring_outer - 2*t
```

Example (w=100, t=2, rtw=1.5):
- Inside: ring 99~103, shelf at 48~49.5 (inside) — rim width = 1.5mm
- Outside: ring 94~97, shelf at 48.5~50 (outside) — rim width = 1.5mm

## Minimum Clamp Values
Profile offsets use `max(value, EPS)` to avoid zero/negative dimensions.
**EPS must be much smaller than the smallest expected feature size (in Blender units = meters).**

| EPS | Value | In mm | Notes |
|-----|-------|-------|-------|
| Current | `0.0001` | 0.1mm | OK for mm-scale models |
| Future | `0.000001` | 0.001mm | For sub-mm precision |

**Affected locations:**
- `ob_off = max(t - rw, EPS)` — inside rim shelf offset
- `ib_cr = max(cr - rw, EPS)` — outside rim bottom corner radius
- `ob_cr = max(cr - t + rw, EPS)` — inside rim bottom corner radius