# Build Rules

- **Build command** (from BUILD.md):
  ```
  cd blender2step\build
  cmake --build . --config Release
  ```
- `.pyd` auto-copies to `step_exporter/lib/` on build
- Python files (`.py`) take effect immediately (via NTFS junction to Blender addons)
- Clear `__pycache__` after Python changes to avoid stale bytecode:
  ```
  Remove-Item -Path "step_exporter\__pycache__" -Recurse -Force
  Remove-Item -Path "step_exporter\ui\__pycache__" -Recurse -Force
  ```

# Curved Shell Construction
- BRIDGE approach: wall layers stop at z=-hh+bf, separate bottom face at z=-hh, connected via quads
- `_make_profile_layers()` builds cosine wall vertex layers
- `_connect_layers()` creates quads between layers
- Bottom fillet = quads bridging wall_bottom → bottom_face_vertices
- No g(s) math, no quarter-circle, no Hermite — just edge bridging
