"""
诊断C++扩展导入问题
在Blender文本编辑器中运行此脚本
"""

import sys
import os
import traceback
import importlib.util

print("=" * 60)
print("C++ Extension Import Diagnosis")
print("=" * 60)

# 获取插件目录
plugin_dir = os.path.dirname(__file__)
lib_dir = os.path.join(plugin_dir, "lib")

print(f"Plugin directory: {plugin_dir}")
print(f"Library directory: {lib_dir}")

# 查找.pyd文件
pyd_files = [f for f in os.listdir(lib_dir) if f.lower().endswith('.pyd')]
print(f"\nFound {len(pyd_files)} .pyd files:")
for pyd in pyd_files:
    pyd_path = os.path.join(lib_dir, pyd)
    print(f"  - {pyd} ({os.path.getsize(pyd_path):,} bytes)")

if not pyd_files:
    print("[ERROR] No .pyd files found")
    sys.exit(1)

# 设置DLL搜索路径
os.environ['PATH'] = lib_dir + ';' + os.environ.get('PATH', '')

# 方法1: 尝试标准导入
print("\n1. Trying standard import...")
try:
    # 临时从sys.path中移除当前目录
    original_sys_path = sys.path.copy()
    if lib_dir in sys.path:
        sys.path.remove(lib_dir)
    if plugin_dir in sys.path:
        sys.path.remove(plugin_dir)
    
    # 添加lib目录
    sys.path.insert(0, lib_dir)
    
    # 尝试导入
    for pyd in pyd_files:
        module_name = os.path.splitext(pyd)[0]
        print(f"  Trying to import: {module_name}")
        
        try:
            module = __import__(module_name)
            print(f"    [SUCCESS] Imported: {module}")
            print(f"    Module attributes: {[a for a in dir(module) if not a.startswith('_')]}")
            
            if hasattr(module, 'export_step'):
                print(f"    ✓ Found export_step")
            if hasattr(module, 'get_version'):
                print(f"    ✓ Found get_version")
                try:
                    version = module.get_version()
                    print(f"      Version: {version}")
                except:
                    pass
                    
        except ImportError as e:
            print(f"    [ERROR] Import failed: {e}")
    
    sys.path = original_sys_path
    
except Exception as e:
    print(f"[ERROR] Standard import test failed: {e}")
    traceback.print_exc()

# 方法2: 使用importlib
print("\n2. Trying importlib...")
for pyd in pyd_files:
    pyd_path = os.path.join(lib_dir, pyd)
    print(f"  Loading: {pyd}")
    
    try:
        # 为模块创建一个唯一的名称
        unique_name = f"_diagnostic_{os.path.splitext(pyd)[0]}"
        
        spec = importlib.util.spec_from_file_location(unique_name, pyd_path)
        if spec is None:
            print(f"    [ERROR] Could not create spec from {pyd}")
            continue
        
        module = importlib.util.module_from_spec(spec)
        sys.modules[unique_name] = module
        
        # 执行模块
        spec.loader.exec_module(module)
        
        print(f"    [SUCCESS] Module loaded via importlib")
        print(f"    Attributes: {[a for a in dir(module) if not a.startswith('_')]}")
        
        # 测试函数
        if hasattr(module, 'export_step'):
            print(f"    ✓ export_step function found")
            
            # 尝试调用
            import tempfile
            test_file = os.path.join(tempfile.gettempdir(), 'test_diag.step')
            print(f"    Testing export to: {test_file}")
            
            try:
                result = module.export_step(test_file)
                print(f"    Export result: {result}")
                
                if result and os.path.exists(test_file):
                    print(f"    [SUCCESS] File created: {test_file}")
                    os.remove(test_file)
            except Exception as e:
                print(f"    [ERROR] Export test failed: {e}")
        
        if hasattr(module, 'get_version'):
            print(f"    ✓ get_version function found")
            try:
                version = module.get_version()
                print(f"      Version: {version}")
            except Exception as e:
                print(f"    [ERROR] Could not get version: {e}")
                
    except Exception as e:
        print(f"    [ERROR] importlib loading failed: {e}")
        traceback.print_exc()

print("\n" + "=" * 60)
print("Diagnosis complete")
print("=" * 60)
