cd blender2step\build
Remove-Item CMakeCache.txt -ErrorAction SilentlyContinue
cmake .. -DCMAKE_TOOLCHAIN_FILE="F:/git/vcpkg/scripts/buildsystems/vcpkg.cmake"

cmake --build . --config Release

Copy-Item -Path "F:\git\blender2step\build\Release\_step_exporter.pyd" -Destination "F:\git\blender2step\step_exporter\lib\" -Force

