"""
C++扩展诊断工具
在Blender文本编辑器中运行此脚本
"""

import sys
import os
import traceback
import importlib.util
import tempfile

print("=" * 60)
print("C++扩展诊断工具")
print("=" * 60)

# 获取当前脚本的绝对路径
current_file = os.path.abspath(__file__)
print(f"当前脚本: {current_file}")

# 尝试解析符号链接
if hasattr(os.path, 'readlink'):
    try:
        real_current_file = os.path.realpath(current_file)
        if real_current_file != current_file:
            print(f"脚本实际路径: {real_current_file}")
            current_file = real_current_file
    except:
        pass

# 计算插件目录
def find_plugin_dir():
    """查找插件目录"""
    # 方法1: 从典型位置查找
    typical_locations = [
        os.path.join(os.environ.get('APPDATA', ''), 'Blender Foundation', 'Blender', '4.2', 'scripts', 'addons', 'step_exporter'),
        os.path.join(os.environ.get('APPDATA', ''), 'Blender Foundation', 'Blender', '4.1', 'scripts', 'addons', 'step_exporter'),
        os.path.join(os.environ.get('APPDATA', ''), 'Blender Foundation', 'Blender', '4.0', 'scripts', 'addons', 'step_exporter'),
        os.path.join(os.environ.get('APPDATA', ''), 'Blender Foundation', 'Blender', '3.6', 'scripts', 'addons', 'step_exporter'),
    ]
    
    for location in typical_locations:
        if os.path.exists(location):
            init_file = os.path.join(location, "__init__.py")
            lib_dir = os.path.join(location, "lib")
            
            if os.path.exists(init_file) and os.path.exists(lib_dir):
                print(f"在典型位置找到插件目录: {location}")
                return location
    
    # 方法2: 从当前脚本所在目录向上查找
    current_dir = os.path.dirname(current_file)
    max_depth = 5
    depth = 0
    
    while current_dir and depth < max_depth:
        init_file = os.path.join(current_dir, "__init__.py")
        lib_dir = os.path.join(current_dir, "lib")
        
        if os.path.exists(init_file) and os.path.exists(lib_dir):
            print(f"在父目录中找到插件目录: {current_dir}")
            return current_dir
        
        parent_dir = os.path.dirname(current_dir)
        if parent_dir == current_dir:
            break
            
        current_dir = parent_dir
        depth += 1
    
    # 方法3: 尝试项目目录
    project_dir = r"F:\git\blender2step\step_exporter"
    if os.path.exists(project_dir):
        print(f"使用项目目录: {project_dir}")
        return project_dir
    
    return None

# 查找插件目录
plugin_dir = find_plugin_dir()

if plugin_dir is None:
    print("[ERROR] 无法找到插件目录")
    sys.exit(1)

print(f"\n使用的插件目录: {plugin_dir}")
lib_dir = os.path.join(plugin_dir, "lib")
print(f"库目录: {lib_dir}")

# 检查lib目录是否存在
if not os.path.exists(lib_dir):
    print(f"[ERROR] lib目录不存在: {lib_dir}")
    sys.exit(1)

# 查找.pyd文件
pyd_files = [f for f in os.listdir(lib_dir) if f.lower().endswith('.pyd')]
if not pyd_files:
    print("[ERROR] 未找到.pyd文件")
    sys.exit(1)

pyd_file = pyd_files[0]
pyd_path = os.path.join(lib_dir, pyd_file)

print(f"\n找到C++扩展: {pyd_file}")
print(f"完整路径: {pyd_path}")
print(f"文件大小: {os.path.getsize(pyd_path):,} 字节")

# 设置DLL搜索路径
original_path = os.environ.get('PATH', '')
os.environ['PATH'] = lib_dir + ';' + original_path
print(f"已设置DLL搜索路径: {lib_dir}")

# 尝试加载C++扩展
print("\n尝试加载C++扩展...")

