#!/usr/bin/env python3
"""
诊断C++扩展加载问题的脚本
在Blender外部运行此脚本
"""

import os
import sys
import subprocess
import ctypes
import tempfile
from pathlib import Path

def diagnose_cpp_extension():
    """诊断C++扩展问题"""
    project_dir = Path(r"F:\git\blender2step")
    build_dir = project_dir / "out" / "build" / "x64-Release"
    
    print("=" * 60)
    print("C++ Extension Diagnosis Tool")
    print("=" * 60)
    
    if not build_dir.exists():
        print(f"[ERROR] Build directory not found: {build_dir}")
        return False
    
    # 1. 检查C++扩展文件
    print("\n1. Checking C++ extension file...")
    pyd_files = list(build_dir.glob("*.pyd"))
    
    if not pyd_files:
        print("[ERROR] No .pyd files found in build directory")
        return False
    
    pyd_file = pyd_files[0]
    print(f"[OK] Found C++ extension: {pyd_file.name}")
    print(f"    Size: {pyd_file.stat().st_size:,} bytes")
    print(f"    Path: {pyd_file}")
    
    # 2. 检查DLL依赖
    print("\n2. Checking DLL dependencies...")
    
    # 使用dumpbin检查依赖
    dumpbin_path = None
    vs_paths = [
        r"C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Tools\MSVC\14.xx.xxxxx\bin\Hostx64\x64\dumpbin.exe",
        r"C:\Program Files\Microsoft Visual Studio\2022\Professional\VC\Tools\MSVC\14.xx.xxxxx\bin\Hostx64\x64\dumpbin.exe",
        r"C:\Program Files\Microsoft Visual Studio\2022\Enterprise\VC\Tools\MSVC\14.xx.xxxxx\bin\Hostx64\x64\dumpbin.exe",
    ]
    
    for path in vs_paths:
        if os.path.exists(path):
            dumpbin_path = path
            break
    
    if dumpbin_path:
        print(f"[INFO] Using dumpbin: {dumpbin_path}")
        
        # 检查导入
        import_result = subprocess.run(
            [dumpbin_path, "/imports", str(pyd_file)],
            capture_output=True,
            text=True
        )
        
        if import_result.returncode == 0:
            print("[OK] Dumpbin imports analysis:")
            for line in import_result.stdout.split('\n'):
                if any(keyword in line for keyword in ['python', 'TK', 'kernel', 'MSVCP', 'VCRUNTIME']):
                    print(f"    {line.strip()}")
        else:
            print("[WARN] Could not analyze imports with dumpbin")
    else:
        print("[INFO] dumpbin not found, skipping dependency analysis")
    
    # 3. 尝试加载C++扩展
    print("\n3. Attempting to load C++ extension...")
    
    # 切换到构建目录
    original_dir = os.getcwd()
    os.chdir(build_dir)
    
    try:
        # 设置DLL搜索路径
        os.environ['PATH'] = str(build_dir) + ';' + os.environ.get('PATH', '')
        sys.path.insert(0, str(build_dir))
        
        # 获取模块名（不带.pyd扩展名）
        module_name = pyd_file.stem
        
        print(f"[INFO] Attempting to import module: {module_name}")
        
        # 尝试导入
        try:
            module = __import__(module_name)
            print(f"[SUCCESS] Module imported: {module}")
            
            # 检查模块属性
            print("[INFO] Module attributes:")
            for attr in dir(module):
                if not attr.startswith('_'):
                    print(f"    - {attr}")
            
            # 测试函数
            if hasattr(module, 'get_version'):
                try:
                    version = module.get_version()
                    print(f"[SUCCESS] get_version(): {version}")
                except Exception as e:
                    print(f"[ERROR] get_version() failed: {e}")
            else:
                print("[WARNING] get_version() not found")
            
            if hasattr(module, 'export_step'):
                print("[SUCCESS] export_step() found")
                
                # 测试导出
                import tempfile
                test_file = Path(tempfile.gettempdir()) / "diagnosis_test.step"
                print(f"[INFO] Testing export to: {test_file}")
                
                try:
                    result = module.export_step(str(test_file))
                    print(f"[INFO] export_step() result: {result}")
                    
                    if result and test_file.exists():
                        size = test_file.stat().st_size
                        print(f"[SUCCESS] Export successful! File size: {size:,} bytes")
                        
                        # 验证文件
                        with open(test_file, 'rb') as f:
                            first_bytes = f.read(100)
                            if b'ISO-10303-21' in first_bytes or b'STEP' in first_bytes.upper():
                                print("[SUCCESS] Valid STEP file detected")
                            else:
                                print("[WARNING] File may not be a valid STEP file")
                        
                        # 清理
                        test_file.unlink()
                    else:
                        print("[ERROR] Export failed or file not created")
                        
                except Exception as e:
                    print(f"[ERROR] export_step() failed: {e}")
                    import traceback
                    traceback.print_exc()
            else:
                print("[WARNING] export_step() not found")
            
            return True
            
        except ImportError as e:
            print(f"[ERROR] Import failed: {e}")
            
            # 检查缺少的DLL
            print("[INFO] Checking for required DLLs in build directory:")
            required_dlls = ['python313.dll', 'TKernel.dll', 'TKDESTEP.dll', 'TKSTEP.dll']
            
            for dll in required_dlls:
                dll_path = build_dir / dll
                if dll_path.exists():
                    print(f"    ✓ {dll}")
                else:
                    print(f"    ✗ {dll} (MISSING)")
            
            return False
            
        except Exception as e:
            print(f"[ERROR] Unexpected error: {e}")
            import traceback
            traceback.print_exc()
            return False
            
    finally:
        os.chdir(original_dir)

