# blender2step Project Setup

## File Locations
- **Git repo**: `f:\git\blender2step\`
- **Blender addon**: `C:\Users\shi.jinghai-honor\AppData\Roaming\Blender Foundation\Blender\4.2\scripts\addons\step_exporter\` → **junction to** `f:\git\blender2step\step_exporter\`
- Edits to `f:\git\blender2step\step_exporter\` are immediately reflected in Blender. Do NOT edit AppData files directly.
- **No need to copy files to Blender** — the junction means any change to the git repo is instantly available in Blender.

## Design Rule
- **Blender preview must match STEP exactly** — BMesh preview and C++ STEP export must produce identical geometry. Use the same algorithmic approach (e.g., Boolean ops) for both, not separate implementations that diverge.
- **Bottom fillet → direct shell construction** — 当设置底部圆角(bf>0)时，禁止使用 Boolean 切削方式（底面和侧壁会分离），必须使用 `_build_square`/`_build_rounded` 直接构建壳体的方法，然后对底部边（外层 Z=0 + 内层 Z=t）统一倒角。内外倒角半径让 Blender 自动生成。

## Build
- C++ build: `cd f:\git\blender2step\build` → `cmake --build . --config Release`
- `.pyd` auto-copies to `step_exporter/lib/` on build

## Python Module Structure
```
step_exporter/
├── __init__.py           entry point, C++ loading, register/unregister
├── _globals.py           shared state
├── utils.py              logging, file merge, verify
├── core/                 mesh_data.py, utils.py, _globals.py
├── analysis/             top_shell.py, bottom_shell.py, cylinder.py
├── export/               sync_export.py, staged_export.py, worker_timer.py, progress_report.py
├── ui/                   export_operator.py, panels.py, sample_ops.py, parametric_cylinder.py, cylinder_panel.py
├── examples/             sample scripts (create_top_shell etc.)
└── tests/                test scripts
```

## C++ Module Structure
```
src/
├── curve/       curve*.cpp
├── cylinder/    cylinder_*.cpp/h
├── export/      export_scene, enhanced*, incremental, module
├── shape/       fix_shape, create_*, shape_fix, rounded_box
└── step_converter.cpp
```
