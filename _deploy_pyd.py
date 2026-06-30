import shutil, os, time

src = r'F:\git\blender2step\build\Release\_step_exporter.pyd'
dst = r'F:\git\blender2step\step_exporter\lib\_step_exporter.pyd'

print(f'src mtime: {time.ctime(os.path.getmtime(src))}')
print(f'dst mtime: {time.ctime(os.path.getmtime(dst))}')
print(f'src size: {os.path.getsize(src)}')
print(f'dst size: {os.path.getsize(dst)}')

# copy
shutil.copy2(src, dst)
print(f'Copied! New dst mtime: {time.ctime(os.path.getmtime(dst))}')
