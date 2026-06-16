"""
VSCode Blender 插件开发测试脚本
在Blender中运行此脚本以验证插件设置
"""

import bpy
import sys
import os
import traceback

print("=" * 60)
print("VSCode Blender 插件开发测试")
print("=" * 60)

# 1. 检查插件目录
print("\n1. 检查插件目录...")
plugin_dir = os.path.dirname(__file__)
print(f"   插件目录: {plugin_dir}")

lib_dir = os.path.join(plugin_dir, "lib")
if os.path.exists(lib_dir):
    print(f"   [OK] lib目录存在: {lib_dir}")
    
    # 列出文件
    pyd_files = [f for f in os.listdir(lib_dir) if f.lower().endswith('.pyd')]
    dll_files = [f for f in os.listdir(lib_dir) if f.lower().endswith('.dll')]
    
    print(f"   找到 {len(pyd_files)} 个.pyd文件, {len(dll_files)} 个DLL文件")
    
    if pyd_files:
        print("   .pyd文件:")
        for pyd in pyd_files:
            print(f"     - {pyd}")
    else:
        print("   [ERROR] 未找到.pyd文件")
else:
    print(f"   [ERROR] lib目录不存在: {lib_dir}")

# 2. 测试C++扩展加载
print("\n2. 测试C++扩展加载...")

# 设置DLL搜索路径
os.environ['PATH'] = lib_dir + ';' + os.environ.get('PATH', '')

# 添加lib目录到Python路径
if lib_dir not in sys.path:
    sys.path.insert(0, lib_dir)

if pyd_files:
    pyd_name = os.path.splitext(pyd_files[0])[0]
    print(f"   尝试导入: {pyd_name}")
    
    try:
        module = __import__(pyd_name)
        print(f"   [SUCCESS] 导入成功: {pyd_name}")
        
        # 检查函数
        functions = [f for f in dir(module) if not f.startswith('_')]
        print(f"   可用函数: {functions}")
        
        if hasattr(module, 'get_version'):
            try:
                version = module.get_version()
                print(f"   版本: {version}")
            except Exception as e:
                print(f"   获取版本失败: {e}")
        
        if hasattr(module, 'export_step'):
            print("   [OK] export_step函数存在")
        else:
            print("   [ERROR] export_step函数不存在")
            
    except ImportError as e:
        print(f"   [ERROR] 导入失败: {e}")
        print("   [DEBUG] sys.path:")
        for i, path in enumerate(sys.path[:5]):
            print(f"     {i}: {path}")
    except Exception as e:
        print(f"   [ERROR] 意外错误: {e}")
        traceback.print_exc()
else:
    print("   [SKIP] 无.pyd文件，跳过导入测试")

# 3. 检查Blender插件状态
print("\n3. 检查Blender插件状态...")

# 检查插件是否注册
if hasattr(bpy.types, 'STEP_EXPORTER_OT_export'):
    print("   [OK] STEP导出器操作符已注册")
else:
    print("   [WARNING] STEP导出器操作符未注册")

# 检查菜单
print("\n4. 测试菜单...")
print("   请在文件菜单中检查是否有'导出 > STEP (.step)'选项")

print("\n" + "=" * 60)
print("测试完成!")
print("=" * 60)
