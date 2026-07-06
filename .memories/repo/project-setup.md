# blender2step Project Setup

## File Locations
- **Git repo**: `f:\git\blender2step\`
- **Blender addon**: `C:\Users\shi.jinghai-honor\AppData\Roaming\Blender Foundation\Blender\4.2\scripts\addons\step_exporter\` → **junction to** `f:\git\blender2step\step_exporter\`
- Edits to `f:\git\blender2step\step_exporter\` are immediately reflected in Blender. Do NOT edit AppData files directly.
- **No need to copy files to Blender** — the junction means any change to the git repo is instantly available in Blender.

## Design Rule
- **Blender preview must match STEP exactly** — BMesh preview and C++ STEP export must produce identical geometry. Use the same algorithmic approach for both, not separate implementations that diverge.
- **Bottom fillet → manual arc-ring construction** — 禁止使用任何 bevel/bpy.ops/bmesh.ops.bevel/Bevel Modifier 方式。必须手动构建圆角过渡环：将 XY 轮廓向内缩小 fillet_radius 形成底面（圆心辐条式），然后沿四分之一圆弧用 sin(θ)/1-cos(θ) 插值生成多层过渡环（expand = r*sin(θ), rise = r*(1-cos(θ))），每层与上层用 quad 连接。内外圆角半径分别为 bf 和 max(bf-t, 0.001)。C++ 侧对应使用 apply_bottom_fillet_to_box 对内外 Solid 分别倒角后布尔切削。

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
