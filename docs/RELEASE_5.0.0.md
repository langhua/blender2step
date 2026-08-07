# Release v5.0.0 — Blender 5.0+ & Groove Eccentricity

**blender2step** is a Blender addon that exports 3D models to STEP using OpenCASCADE 7.8.1.
This release focuses on parametric editing of cylinders/cones/shells, exact OCCT-based
previews, and a new **groove eccentricity** parameter.

> **⚠ Platform: Windows 64-bit only.** The zip bundles a Windows `_step_exporter.pyd`
> (Python extension) and OpenCASCADE `TK*.dll` runtimes, so this build does **not** run
> on Linux or macOS.

Requires **Blender 5.0+ (Python 3.13)** (tested on 5.2).

> **Why Blender 5.0+?** The compiled `_step_exporter.pyd` is a CPython **3.13** extension.
> CPython extensions are binary-bound to the Python minor version, and Blender 4.x ships
> Python 3.11, so the addon cannot load there. Blender 5.0 and newer use Python 3.13.

---

## ✨ New in this release

- **Blender 5.0+ / Python 3.13 only** — the addon is aligned to the Python 3.13
  interpreter shipped with Blender 5.0+; `bl_info` minimum is `(5, 0, 0)`.
- **Groove eccentricity (`Eccentric %`)** — move the external trapezoidal groove
  up/down on cylinders and cones as a percentage of height (−45% … +45%).
  - Cones adapt the groove to the local wall radius, so the groove stays flush with
    the slanted surface at any offset.
  - The Blender preview and the STEP export use the **same** OCCT geometry.
- **Parametric editing ("Write to Selected")** for cylinders, cones, inverted-cones
  and parametric shells — adjust parameters and regenerate an existing object in place.
- **OCCT-generated preview meshes** for cylinders/cones/inverted-cones, so what you
  see in Blender matches the STEP file exactly.
- **Fully parametric cylinder export** — parts are exported from their stored
  creation parameters instead of fragile mesh re-detection.

## 🐛 Bug fixes

- **Grooved cone STEP export** produced wrong groove size/position. The export now
  always computes groove parameters from the live creation parameters (previously it
  could read stale values after editing), so **preview == export**.
- Removed a 0.2 mm groove-width discrepancy (bmesh boolean margin leaked into the
  exported width).
- Cone inverted-radius compensation (only chamfers enlarge the outer radius).
- Removed leftover debug logging from the export path.

## 📦 Installation

1. Download `blender2step-5.0.0.zip`.
2. Blender: **Edit → Preferences → Add-ons → Install from Disk…** → select the zip → enable
   **"STEP Exporter (Enhanced)"**.
3. Find it under **File → Export → STEP (Enhanced)**.

The zip bundles the compiled C++ core (`_step_exporter.pyd`) and all OpenCASCADE
runtime DLLs — no separate build or install is needed. **Windows 64-bit only.**

## 🔨 Build from source

```shell
cmake --build build --config Release          # produces step_exporter/lib/_step_exporter.pyd
python tools/make_release.py                  # packages blender2step-5.0.0.zip
```

Requires Python 3.13 and OpenCASCADE 7.8.1 (see `BUILD.md`).

## 🚀 Release checklist

Steps to cut a new release (run from the repo root, Windows x64):

1. **Bump the version** in `step_exporter/__init__.py` (`bl_info["version"]`,
   `bl_info["blender"]`) and `src/export/module.cpp` (`MODULE_VERSION`); add a
   `CHANGELOG.md` entry and update the README / release-note docs.
2. **Rebuild the C++ core and commit the binary** — the release zip only packs
   git-tracked files, so the rebuilt `step_exporter/lib/_step_exporter.pyd` (and
   any changed DLLs) must be committed:
   ```shell
   cmake --build build --config Release
   ```
3. **Audit `step_exporter/lib/`** — no orphaned DLLs may be present:
   ```shell
   python tools/audit_lib.py --check
   ```
4. **Build the release zip** (runs the orphan check again automatically):
   ```shell
   python tools/make_release.py            # -> blender2step-<version>.zip
   ```
5. **Smoke-test the zip**: install in a fresh Blender 5.x, create + export a
   parametric part, and verify the STEP in FreeCAD.
6. **Push** — CI runs build / test / integration / lint (including the lib audit).
7. **Tag & publish**: `git tag v<version>` → GitHub Release → attach
   `blender2step-<version>.zip` and paste this file's content as the release notes.

## ✅ Tests

CI runs C++ build + Blender unit tests + integration tests (create → export STEP →
verify shells) + ruff lint. See `CHANGELOG.md` for the full history.

---

Full changelog: [`CHANGELOG.md`](../CHANGELOG.md)
