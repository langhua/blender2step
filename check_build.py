# check_build.py
import os
import sys
import subprocess

def check_visual_studio():
    """检查Visual Studio安装"""
    vs_paths = [
        r"C:\Program Files\Microsoft Visual Studio\2022\Community\Common7\Tools\VsDevCmd.bat",
        r"C:\Program Files\Microsoft Visual Studio\2019\Community\Common7\Tools\VsDevCmd.bat"
    ]
    
    for path in vs_paths:
        if os.path.exists(path):
            return path
    return None

def check_vcpkg():
    """检查vcpkg安装"""
    vcpkg_path = r"F:\git\vcpkg\vcpkg.exe"
    if os.path.exists(vcpkg_path):
        return vcpkg_path
    return None

def check_opencascade():
    """检查OpenCASCADE安装"""
    occ_path = r"F:\git\vcpkg\installed\x64-windows\share\opencascade"
    if os.path.exists(occ_path):
        return occ_path
    return None

def check_python():
    """检查Python安装"""
    python_paths = [
        r"C:\Python311\python.exe",
        sys.executable
    ]
    
    for path in python_paths:
        if os.path.exists(path):
            return path
    return None

def main():
    print("=== 编译环境检查 ===")
    
    # 检查Visual Studio
    vs_path = check_visual_studio()
    if vs_path:
        print(f"✓ Visual Studio: {vs_path}")
    else:
        print("✗ Visual Studio未找到")
    
    # 检查vcpkg
    vcpkg_path = check_vcpkg()
    if vcpkg_path:
        print(f"✓ vcpkg: {vcpkg_path}")
    else:
        print("✗ vcpkg未找到")
    
    # 检查OpenCASCADE
    occ_path = check_opencascade()
    if occ_path:
        print(f"✓ OpenCASCADE: {occ_path}")
    else:
        print("✗ OpenCASCADE未找到")
    
    # 检查Python
    python_path = check_python()
    if python_path:
        print(f"✓ Python: {python_path}")
    else:
        print("✗ Python未找到")
    
    # 检查编译输出
    build_dir = r"F:\git\blender2step\out\build\x64-Release\bin"
    if os.path.exists(build_dir):
        print(f"\n✓ 编译目录存在: {build_dir}")
        
        # 列出目录内容
        files = os.listdir(build_dir)
        print(f"  目录内容:")
        for file in files:
            if file.endswith('.pyd') or file.endswith('.dll'):
                print(f"    - {file}")
    else:
        print(f"\n✗ 编译目录不存在: {build_dir}")
    
    print("\n=== 建议操作 ===")
    print("1. 确保Visual Studio已安装CMake组件")
    print("2. 运行: vcpkg install opencascade:x64-windows")
    print("3. 清理并重新生成CMake缓存")
    print("4. 在Visual Studio中重新编译")

if __name__ == "__main__":
    main()