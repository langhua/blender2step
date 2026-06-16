# OpenCASCADE使用7.8.1版本，与FreeCAD的OpenCASCADE版本一致


cd blender2step\build

### 如果缓存出错，运行下列命令
```powershell
Remove-Item ..\CMakeCache.txt -ErrorAction SilentlyContinue
Remove-Item CMakeCache.txt -ErrorAction SilentlyContinue
cmake .. -DCMAKE_TOOLCHAIN_FILE="F:/git/vcpkg/scripts/buildsystems/vcpkg.cmake" -DOpenCASCADE_DIR="f:/git/blender2step/vcpkg_installed/x64-windows/share/opencascade"
```

### 通常情况下，运行这两行命令即可
```powershell
cmake --build . --config Release

Copy-Item -Path "F:\git\blender2step\build\Release\_step_exporter.pyd" -Destination "F:\git\blender2step\step_exporter\lib\" -Force
```
