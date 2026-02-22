#!/usr/bin/env python3
"""
诊断脚本：检查_step_exporter模块导入问题
运行此脚本以确定为什么无法导入_step_exporter模块
"""

import sys
import os
import platform
import traceback

def print_section(title):
    """打印一个标题部分"""
    print("\n" + "=" * 60)
    print(f" {title}")
    print("=" * 60)

def find_module_file(module_name):
    """查找模块文件"""
    # 可能的扩展名
    extensions = ['.pyd', '.so', '.dll', '.py', '.pyc']
    # 可能的文件名变体
    filenames = [module_name, module_name + '_step_exporter', '_step_exporter']
    
    for path in sys.path:
        if not os.path.exists(path) or not os.path.isdir(path):
            continue
            
        for filename in filenames:
            for ext in extensions:
                full_path = os.path.join(path, filename + ext)
                if os.path.exists(full_path):
                    return full_path
                    
                # 对于包，检查__init__.py
                if ext == '.py':
                    init_path = os.path.join(path, filename, '__init__.py')
                    if os.path.exists(init_path):
                        return init_path
    return None

def main():
    print_section("STEP导出模块诊断工具")
    
    # 1. 系统信息
    print("1. 系统信息:")
    print(f"   操作系统: {platform.system()} {platform.release()}")
    print(f"   Python版本: {platform.python_version()}")
    print(f"   Python解释器: {sys.executable}")
    print(f"   工作目录: {os.getcwd()}")
    
    # 2. Python路径
    print_section("2. Python搜索路径 (sys.path)")
    for i, path in enumerate(sys.path):
        print(f"   [{i:3d}] {path}")
        if not os.path.exists(path):
            print(f"        ⚠ 路径不存在")
    
    # 3. 尝试查找模块文件
    print_section("3. 查找_step_exporter模块文件")
    module_path = find_module_file('_step_exporter')
    if module_path:
        print(f"   ✓ 找到模块文件: {module_path}")
        print(f"     文件大小: {os.path.getsize(module_path)} 字节")
        print(f"     修改时间: {os.path.getmtime(module_path)}")
        
        # 检查文件类型
        if module_path.endswith('.pyd'):
            print(f"     文件类型: Windows Python扩展模块 (.pyd)")
        elif module_path.endswith('.so'):
            print(f"     文件类型: Linux/POSIX共享库 (.so)")
        elif module_path.endswith('.dll'):
            print(f"     文件类型: 动态链接库 (.dll)")
        elif module_path.endswith('.py'):
            print(f"     文件类型: Python源文件 (.py)")
    else:
        print("   ✗ 未找到_step_exporter模块文件")
        print("   \n   可能的原因:")
        print("   1. 模块文件不在Python搜索路径中")
        print("   2. 模块文件名称不正确")
        print("   3. 模块文件不存在或未编译")
    
    # 4. 检查Blender相关路径
    print_section("4. 检查Blender相关路径")
    blender_paths = []
    
    # 常见Blender插件路径
    if platform.system() == "Windows":
        appdata = os.getenv('APPDATA', '')
        if appdata:
            blender_base = os.path.join(appdata, 'Blender Foundation', 'Blender')
            if os.path.exists(blender_base):
                for version in os.listdir(blender_base):
                    addon_path = os.path.join(blender_base, version, 'scripts', 'addons')
                    if os.path.exists(addon_path):
                        blender_paths.append(addon_path)
    
    # 检查当前脚本所在目录
    script_dir = os.path.dirname(os.path.abspath(__file__))
    blender_paths.append(script_dir)
    
    # 检查上级目录（假设插件在blender2step目录中）
    parent_dir = os.path.dirname(script_dir)
    blender_paths.append(parent_dir)
    
    for i, path in enumerate(blender_paths):
        print(f"   [{i}] {path}")
        if os.path.exists(path):
            # 查找该目录下的_step_exporter文件
            for root, dirs, files in os.walk(path):
                for file in files:
                    if '_step_exporter' in file and file.endswith(('.pyd', '.so', '.dll')):
                        print(f"      ✓ 找到: {os.path.join(root, file)}")
        else:
            print(f"      ⚠ 路径不存在")
    
    # 5. 尝试导入模块
    print_section("5. 尝试导入_step_exporter模块")
    print("   导入尝试中...")
    
    try:
        # 首先尝试直接导入
        import _step_exporter
        print("   ✓ 成功导入_step_exporter模块")
        print(f"      模块位置: {_step_exporter.__file__}")
        
        # 检查模块版本
        if hasattr(_step_exporter, 'get_version'):
            version = _step_exporter.get_version()
            print(f"      模块版本: {version}")
        else:
            print("      模块没有get_version函数")
            
        # 列出模块中的函数
        print(f"      模块函数: {[name for name in dir(_step_exporter) if not name.startswith('_')]}")
        
    except ImportError as e:
        print(f"   ✗ 导入失败: {e}")
        print("\n   详细错误信息:")
        traceback.print_exc()
        
        # 尝试从常见位置导入
        print("\n   尝试从特定路径导入:")
        test_paths = [
            script_dir,
            parent_dir,
            os.path.join(script_dir, 'lib'),
            os.path.join(parent_dir, 'lib'),
        ]
        
        for test_path in test_paths:
            if os.path.exists(test_path):
                print(f"\n   尝试添加路径: {test_path}")
                sys.path.insert(0, test_path)
                try:
                    import _step_exporter
                    print(f"      ✓ 从 {test_path} 导入成功")
                    print(f"         模块位置: {_step_exporter.__file__}")
                    break
                except ImportError:
                    sys.path.remove(test_path)
                    print(f"      ✗ 从 {test_path} 导入失败")
    
    # 6. 检查环境变量
    print_section("6. 环境变量检查")
    env_vars = ['PATH', 'PYTHONPATH', 'BLENDER_USER_SCRIPTS']
    for var in env_vars:
        value = os.getenv(var)
        if value:
            print(f"   {var}: {value}")
        else:
            print(f"   {var}: 未设置")
    
    # 7. 建议
    print_section("7. 诊断建议")
    
    if not module_path:
        print("""
   问题: 未找到_step_exporter模块文件
    
   解决方案:
   1. 确保已成功编译C++扩展模块
      - 检查编译输出是否有错误
      - 确认生成了_step_exporter.pyd文件
   
   2. 将模块文件复制到正确位置
      - 复制_step_exporter.pyd到Blender的插件目录
      - 常见位置: C:\\Users\\<用户名>\\AppData\\Roaming\\Blender Foundation\\Blender\\<版本>\\scripts\\addons\\blender2step\\
   
   3. 确保Python可以找到模块
      - 将模块所在目录添加到sys.path
      - 或设置PYTHONPATH环境变量
   
   4. 检查模块文件完整性
      - 确认_step_exporter.pyd文件完整
      - 重新编译并复制文件
        """)
    else:
        print("""
   模块文件已找到，但导入失败。
   
   可能的原因:
   1. 模块依赖的DLL文件缺失
      - 确保OpenCASCADE 7.7.2的DLL文件在相同目录或系统PATH中
   
   2. Python版本不匹配
      - 编译模块的Python版本与运行的Python版本不一致
   
   3. 模块文件损坏
      - 尝试重新编译模块
   
   4. 32位/64位不匹配
      - 确保Python、Blender和模块都是相同架构(32位或64位)
        """)
    
    print_section("诊断完成")

if __name__ == "__main__":
    main()
