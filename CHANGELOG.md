# Changelog

All notable changes to the **blender2step** addon are documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versioning mirrors the C++ module version (`src/export/module.cpp` `MODULE_VERSION`),
which is also what the addon UI reports (see `step_exporter/__init__.py` `bl_info`).

---

## [5.0.0] — 2026-08-07

### Changed
- **Version bumped to 5.0.0**, aligned across `bl_info` and the C++ `MODULE_VERSION`.
- **Requires Blender 5.0 or newer (Python 3.13).** The compiled `_step_exporter.pyd`
  is a CPython 3.13 extension and cannot load in the Python 3.11 interpreter that
  Blender 4.x ships (CPython extension ABI is bound to the Python minor version).
  `bl_info` `"blender"` minimum is now `(5, 0, 0)`, so Blender 4.x shows the addon
  as incompatible instead of loading it broken.
- Release zip renamed to `blender2step-<version>.zip`.

---

## [4.2.3] — 2026-08-07

### Added
- **Groove eccentricity** (`偏心 %` / *Eccentric %*): move the external trapezoidal
  groove up/down on cylinders and cones as a percentage of height (−45% … +45%).
  - New UI property `groove_eccentric` (stored as `param_groove_eccentric`).
  - C++ `create_*_parametric` functions accept a `groove_offset` (mm); cone functions
    adapt the local radius at the offset so the groove stays flush with the slanted wall.
  - OCCT preview (`generate_cylinder_mesh`) matches the STEP export exactly.
- **Edit features for parametric parts**:
  - "Write to Selected" / 写入选中对象 for **cylinder / cone / inverted-cone**.
  - Same edit capability for the **parametric shell** (Generate / Edit Shell).
  - "Write to Selected" checkbox moved to the bottom of both dialogs.
- **Fully parametric cylinder export**: cylinders/cones are exported from stored
  creation parameters (`param_*`), no longer relying on fragile mesh re-detection.
- **OCCT-generated preview mesh** for cylinders, cones and inverted-cones (replaces
  the bmesh preview so the Blender view matches the STEP output).

### Fixed
- Grooved cone (凹槽锥柱) STEP export produced wrong groove size/position.
  Root cause: the export analysis preferred stale `step_groove_*` values left by the
  bmesh cutter at creation time. After editing, these were outdated (e.g. old
  `step_groove_offset`), while the preview used the up-to-date `param_groove_*`.
  The analysis now always computes groove parameters from `param_groove_*`, so
  **preview == export** and edits take effect immediately.
- Removed a 0.2 mm groove-width discrepancy caused by the bmesh boolean margin
  leaking into the exported `groove_bottom_width`.
- Removed leftover debug prints (`[DBG]`, `[DEBUG Phase3/4]`) from the export path
  and sample operators.
- Cone top residual / inverted-cone (上粗下细) radius compensation: only chamfers
  compensate the outer radius (fillets keep the design radius).
- Stepped-hole bottom sharpness and 大孔半径 vs 锥形顶半径 semantics clarified in the UI.

### Changed
- Version aligned across `bl_info` and the C++ module (`4.2.3`).
- `step_exporter/lib/` ships the compiled `_step_exporter.pyd` and all OpenCASCADE
  runtime DLLs — a fresh clone runs without building.
- **Windows 64-bit only** — the binary core (`_step_exporter.pyd`) and the OCCT
  `TK*.dll` runtimes are Windows x64; there is no Linux/macOS build.
- Added release packaging script `tools/make_release.py`.

---

## [4.2.x] — mid-2026

### Added
- **Parametric shell** (壳体):
  - Parametric shell creation + editing (rounded / square / cosine-wall shells).
  - Eccentric shells (偏心壳体), bottom-thickness parameter.
  - Rim/edge profiles (rectangular, trapezoidal inside/outside).
  - Bottom fillets (radius computed from the side wall down to the bottom).
  - Round and rounded-rectangular through-holes with mouth fillets on curved
    (cosine) walls; hole editing + delete.
  - Cosine-wall layer count setting; OCCT-based shell + hole preview.
- **Cylinder / cone galleries** (圆柱库 / 圆锥库 / 倒锥库): expanded from 96 to 192
  objects each; a second set adds the trapezoidal groove (梯形槽).
- **Groove (梯形槽) support** on cylinders, cones and inverted-cones: solid,
  through-hole, blind-hole and stepped-hole variants.
- **Stepped holes** (阶梯孔): straight + tapered step, chamfer/fillet combos.
- **Blind / tapered / dual-end holes** with mouth fillets and chamfers.
- **Edge features**: chamfers and fillets on both ends of cylinders and cones.
- **Top/bottom shells**: parametric top shell with curved walls, 3 skylights,
  side-wall holes, step ring, bottom shell with 4 through-holes and fillets.
- **Curve export**: Bezier and NURBS support; bezier-circle fix.
- **i18n**: Chinese / English UI (多语言化).
- **Mirror X axis** option in STEP export.
- **CI**: GitHub Actions (build with OCCT 7.8.1 prebuilt, unit tests in Blender,
  integration tests, ruff lint).
- Export progress bar, log file, auto Blender→FreeCAD screenshot comparison scripts.

### Changed
- Upgraded target from Blender 4.2.1 to **Blender 5.2.0** (better boolean drills).
- OpenCASCADE 7.7.2 → **7.8.1**.
- Hole-drilling now uses **FLOAT** boolean; added solver-choice UI.
- Unified Blender/STEP units (mm/m); fixed FreeCAD size/position consistency.
- Reorganized large `__init__.py`/`.cpp` files into sub-packages.

---

## [4.1.x] — early 2026

### Added
- First working STEP export from Blender (cylinders, cones, hollow shapes).
- Tapered (2°–5° draft) cylinders and standard cones.
- Edge chamfers / fillets with super-ellipse fitting (Bevel ↔ FreeCAD fillet,
  coefficient 1.8745, error −0.003%).
- Hollow cylinders (straight & tapered) and hollow cones.
- Rounded-rectangle STEP export (perfect analytic surfaces).
- 4-through-hole bottom shell and filleted bottom shell export.
- Progress reporting; export log improvements.
- Units: mm/m handling; STEP schema selection (AP203 / AP214 / AP242).

### Fixed
- FreeCAD dimension/position mismatches vs Blender.
- Bambu Studio unit-confirmation issue (mm STEP files).

---

[4.2.3]: https://github.com/langhua/blender2step/releases/tag/v4.2.3
[5.0.0]: https://github.com/langhua/blender2step/releases/tag/v5.0.0
