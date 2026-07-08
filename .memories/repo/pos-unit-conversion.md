# Position Unit Conversion Rule

## The Rule
**`obj.location` (Blender) is ALWAYS in meters. Parametric dimensions are converted to target units via `scale`. POS values MUST also be multiplied by `scale`.**

```python
'pos_x': obj.location.x * scale,  # NOT obj.location.x
'pos_y': obj.location.y * scale,
'pos_z': obj.location.z * scale,
```

## Why
- Blender internal unit = meters (always)
- `obj.location.x/y/z` returns meters regardless of scene unit display
- Parametric dimensions (width, depth, height, radius, thickness) are multiplied by `scale` (1000 for mm, 1 for m)
- Without scaling pos, 1m offset becomes 1mm → shells/cylinders overlap

## Where to check
- `step_exporter/analysis/parametric_shell.py` ✅ fixed
- `step_exporter/analysis/bottom_shell.py` ⚠️ line 46 fixed, line 483 already correct
- `step_exporter/analysis/cylinder.py` ⚠️ mixed: some use `* S`, some miss it
- `step_exporter/analysis/top_shell.py` ✅ already uses `* S`
