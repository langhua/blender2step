

# 测试文档 (Tests)

## 目录

- [测试架构总览](#测试架构总览)
- [测试分类](#测试分类)
  - [A. 基础单元测试（无需 Blender）](#a-基础单元测试无需-blender)
  - [B. Blender 集成测试（需 Blender + C++ .pyd）](#b-blender-集成测试需-blender--c-pyd)
  - [C. 构建验证](#c-构建验证)
  - [D. STEP 输出验证](#d-step-输出验证)
  - [E. 诊断/分析脚本](#e-诊断分析脚本)
- [运行测试](#运行测试)
- [CI（GitHub Actions）](#cigithub-actions)
- [OCCT 预编译包发布](#occt-预编译包发布)

---

## 测试架构总览

```
                    ┌─────────────────────────────┐
                    │     ci_test_runner.py        │  ← CI 入口（Blender 内运行 pytest）
                    │  blender --background        │
                    └──────────┬──────────────────┘
                               │
           ┌───────────────────┼───────────────────┐
           ▼                   ▼                   ▼
   ┌──────────────┐   ┌──────────────┐   ┌──────────────┐
   │ test_core_   │   │  test_i18n   │   │ ci_integration│
   │ utils.py     │   │  .py         │   │ _test.py      │
   │ (纯 Python)  │   │ (纯 Python)  │   │ (完整流程)     │
   └──────┬───────┘   └──────┬───────┘   └──────┬───────┘
          │                  │                  │
          ▼                  ▼                  ▼
   ┌──────────────────────────────────────────────────┐
   │  C++ 扩展: _step_exporter.pyd (OpenCASCADE 7.8.1) │
   └──────────────────────────────────────────────────┘
```

## 测试分类

### A. 基础单元测试（无需 Blender）

这些测试可以直接用系统 Python 运行，不依赖 Blender。

| 文件 | 测试内容 | 运行方式 |
|------|---------|---------|
| `step_exporter/tests/test_core_utils.py` | `_verify_step_shell`（STEP shell 计数）、`_merge_step_files`（合并 STEP）、`log_to_file`（日志） | `pytest step_exporter/tests/test_core_utils.py -v` |
| `step_exporter/tests/test_i18n.py` | 翻译键完整性（zh_CN 覆盖率）、格式占位符匹配、`_build_translations()` | `pytest step_exporter/tests/test_i18n.py -v` |
| `tests/test_plugin.py` | `.pyd` 文件发现、模块加载、版本号验证 | `python tests/test_plugin.py` |

### B. Blender 集成测试（需 Blender + C++ .pyd）

这些测试必须在 Blender 环境中运行（依赖 `bpy`、`bmesh` 和 C++ 扩展）。

| 文件 | 测试内容 | 备注 |
|------|---------|------|
| `ci_integration_test.py` | **主集成测试**：创建各类圆柱体 → 同步导出 STEP → 验证 shell 数量 | CI 核心测试，覆盖 standard/tapered/chamfer/fillet/thru_hole/stepped |
| `step_exporter/tests/test_chamfered_cylinder.py` | 倒角圆柱体顶点生成和导出 | 独立脚本，手动运行 |
| `step_exporter/tests/test_fillet_cylinder.py` | 圆角圆柱体 Blender 建模和导出 | 使用 `bpy.ops.mesh.bevel` |
| `step_exporter/tests/test_tapered_cylinder.py` | 2° 锥度圆柱体验证 | 含 `tan(α)` 半径计算验证 |
| `step_exporter/tests/test_multiple_tapers.py` | 多锥度角度测试 | 多角度参数扫描 |
| `step_exporter/tests/test_volume_zero.py` | 零体积形状（平面）导出修复 | 验证平面不被导出 |
| `step_exporter/tests/test_blender_export.py` | Blender 基础导出流程 | 立方体/球体/圆柱组合导出 |

#### 运行 Blender 集成测试

```powershell
# 运行全部 CI 测试（推荐）
& "f:\Program Files\Blender Foundation\Blender 4.2\blender.exe" --background --python ci_test_runner.py

# 运行单个集成测试
& "f:\Program Files\Blender Foundation\Blender 4.2\blender.exe" --background --python ci_integration_test.py
```

### C. 构建验证

| 文件 | 功能 | 运行方式 |
|------|------|---------|
| `check_build.py` | 检查 VS2022、vcpkg、OpenCASCADE、Python 安装状态 | `python check_build.py` |
| `verify_build.py` | 验证 `.pyd` 加载、版本号、OCCT 版本、`merge_step_files` 函数 | `python verify_build.py` |
| `check_exports.py` | 检查 C++ 导出的 cone 相关函数 | `python check_exports.py` |
| `scripts/verify_vcpkg_installation.py` | 验证 vcpkg + OpenCASCADE 安装 | `python scripts/verify_vcpkg_installation.py` |
| `scripts/check_dependencies.py` | 检查项目依赖 | `python scripts/check_dependencies.py` |

### D. STEP 输出验证

| 文件 | 功能 | 运行方式 |
|------|------|---------|
| `verify_full.py` | 完整验证：解析 `.step.log` → 比对 STEP 几何参数（半径、高度、锥度） | `python verify_full.py` |
| `dump_step_solids.py` | 解析 STEP 文件中的实体（CLOSED_SHELL、MANIFOLD_SOLID_BREP）并打印尺寸 | `python dump_step_solids.py` |

### E. 诊断/分析脚本

这些是开发调试用的辅助脚本，**CI 中已忽略**：

| 文件 | 功能 |
|------|------|
| `step_exporter/tests/diagnose_step_exporter.py` | 诊断 `_step_exporter` 模块导入问题（DLL 搜索路径、Python 路径） |
| `step_exporter/tests/diagnose_import.py` | 导入诊断 |
| `step_exporter/tests/diagnose_cpp_ext.py` | C++ 扩展诊断 |
| `step_exporter/tests/analyze_step.py` | STEP 文件结构分析 |
| `step_exporter/tests/analyze_step_detailed.py` | STEP 文件详细分析 |
| `step_exporter/tests/analyze_positions.py` | 分析 STEP 中位置信息 |
| `step_exporter/tests/analyze_positions2.py` | 分析 STEP 中位置信息 v2 |
| `step_exporter/tests/check_coords.py` | 检查坐标数据 |
| `step_exporter/tests/simple_test.py` | 简单 Blender 插件加载测试 |

---

## 运行测试

### 快速验证（推荐顺序）

```powershell
# 1. 构建环境检查（10 秒）
python check_build.py

# 2. 验证 .pyd 编译成功（5 秒）
python verify_build.py

# 3. 运行基础单元测试（5 秒）
python -m pytest step_exporter/tests/test_core_utils.py step_exporter/tests/test_i18n.py -v

# 4. 运行完整 CI 测试（需 Blender，约 30 秒）
& "f:\Program Files\Blender Foundation\Blender 4.2\blender.exe" --background --python ci_test_runner.py
```

### 一键测试脚本

```powershell
python scripts/run_tests.py
```

该脚本依次运行：vcpkg 验证 → 依赖检查 → 插件测试。

---

## CI（GitHub Actions）

CI 配置位于 `.github/workflows/ci.yml`，触发条件：

- **Push** 到 `main` 分支（忽略 `.md`、`.txt`、`docs/`）
- **Pull Request** 到 `main` 分支
- **手动触发** (`workflow_dispatch`)

### CI 流水线（4 个 Job）

| Job | 说明 | 耗时 |
|-----|------|------|
| `build` | 从 GitHub Release 下载 OCCT 7.8.1 → 编译 C++ .pyd → 上传构建产物 | ~3 分钟 |
| `test` | 下载 Blender 4.2 → 运行 `ci_test_runner.py`（pytest 单元测试） | ~2 分钟 |
| `lint` | ubuntu-latest 上运行 `ruff check`（Python 代码质量，允许失败） | ~30 秒 |
| `integration` | 依赖 `build`，下载 .pyd + Blender → 运行 `ci_integration_test.py`（完整流程） | ~5 分钟 |

---

## OCCT 预编译包发布

CI 使用预编译的 OCCT 7.8.1，避免每次从头编译（节省 ~30 分钟）。

### 更新 OCCT 预编译包

```powershell
# 第 1 步：打包本地 OCCT
.\scripts\pack_occt_for_ci.ps1
# 生成 occt-x64-windows-release.zip（约 200MB）

# 第 2 步：发布到 GitHub Release
# 打开 https://github.com/langhua/blender2step/releases/new
# Tag: occt-v1, Title: OCCT 7.8.1 Pre-built
# 上传 occt-x64-windows-release.zip → Publish release
```

> **注意**：仅当 OCCT 版本更新或 vcpkg 包变化时需要重新发布。

