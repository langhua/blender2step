@echo off
echo Checking .pyd versions...
echo.
echo Source:
dir "F:\git\blender2step\build\Release\_step_exporter.pyd" | findstr _step_exporter
echo.
echo Destination:
dir "F:\git\blender2step\step_exporter\lib\_step_exporter.pyd" | findstr _step_exporter
echo.
echo Copying...
copy /Y "F:\git\blender2step\build\Release\_step_exporter.pyd" "F:\git\blender2step\step_exporter\lib\_step_exporter.pyd"
echo.
echo Result:
dir "F:\git\blender2step\step_exporter\lib\_step_exporter.pyd" | findstr _step_exporter
echo.
echo DONE - Now restart Blender
pause
