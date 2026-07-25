@echo off
echo Running STEP verification...
echo.
"F:\Program Files\Blender Foundation\Blender 5.2\5.2\python\bin\python.exe" F:\git\blender2step\_verify_groups.py > F:\git\blender2step\_verify_result.txt 2>&1
echo Done. Check _verify_result.txt
type F:\git\blender2step\_verify_result.txt
pause
