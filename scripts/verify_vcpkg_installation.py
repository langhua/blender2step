#!/usr/bin/env python3
"""
验证 vcpkg 和 OpenCASCADE 安装
"""

import os
import sys
import subprocess
import re
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

def verify_vcpkg_installation():
    """验证 vcpkg 安装的 OpenCASCADE"""
    vcpkg_dir = Path(r"F:\git\vcpkg")
    vcpkg_exe = vcpkg_dir / "vcpkg.exe"
    
    print("=" * 60)
    print("Verify vcpkg OpenCASCADE Installation")
    print("=" * 60)
    
    # 1. 检查 vcpkg 可执行文件
    print("1. Checking vcpkg executable...")
    if not vcpkg_exe.exists():
        print(f"   [ERROR] vcpkg executable not found: {vcpkg_exe}")
        return False
    print(f"   [OK] vcpkg executable: {vcpkg_exe}")
    
    # 2. 检查已安装的包
    print("\n2. Checking installed packages...")
    result = run_command_safe([str(vcpkg_exe), "list"])
    
    if result and "opencascade" in result.stdout.lower():
        print("   [OK] OpenCASCADE is installed")
        for line in result.stdout.split('\n'):
            if "opencascade" in line.lower():
                print(f"      {line.strip()}")
    else:
        print("   [ERROR] OpenCASCADE is not installed")
        if result:
            print(f"   Output: {result.stdout[:200]}")
        return False
    
    # 3. 检查安装文件
    print("\n3. Checking installed files...")
    install_dir = vcpkg_dir / "installed" / "x64-windows"
    
    if not install_dir.exists():
        print(f"   [ERROR] vcpkg install directory not found: {install_dir}")
        return False
    
    print(f"   [OK] Install directory: {install_dir}")
    
    # 检查头文件
    inc_dir = install_dir / "include" / "opencascade"
    if inc_dir.exists():
        try:
            hxx_files = [f for f in inc_dir.iterdir() if f.name.endswith('.hxx')]
            print(f"   [OK] Header directory: {inc_dir}")
            print(f"        Found {len(hxx_files)} header files")
        except Exception as e:
            print(f"   [OK] Header directory: {inc_dir} (error: {e})")
    else:
        print("   [ERROR] OpenCASCADE header directory not found")
    
    # 检查库文件
    lib_dir = install_dir / "lib"
    if lib_dir.exists():
        try:
            tk_libs = [f for f in lib_dir.iterdir() if f.name.startswith('TK') and f.name.endswith('.lib')]
            print(f"   [OK] Library directory: {lib_dir}")
            print(f"        Found {len(tk_libs)} TK libraries")
            
            # 显示关键库
            critical_libs = ["TKernel.lib", "TKDESTEP.lib", "TKSTEP.lib", "TKMath.lib", "TKG3d.lib"]
            for lib in critical_libs:
                lib_path = lib_dir / lib
                if lib_path.exists():
                    print(f"        [OK] {lib}")
                else:
                    print(f"        [WARN] {lib} not found")
                    
        except Exception as e:
            print(f"   [ERROR] Cannot list library files: {e}")
    else:
        print("   [ERROR] Library directory not found")
    
    # 检查 DLL 文件
    bin_dir = install_dir / "bin"
    if bin_dir.exists():
        try:
            tk_dlls = [f for f in bin_dir.iterdir() if f.name.startswith('TK') and f.name.endswith('.dll')]
            print(f"   [OK] DLL directory: {bin_dir}")
            print(f"        Found {len(tk_dlls)} TK DLLs")
        except Exception as e:
            print(f"   [OK] DLL directory: {bin_dir} (error: {e})")
    else:
        print("   [ERROR] DLL directory not found")
    
    # 4. 检查 CMake 配置文件
    print("\n4. Checking CMake configuration files...")
    cmake_config_paths = [
        install_dir / "share" / "opencascade" / "OpenCASCADEConfig.cmake",
        install_dir / "share" / "OpenCASCADE" / "OpenCASCADEConfig.cmake",
        install_dir / "lib" / "cmake" / "OpenCASCADE" / "OpenCASCADEConfig.cmake",
    ]
    
    found_config = False
    for config_path in cmake_config_paths:
        if config_path.exists():
            print(f"   [OK] Found CMake config: {config_path}")
            found_config = True
            
            # 读取版本信息
            try:
                with open(config_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                    version_match = re.search(r'set\s*\(\s*OpenCASCADE_VERSION\s+"([^"]+)"\s*\)', content)
                    if version_match:
                        version = version_match.group(1)
                        print(f"        OpenCASCADE version: {version}")
            except Exception as e:
                print(f"        Error reading config: {e}")
            break
    
    if not found_config:
        print("   [WARN] CMake config file not found")
    
    # 5. 检查工具链文件
    print("\n5. Checking vcpkg toolchain file...")
    toolchain_file = vcpkg_dir / "scripts" / "buildsystems" / "vcpkg.cmake"
    
    if toolchain_file.exists():
        print(f"   [OK] Found vcpkg toolchain: {toolchain_file}")
        
        # 提供使用示例
        print("\n" + "=" * 60)
        print("Usage instructions for CMakeLists.txt:")
        print("-" * 60)
        print(f'set(CMAKE_TOOLCHAIN_FILE "{toolchain_file}")')
        print("find_package(OpenCASCADE CONFIG REQUIRED)")
        print("# Link with: target_link_libraries(your_target PRIVATE OpenCASCADE::TKernel ...)")
    else:
        print(f"   [ERROR] vcpkg toolchain file not found: {toolchain_file}")
        return False
    
    print("\n" + "=" * 60)
    print("Verification completed successfully!")
    return True

if __name__ == "__main__":
    try:
        success = verify_vcpkg_installation()
        if success:
            sys.exit(0)
        else:
            sys.exit(1)
    except KeyboardInterrupt:
        print("\n\nVerification interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n[ERROR] Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
