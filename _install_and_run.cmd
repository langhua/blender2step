@echo off
set PYTHON=F:\Program Files\Blender Foundation\Blender 5.2\5.2\python\bin\python.exe

echo Upgrading pip...
"%PYTHON%" -m pip install --upgrade pip

echo Installing pythonocc-core...
"%PYTHON%" -m pip install pythonocc-core

echo Running verify script...
"%PYTHON%" F:\git\blender2step\_verify_groups.py > F:\git\blender2step\_verify_result.txt 2>&1

echo Done.
type F:\git\blender2step\_verify_result.txt