# 保存原始sys.path
original_sys_path = sys.path.copy()

# 添加lib目录到sys.path
if lib_dir not in sys.path:
    sys.path.insert(0, lib_dir)

# 尝试模块名
module_name = "step_exporter"
print(f"尝试模块名: {module_name}")

try:
    # 从sys.modules中移除可能的冲突
    if module_name in sys.modules:
        del sys.modules[module_name]
    
    # 使用importlib加载
    spec = importlib.util.spec_from_file_location(module_name, pyd_path)
    if spec is None:
        print(f"  [ERROR] 无法创建规范")
        sys.exit(1)
    
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    
    # 执行模块
    spec.loader.exec_module(module)
    
    print(f"  [SUCCESS] 加载成功!")
    print(f"  模块类型: {type(module)}")
    
    # 列出所有属性
    attrs = [attr for attr in dir(module) if not attr.startswith('_')]
    print(f"  可用属性 ({len(attrs)}个): {attrs}")
    
    # 检查关键函数
    export_step_found = hasattr(module, 'export_step')
    get_version_found = hasattr(module, 'get_version')
    
    if export_step_found:
        print(f"  ✓ export_step函数存在")
    else:
        print(f"  ✗ export_step函数不存在")
    
    if get_version_found:
        print(f"  ✓ get_version函数存在")
    else:
        print(f"  ✗ get_version函数不存在")
    
    # 测试导出功能
    if export_step_found:
        test_file = os.path.join(tempfile.gettempdir(), 'diagnose_test.step')
        print(f"  测试导出到: {test_file}")
        
        try:
            result = module.export_step(test_file)
            print(f"  导出结果: {result}")
            
            if os.path.exists(test_file):
                size = os.path.getsize(test_file)
                print(f"  文件大小: {size:,} 字节")
                
                # 验证内容
                with open(test_file, 'rb') as f:
                    header = f.read(100)
                    if b'ISO-10303-21' in header or b'STEP' in header.upper():
                        print(f"  ✓ 有效的STEP文件")
                    else:
                        print(f"  ⚠️ 文件格式不是标准STEP")
                
                # 清理
                os.remove(test_file)
            else:
                print(f"  ⚠️ 文件未创建")
        except Exception as e:
            print(f"  [ERROR] 导出测试失败: {e}")
            traceback.print_exc()
    
    # 获取版本信息
    if get_version_found:
        try:
            version = module.get_version()
            print(f"  版本: {version}")
        except Exception as e:
            print(f"  [ERROR] 获取版本失败: {e}")
    
    print(f"\n  [INFO] 找到完全兼容的模块: {module_name}")
    
except ImportError as e:
    print(f"  [ERROR] 导入失败: {e}")
    sys.exit(1)
except Exception as e:
    print(f"  [ERROR] 加载错误: {e}")
    traceback.print_exc()
    sys.exit(1)
finally:
    # 恢复原始sys.path
    sys.path = original_sys_path

print("\n" + "=" * 60)
print("诊断摘要")
print("=" * 60)

print(f"[SUCCESS] 找到可用的C++扩展模块")
print(f"  模块名: {module_name}")
print(f"  导出函数: {'✓' if export_step_found else '✗'}")
print(f"  版本函数: {'✓' if get_version_found else '✗'}")

# 测试最终导出
print(f"\n[INFO] 执行最终测试...")
test_file = os.path.join(tempfile.gettempdir(), 'final_test.step')
print(f"  导出文件: {test_file}")

try:
    result = module.export_step(test_file)
    if result and os.path.exists(test_file):
        size = os.path.getsize(test_file)
        print(f"  [SUCCESS] 导出成功! 文件大小: {size:,} 字节")
        os.remove(test_file)
    else:
        print(f"  [WARNING] 导出可能失败")
except Exception as e:
    print(f"  [ERROR] 最终测试失败: {e}")

print("\n" + "=" * 60)
print("诊断完成")
print("=" * 60)
