#!/usr/bin/env python3
"""
检查项目所有依赖的工具
"""

import os
import sys
import subprocess
from pathlib import Path

def run_command_safe(cmd, cwd=None):
    """安全运行命令，避免编码问题"""
    try:
        result = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace'
        )
        return result
    except Exception as e:
        print(f"Command failed: {e}")
        return None

def check_all_dependencies():
    """检查所有依赖"""
    project_dir = Path(__file__).parent.parent
    vcpkg_dir = Path(r"F:\git\vcpkg")
    python_dir = Path(r"C:\Python311")
    
    print("=" * 60)
    print("Dependency Check Tool")
    print("=" * 60)
    
    all_ok = True
    
    # 1. 检查 Python
    print("\n1. Checking Python environment:")
    print(f"   Python version: {sys.version}")
    print(f"   Architecture: {'64-bit' if sys.maxsize > 2**32 else '32-bit'}")
    print(f"   Executable: {sys.executable}")
    
    # 检查 python311.dll
    python_dll = python_dir / "python311.dll"
    if python_dll.exists():
        print(f"   [OK] Python DLL: {python_dll}")
    else:
        print(f"   [ERROR] Python DLL not found: {python_dll}")
        all_ok = False
    
    # 2. 检查 vcpkg
    print("\n2. Checking vcpkg:")
    vcpkg_exe = vcpkg_dir / "vcpkg.exe"
    if vcpkg_exe.exists():
        print(f"   [OK] vcpkg executable: {vcpkg_exe}")
        
        # 检查 OpenCASCADE
        install_dir = vcpkg_dir / "installed" / "x64-windows"
        if install_dir.exists():
            print(f"   [OK] vcpkg install directory: {install_dir}")
            
            # 检查关键库
            critical_libs = ["TKernel.dll", "TKDESTEP.dll", "TKMath.dll", "TKG3d.dll"]
            bin_dir = install_dir / "bin"
            missing_libs = []
            
            for lib in critical_libs:
                lib_path = bin_dir / lib
                if lib_path.exists():
                    print(f"     [OK] {lib}")
                else:
                    print(f"     [ERROR] {lib}")
                    missing_libs.append(lib)
            
            if missing_libs:
                print(f"   [WARN] Missing {len(missing_libs)} critical libraries")
                all_ok = False
                
            # 检查库文件
            lib_dir = install_dir / "lib"
            if lib_dir.exists():
                tk_libs = list(lib_dir.glob("TK*.lib"))
                if tk_libs:
                    print(f"   [OK] Found {len(tk_libs)} TK library files")
                else:
                    print(f"   [WARN] No TK library files found")
        else:
            print(f"   [ERROR] vcpkg install directory not found")
            all_ok = False
    else:
        print(f"   [ERROR] vcpkg not found: {vcpkg_exe}")
        all_ok = False
    
    # 3. 检查构建目录
    print("\n3. Checking build directories:")
    build_configs = [
        project_dir / "out" / "build" / "x64-Release",
        project_dir / "out" / "build" / "x64-RelWithDebInfo",
        project_dir / "out" / "build" / "x64-Debug",
        project_dir / "build" / "Release",
        project_dir / "build2" / "Release",
    ]
    
    found_build = False
    for build_dir in build_configs:
        if build_dir.exists():
            pyd_files = list(build_dir.glob("*.pyd"))
            if pyd_files:
                print(f"   [OK] Found build directory: {build_dir}")
                print(f"        Plugin file: {pyd_files[0].name}")
                
                # 列出 DLL 文件
                dll_files = list(build_dir.glob("*.dll"))
                if dll_files:
                    print(f"        Found {len(dll_files)} DLL files")
                
                found_build = True
                break
            else:
                print(f"   [WARN] Build directory exists but no .pyd files: {build_dir}")
    
    if not found_build:
        print("   [WARN] No build directory found, please build the project first")
        all_ok = False
    
    # 4. 检查系统运行时
    print("\n4. Checking system runtime libraries:")
    vc_dlls = ["vcruntime140.dll", "msvcp140.dll", "vcruntime140_1.dll"]
    system32 = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32"
    
    for dll in vc_dlls:
        dll_path = system32 / dll
        if dll_path.exists():
            print(f"   [OK] {dll}")
        else:
            print(f"   [WARN] {dll} not found in System32")
    
    # 5. 测试插件加载
    print("\n5. Testing plugin loading:")
    if found_build:
        for build_dir in build_configs:
            if build_dir.exists():
                pyd_files = list(build_dir.glob("*.pyd"))
                if pyd_files:
                    success = test_plugin_in_directory(build_dir)
                    if not success:
                        all_ok = False
                    break
    else:
        print("   [SKIP] No build directory found, skipping plugin test")
    
    print("\n" + "=" * 60)
    if all_ok:
        print("[SUCCESS] All dependencies checked successfully!")
    else:
        print("[WARNING] Some dependency issues found")
    
    return all_ok

def test_plugin_in_directory(build_dir):
    """在指定目录测试插件"""
    import os
    import sys
    import traceback
    
    print(f"   Testing in directory: {build_dir}")
    
    # 切换到构建目录
    original_dir = os.getcwd()
    os.chdir(build_dir)
    
    try:
        # 设置 DLL 搜索路径
        try:
            os.add_dll_directory(str(build_dir))
        except:
            pass
        
        os.environ['PATH'] = str(build_dir) + ';' + os.environ.get('PATH', '')
        sys.path.insert(0, str(build_dir))
        
        # 查找插件文件
        pyd_files = [f for f in os.listdir('.') if f.lower().endswith('.pyd')]
        if not pyd_files:
            print("   [ERROR] No .pyd files found")
            return False
        
        plugin_name = os.path.splitext(pyd_files[0])[0]
        print(f"   Plugin file: {pyd_files[0]}")
        print(f"   Module name: {plugin_name}")
        
        try:
            # 动态导入插件
            plugin_module = __import__(plugin_name)
            print(f"   [OK] Plugin imported successfully: {plugin_name}")
            
            # 测试版本函数
            if hasattr(plugin_module, 'get_version'):
                try:
                    version = plugin_module.get_version()
                    print(f"        Version: {version}")
                except Exception as e:
                    print(f"        [ERROR] Failed to get version: {e}")
            else:
                print("        [WARN] get_version() function not found")
            
            return True
            
        except ImportError as e:
            print(f"   [ERROR] Import failed: {e}")
            
            # 检查缺少的 DLL
            print("   Checking for missing DLLs:")
            required_dlls = ['TKernel.dll', 'TKDESTEP.dll', 'TKSTEP.dll', 'python311.dll']
            
            for dll in required_dlls:
                dll_path = os.path.join(build_dir, dll)
                if os.path.exists(dll_path):
                    print(f"        [OK] {dll}")
                else:
                    print(f"        [ERROR] {dll} (MISSING)")
            
            return False
        except Exception as e:
            print(f"   [ERROR] Unexpected error: {e}")
            traceback.print_exc()
            return False
            
    finally:
        os.chdir(original_dir)

if __name__ == "__main__":
    try:
        success = check_all_dependencies()
        if success:
            sys.exit(0)
        else:
            sys.exit(1)
    except KeyboardInterrupt:
        print("\n\nCheck interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n[ERROR] Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
