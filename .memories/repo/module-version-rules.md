# Module Version Numbering Rules

`src/export/module.cpp` — `MODULE_VERSION` constant.

## When to bump:
- **Major (X.0.0)**: New export format, breaking API changes
- **Minor (4.X.0)**: New C++ function added, significant new feature
- **Patch (4.1.X)**: Bug fixes, small improvements

## Format:
```cpp
const char* MODULE_VERSION = "4.2.0";  // +short description of change
```

## Files to update:
- `src/export/module.cpp` — the `MODULE_VERSION` constant

Version is reported in logs as `[OK] C++ loaded v=X.Y.Z`.
