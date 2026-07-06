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
