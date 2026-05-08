import os
path = r"F:\git\blender2step\build\bottom_shell-freecad.png"
if os.path.exists(path):
    stat = os.stat(path)
    print(f"File exists: {path}")
    print(f"Size: {stat.st_size} bytes")
    print(f"Modified: {stat.st_mtime}")
else:
    print("File does not exist")
