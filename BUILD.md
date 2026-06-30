## OpenCASCADE使用7.8.1版本，与FreeCAD的OpenCASCADE版本一致


cd blender2step\build

### 如果缓存出错，运行下列命令
Error: could not find CMAKE_GENERATOR in Cache

```powershell
cd blender2step\build
Remove-Item ..\CMakeCache.txt -ErrorAction SilentlyContinue
Remove-Item CMakeCache.txt -ErrorAction SilentlyContinue
cmake .. -DCMAKE_TOOLCHAIN_FILE="F:/git/vcpkg/scripts/buildsystems/vcpkg.cmake" -DOpenCASCADE_DIR="f:/git/blender2step/vcpkg_installed/x64-windows/share/opencascade"
```

### 通常情况下，运行这两行命令即可
```powershell
cd blender2step\build
cmake --build . --config Release
```


## 拷贝文件
编译成功后，将_step_exporter.pyd文件会自动复制到lib目录下，如果没有，请手动复制：

```powershell
Copy-Item -Path "F:\git\blender2step\build\Release\_step_exporter.pyd" -Destination "F:\git\blender2step\step_exporter\lib\" -Force
```

