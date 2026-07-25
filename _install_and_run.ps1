$python = "F:\Program Files\Blender Foundation\Blender 5.2\5.2\python\bin\python.exe"

Write-Host "Upgrading pip..."
& $python -m pip install --upgrade pip

Write-Host "Installing pythonocc-core..."
& $python -m pip install pythonocc-core

Write-Host "Running verify script..."
& $python F:\git\blender2step\_verify_groups.py > F:\git\blender2step\_verify_result.txt 2>&1

Write-Host "Done."
Get-Content F:\git\blender2step\_verify_result.txt
