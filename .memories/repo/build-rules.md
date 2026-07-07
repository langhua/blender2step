# Build Rules

- **NEVER run `cmake --build` or any compilation** — the user compiles manually
- **CAN modify C++ files** (`.cpp`, `.h`, `CMakeLists.txt`) — just don't compile
- CAN modify Python files (`.py`) freely
- Build method (from BUILD.md):
  ```
  cd blender2step\build
  cmake --build . --config Release
  ```
- Then copy: `Copy-Item build\Release\_step_exporter.pyd step_exporter\lib\ -Force`

# Curved Shell Construction
- BRIDGE approach: wall layers stop at z=-hh+bf, separate bottom face at z=-hh, connected via quads
- `_make_profile_layers()` builds cosine wall vertex layers
- `_connect_layers()` creates quads between layers
- Bottom fillet = quads bridging wall_bottom → bottom_face_vertices
- No g(s) math, no quarter-circle, no Hermite — just edge bridging