def check_blender_plugin_structure():
    """检查Blender插件结构"""
    print("\n" + "=" * 60)
    print("Checking Blender Plugin Structure")
    print("=" * 60)
    
    # 查找Blender插件目录
    blender_versions = ["4.2", "4.1", "4.0", "3.6", "3.5", "3.4", "3.3", "3.2", "3.1", "3.0"]
    
    plugin_dir = None
    for version in blender_versions:
        addons_dir = Path(os.path.expanduser(f"~\\AppData\\Roaming\\Blender Foundation\\Blender\\{version}\\scripts\\addons"))
        plugin_path = addons_dir / "step_exporter"
        if plugin_path.exists():
            plugin_dir = plugin_path
            break
    
    if not plugin_dir:
        print("[ERROR] Plugin not found in Blender addons directory")
        return False
    
    print(f"[INFO] Found plugin at: {plugin_dir}")
    
    # 检查文件结构
    print("\n[INFO] Plugin structure:")
    for root, dirs, files in os.walk(plugin_dir):
        level = root.replace(str(plugin_dir), '').count(os.sep)
        indent = ' ' * 2 * level
        print(f'{indent}{os.path.basename(root)}/')
        subindent = ' ' * 2 * (level + 1)
        for file in files:
            if file.endswith(('.py', '.pyd', '.dll')):
                print(f'{subindent}{file}')
    
    return True

def main():
    """主函数"""
    print("C++ Extension and Blender Plugin Diagnosis")
    
    all_ok = True
    
    # 诊断C++扩展
    if not diagnose_cpp_extension():
        all_ok = False
    
    # 检查Blender插件结构
    if not check_blender_plugin_structure():
        all_ok = False
    
    # 提供修复建议
    print("\n" + "=" * 60)
    print("DIAGNOSIS COMPLETE")
    print("=" * 60)
    
    if all_ok:
        print("[SUCCESS] All checks passed!")
    else:
        print("\n[RECOMMENDATIONS]")
        print("1. Ensure all required DLLs are in the same directory as step_exporter.pyd")
        print("2. Check that Python version matches (should be Python 3.11)")
        print("3. Verify the C++ extension was built with correct ABI (should be Release, x64)")
        print("4. Try copying the entire build directory to Blender plugin's lib directory")
        print("5. Make sure no other 'step_exporter' module is in Python's search path")
    
    return all_ok

if __name__ == "__main__":
    try:
        success = main()
        
        if success:
            sys.exit(0)
        else:
            sys.exit(1)
    except Exception as e:
        print(f"\n[ERROR] Diagnosis failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
