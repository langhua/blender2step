# blender2step
Blender step exporter based on OpenCASCADE.




## Development

### Install Python 3.11.4

As the python version in Blender 4.2.1 is 3.11.4, you need to install the same version of Python.

1. Visit https://www.python.org/downloads/release/python-3114/

2. Download "Windows installer (64-bit)" and install it.


### Build Python 3.11.4 on Windows 11 with Visual Studio Community 2022

As I didn't have python311_d.lib installed, I built it from source.

1. Visit the source code from https://www.python.org/ftp/python/3.11.4/

2. Download Python-3.11.4.tar.xz and extract it.

3. Open a terminal, cd \Python-3.11.4.tar\Python-3.11.4\PCbuild, run .\get_externals.bat:

```
PS F:\Python-3.11.4.tar\Python-3.11.4\PCbuild> .\get_externals.bat
Using "F:\Python-3.11.4.tar\Python-3.11.4\PCbuild\\..\externals\pythonx86\tools\python.exe" (found in externals directory)
Fetching external libraries...
Fetching bzip2-1.0.8...
Fetching sqlite-3.42.0.0...
Fetching xz-5.2.5...
Fetching zlib-1.2.13...
Fetching external binaries...
Fetching libffi-3.4.4...
Fetching openssl-bin-1.1.1u...
Fetching tcltk-8.6.12.1...
Finished.
```

4. Open Python-3.11.4.tar\Python-3.11.4\PCbuild\pcbuild.sln with Visual Studio Community 2022, run Debug|x64, build the solution.

5. Copy python311_d.lib from Python-3.11.4.tar\Python-3.11.4\PCbuild\amd64\ to the installed python 3.11.4 lib folder, e.g. C:\Python311\libs.

### Build OpenCASCADE 7.9.3 on Windows 11 with vcpkg

1. Clone vcpkg:
```
cd F:\git\
git clone https://github.com/microsoft/vcpkg.git
cd vcpkg
```

2. Bootstrap vcpkg:
```
.\bootstrap-vcpkg.bat
```

3. Integrate vcpkg with Windows:
```
.\vcpkg integrate install
```

4. Install OpenCASCADE 7.9.3:
```
.\vcpkg install opencascade:x64-windows@7.9.3
```

Remove-Item -Recurse -Force F:\git\vcpkg\buildtrees\opencascade\x64-windows-dbg\win64\vc14\bind\TKGeomAlgo.dll -ErrorAction SilentlyContinue
Remove-Item -Recurse -Force F:\git\vcpkg\buildtrees\opencascade\x64-windows-dbg\ -ErrorAction SilentlyContinue

### Build blender2step with Visual Studio Community 2022

1. 