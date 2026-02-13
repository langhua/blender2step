@echo off
echo 运行所有检查
echo =============
echo.

cd /d "%~dp0.."

echo 1. 检查vcpkg安装...
python scripts\verify_vcpkg_installation.py

echo.
echo 2. 检查依赖...
python scripts\check_dependencies.py

echo.
echo 3. 测试插件...
python tests\test_plugin.py

echo.
pause