# 构建说明 (Build Guide)

## 环境要求

| 组件 | 版本 | 说明 |
|------|------|------|
| Visual Studio | 2022 Community | 含 C++ CMake 工具 |
| Python | 3.13.x | 与 Blender 5.2 一致 |
| vcpkg | latest | 包管理器 |
| OpenCASCADE | 7.8.1 | 通过 vcpkg 安装 |

> 详细的环境安装步骤请参见 [README.md](./README.md) 的 Development 部分。

## 快速构建

```powershell
# 1. 进入 build 目录
cd f:\git\blender2step\build

# 2. 编译（Release 模式）
cmake --build . --config Release

# 3. .pyd 会自动复制到 step_exporter/lib/
# 如果没有自动复制，手动执行：
Copy-Item -Path "f:\git\blender2step\build\Release\_step_exporter.pyd" -Destination "f:\git\blender2step\step_exporter\lib\" -Force
```

## 验证构建

```powershell
# 验证 .pyd 是否可用
python verify_build.py
```

期望输出：
```
Module loaded OK
Version: 4.1.2
OCCT: 7.8.1
merge_step_files: FOUND
```

## 常见问题

### CMake 缓存错误

如果遇到 `could not find CMAKE_GENERATOR in Cache`：

```powershell
cd f:\git\blender2step
Remove-Item build\CMakeCache.txt -ErrorAction SilentlyContinue
cd build
cmake .. -DCMAKE_TOOLCHAIN_FILE="F:/git/vcpkg/scripts/buildsystems/vcpkg.cmake" -DOpenCASCADE_DIR="f:/git/blender2step/vcpkg_installed/x64-windows/share/opencascade"
```

### Python 链接错误

确保 `C:\Python313\libs\python313.lib` 存在。如果缺失：
- 安装 Python 3.13.x 或从源码构建

### OpenCASCADE 找不到

确认 vcpkg 已正确安装 OCCT 7.8.1：
```powershell
ls f:\git\vcpkg\installed\x64-windows\share\opencascade\
```

### .pyd 加载失败

```powershell
# 检查 DLL 依赖
python step_exporter/tests/diagnose_step_exporter.py
```

---

## 本地构建 vs CI 构建

| | 本地 (CMakeLists.txt) | CI (CMakeLists.ci.txt) |
|---|---|---|
| vcpkg | 本地 `f:/git/vcpkg/` | GitHub Release 预编译包 |
| Python | `C:/Python313/` | `actions/setup-python@v5` |
| 用途 | 开发调试 | CI 验证编译 |

CI 使用 `CMakeLists.ci.txt`（不含硬编码路径），从 GitHub Release 下载 OCCT 预编译包。

