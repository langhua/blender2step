import os
import sys
import traceback
import tempfile
from pathlib import Path

def find_plugin_directory():
    """查找插件目录"""
    project_dir = Path(__file__).parent.parent
    
    # 所有可能的构建目录
    possible_dirs = [
        project_dir / "out" / "build" / "x64-Release",
        project_dir / "out" / "build" / "x64-RelWithDebInfo",
        project_dir / "out" / "build" / "x64-Debug",
        project_dir / "build" / "Release",
        project_dir / "build2" / "Release",
        project_dir / "build2" / "RelWithDebInfo",
        project_dir / "step_exporter" / "lib",
        project_dir,  # 当前目录
    ]
    
    for dir_path in possible_dirs:
        if dir_path.exists():
            pyd_files = list(dir_path.glob("*.pyd"))
            if pyd_files:
                return dir_path
    
    return None

def test_plugin():
    """测试插件"""
    print("=" * 60)
    print("STEP Exporter Plugin Test")
    print("=" * 60)
    
    # 查找插件目录
    plugin_dir = find_plugin_directory()
    
    if not plugin_dir:
        print("[ERROR] No plugin directory found")
        print("\nPlease build the project first, or ensure plugin is in one of:")
        print("  - out/build/x64-Release/")
        print("  - out/build/x64-RelWithDebInfo/")
        print("  - out/build/x64-Debug/")
        print("  - build/Release/")
        print("  - build2/Release/")
        print("  - build2/RelWithDebInfo/")
        print("  - step_exporter/lib/")
        print("  - current directory/")
        return False
    
    print(f"[INFO] Found plugin directory: {plugin_dir}")
    
    # 切换到插件目录
    original_dir = os.getcwd()
    os.chdir(plugin_dir)
    
    try:
        # 设置 DLL 搜索路径
        try:
            os.add_dll_directory(str(plugin_dir))
            print("[INFO] Added directory to DLL search path")
        except:
            print("[INFO] Using PATH for DLL search")
        
        os.environ['PATH'] = str(plugin_dir) + ';' + os.environ.get('PATH', '')
        sys.path.insert(0, str(plugin_dir))
        
        # 查找插件文件
        pyd_files = [f for f in os.listdir('.') if f.lower().endswith('.pyd')]
        if not pyd_files:
            print("[ERROR] No .pyd files in directory")
            return False
        
        plugin_file = pyd_files[0]
        plugin_name = os.path.splitext(plugin_file)[0]
        
        print(f"[INFO] Plugin file: {plugin_file}")
        print(f"[INFO] Module name: {plugin_name}")
        
        # 导入插件
        print("\n" + "-" * 40)
        print("Importing plugin...")
        try:
            plugin_module = __import__(plugin_name)
            print("[SUCCESS] Plugin imported successfully")
        except ImportError as e:
            print(f"[ERROR] Import failed: {e}")
            print("\nDebug information:")
            traceback.print_exc()
            return False
        
        # 测试版本函数
        print("\n" + "-" * 40)
        print("Testing version function...")
        if hasattr(plugin_module, 'get_version'):
            try:
                version = plugin_module.get_version()
                print(f"[SUCCESS] Version: {version}")
            except Exception as e:
                print(f"[ERROR] Failed to get version: {e}")
                traceback.print_exc()
        else:
            print("[ERROR] get_version() function not found")
        
        # 测试导出函数
        print("\n" + "-" * 40)
        print("Testing export function...")
        if hasattr(plugin_module, 'export_step'):
            # 使用临时文件
            with tempfile.NamedTemporaryFile(suffix='.step', delete=False) as tmp:
                test_file = tmp.name
            
            print(f"[INFO] Testing export to: {test_file}")
            
            try:
                result = plugin_module.export_step(test_file)
                print(f"[INFO] Export result: {result}")
                
                if result and os.path.exists(test_file):
                    size = os.path.getsize(test_file)
                    print(f"[SUCCESS] Export successful! File size: {size:,} bytes")
                    
                    # 验证文件内容
                    with open(test_file, 'rb') as f:
                        first_bytes = f.read(100)
                        
                        if b'ISO-10303-21' in first_bytes or b'STEP' in first_bytes.upper():
                            print("[SUCCESS] Valid STEP file format detected")
                            
                            # 显示文件开头
                            print("\nFile header (ASCII):")
                            ascii_part = ''.join(chr(b) if 32 <= b < 127 else '.' for b in first_bytes)
                            print(f"  {ascii_part}")
                            
                            # 显示更多信息
                            if size > 100:
                                with open(test_file, 'r', encoding='utf-8', errors='ignore') as f:
                                    lines = []
                                    for _ in range(5):
                                        line = f.readline()
                                        if not line:
                                            break
                                        lines.append(line.strip())
                                    
                                    if lines:
                                        print("\nFirst 5 lines:")
                                        for i, line in enumerate(lines, 1):
                                            print(f"  {i}: {line}")
                        else:
                            print("[WARNING] Unknown file format")
                            print(f"  Hex header: {first_bytes[:20].hex()}")
                else:
                    print("[ERROR] Export failed or file not created")
                    
            except Exception as e:
                print(f"[ERROR] Export error: {e}")
                traceback.print_exc()
            
            # 清理临时文件
            try:
                if os.path.exists(test_file):
                    os.unlink(test_file)
            except:
                pass
        else:
            print("[ERROR] export_step() function not found")
        
        # 列出所有可用的函数
        print("\n" + "-" * 40)
        print("Available functions in plugin:")
        functions = [f for f in dir(plugin_module) if not f.startswith('_')]
        if functions:
            for func in sorted(functions):
                print(f"  - {func}")
        else:
            print("  (No public functions found)")
        
        return True
        
    finally:
        # 恢复原始目录
        os.chdir(original_dir)

if __name__ == "__main__":
    print("STEP Exporter Plugin Tester")
    print("=" * 60)
    
    try:
        success = test_plugin()
        
        print("\n" + "=" * 60)
        if success:
            print("[SUCCESS] Plugin test completed successfully!")
            sys.exit(0)
        else:
            print("[FAILURE] Plugin test failed")
            sys.exit(1)
            
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n[ERROR] Unexpected error: {e}")
        traceback.print_exc()
        sys.exit(1)
