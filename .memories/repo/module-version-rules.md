# Module Version Numbering Rules

`src/export/module.cpp` — `MODULE_VERSION` constant.

## When to bump:
- **Major (X.0.0)**: New export format, breaking API changes
- **Minor (4.X.0)**: New C++ function added, significant new feature
- **Patch (4.1.X)**: Bug fixes, small improvements

## Format:
```cpp
const char* MODULE_VERSION = "5.0.0";  // +short description of change
```

## 5.0.0 note (2026-08-07)
- Version jumped 4.2.3 → 5.0.0 (major, breaking support).
- pyd is compiled for **CPython 3.13** (Blender 5.0+ only; `bl_info "blender": (5,0,0)`).
  Blender 4.x ships Python 3.11 → ABI-incompatible, cannot load. Docs updated to
  "Blender 5.0+ (Python 3.13)". Release zip = `blender2step-<version>.zip`.

## Files to update:
- `src/export/module.cpp` — the `MODULE_VERSION` constant

Version is reported in logs as `[OK] C++ loaded v=X.Y.Z`.
