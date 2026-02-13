#!/usr/bin/env python3
"""
修复STEP导出器插件加载问题
"""

import os
import sys
import shutil
import subprocess
from pathlib import Path

def fix_plugin_loading():
    """修复插件加载问题"""
    project_dir = Path(__file__).parent.parent
    
    print("=" * 60)
    print("修复STEP导出器插件加载问题")
    print("=" * 60)
    
    # 1. 检查插件目录
    print("\n1. 检查插件目录...")
    plugin_dir = project_dir / "step_exporter"
    
    if not plugin_dir.exists():
        print(f"[ERROR] 插件目录未找到: {plugin_dir}")
        return False
    
    print(f"[OK] 插件目录: {plugin_dir}")
    
    lib_dir = plugin_dir / "lib"
    if not lib_dir.exists():
        print(f"[ERROR] lib目录未找到: {lib_dir}")
        return False
    
    print(f"[OK] lib目录: {lib_dir}")
    
    # 2. 检查C++扩展文件
    print("\n2. 检查C++扩展文件...")
    pyd_files = list(lib_dir.glob("*.pyd"))
    
    if not pyd_files:
        print("[ERROR] 未找到.pyd文件")
        return False
    
    pyd_file = pyd_files[0]
    print(f"[OK] 找到C++扩展: {pyd_file.name}")
    print(f"    大小: {pyd_file.stat().st_size:,} 字节")
    
    # 3. 测试C++扩展加载
    print("\n3. 测试C++扩展加载...")
    
    # 保存当前状态
    original_cwd = os.getcwd()
    original_path = os.environ.get('PATH', '')
    original_sys_path = sys.path.copy()
    
    try:
        # 切换到lib目录
        os.chdir(lib_dir)
        
        # 设置DLL搜索路径
        os.environ['PATH'] = str(lib_dir) + ';' + original_path
        
        # 添加lib目录到Python路径
        if str(lib_dir) not in sys.path:
            sys.path.insert(0, str(lib_dir))
        
        # 尝试直接导入
        pyd_name = pyd_file.stem
        print(f"尝试导入模块: {pyd_name}")
        
        try:
            import importlib.util
            
            # 使用importlib直接加载
            spec = importlib.util.spec_from_file_location("_test_module", str(pyd_file))
            if spec is None:
                print("[ERROR] 无法创建模块规范")
                return False
            
            module = importlib.util.module_from_spec(spec)
            sys.modules["_test_module"] = module
            
            # 执行模块
            spec.loader.exec_module(module)
            
            print("[SUCCESS] C++扩展加载成功")
            
            # 检查函数
            functions = [f for f in dir(module) if not f.startswith('_')]
            print(f"可用函数: {functions}")
            
            if hasattr(module, 'export_step'):
                print("[OK] ✓ 找到 export_step 函数")
            else:
                print("[ERROR] ✗ 未找到 export_step 函数")
                
            if hasattr(module, 'get_version'):
                print("[OK] ✓ 找到 get_version 函数")
                try:
                    version = module.get_version()
                    print(f"    版本: {version}")
                except Exception as e:
                    print(f"    获取版本失败: {e}")
            else:
                print("[ERROR] ✗ 未找到 get_version 函数")
            
            return True
            
        except ImportError as e:
            print(f"[ERROR] 导入失败: {e}")
            return False
        except Exception as e:
            print(f"[ERROR] 意外错误: {e}")
            import traceback
            traceback.print_exc()
            return False
            
    finally:
        # 恢复原始状态
        os.chdir(original_cwd)
        os.environ['PATH'] = original_path
        sys.path = original_sys_path

def create_fixed_plugin():
    """创建修复后的插件文件"""
    project_dir = Path(__file__).parent.parent
    plugin_dir = project_dir / "step_exporter"
    
    print("\n4. 创建修复后的插件文件...")
    
    # 备份原文件
    init_file = plugin_dir / "__init__.py"
    if init_file.exists():
        backup_file = plugin_dir / "__init__.py.backup"
        shutil.copy2(init_file, backup_file)
        print(f"[INFO] 已备份原文件: {backup_file}")
    
    # 创建修复后的插件文件
    fixed_content = '''"""
STEP Exporter for Blender
Export 3D models to STEP format using OpenCASCADE
"""

bl_info = {
    "name": "STEP Exporter",
    "author": "Your Name",
    "version": (1, 0, 0),
    "blender": (2, 80, 0),
    "location": "File > Export > STEP",
    "description": "Export 3D models to STEP format",
    "category": "Import-Export",
}

import bpy
import sys
import os
import traceback
import importlib.util
from bpy_extras.io_utils import ExportHelper
from bpy.props import StringProperty, BoolProperty, FloatProperty
from bpy.types import Operator, Panel

# 全局变量存储C++扩展模块
_cpp_module = None
_cpp_module_loaded = False
_cpp_module_error = None

def load_cpp_module_safe():
    """安全加载C++扩展模块"""
    global _cpp_module, _cpp_module_loaded, _cpp_module_error
    
    if _cpp_module_loaded:
        return _cpp_module
    
    if _cpp_module_error is not None:
        return None
    
    # 获取插件目录
    plugin_dir = os.path.dirname(__file__)
    lib_dir = os.path.join(plugin_dir, "lib")
    
    if not os.path.exists(lib_dir):
        _cpp_module_error = f"lib目录未找到: {lib_dir}"
        print(f"[STEP EXPORTER ERROR] {_cpp_module_error}")
        return None
    
    # 设置DLL搜索路径
    original_path = os.environ.get('PATH', '')
    os.environ['PATH'] = lib_dir + ';' + original_path
    
    # 查找.pyd文件
    pyd_files = [f for f in os.listdir(lib_dir) if f.lower().endswith('.pyd')]
    if not pyd_files:
        _cpp_module_error = f"在 {lib_dir} 中未找到.pyd文件"
        print(f"[STEP EXPORTER ERROR] {_cpp_module_error}")
        return None
    
    pyd_file = pyd_files[0]
    pyd_path = os.path.join(lib_dir, pyd_file)
    
    print(f"[STEP EXPORTER] 找到C++扩展: {pyd_file}")
    print(f"[STEP EXPORTER] 路径: {pyd_path}")
    
    # 尝试不同的模块名
    possible_names = [
        "step_exporter",  # 原始名称
        "_step_exporter",  # 带下划线的名称
        "step_exporter_cpp",  # 带_cpp后缀
        "_step_cpp_ext",  # 之前尝试的名称
        "step_cpp_module",  # 新尝试
    ]
    
    for module_name in possible_names:
        print(f"[STEP EXPORTER] 尝试模块名: {module_name}")
        
        try:
            # 保存原始sys.path
            original_sys_path = sys.path.copy()
            
            # 添加lib目录到sys.path
            if lib_dir not in sys.path:
                sys.path.insert(0, lib_dir)
            
            # 从sys.modules中移除可能的冲突模块
            if module_name in sys.modules:
                del sys.modules[module_name]
            
            # 使用importlib加载
            spec = importlib.util.spec_from_file_location(module_name, pyd_path)
            if spec is None:
                print(f"[STEP EXPORTER] 无法为 {module_name} 创建规范")
                continue
            
            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module
            
            # 执行模块
            spec.loader.exec_module(module)
            
            print(f"[STEP EXPORTER] ✓ 使用模块名 {module_name} 加载成功")
            
            # 验证函数
            if hasattr(module, 'export_step'):
                print("[STEP EXPORTER] ✓ 找到 export_step 函数")
            else:
                print("[STEP EXPORTER] ✗ 未找到 export_step 函数")
                continue
                
            if hasattr(module, 'get_version'):
                print("[STEP EXPORTER] ✓ 找到 get_version 函数")
            else:
                print("[STEP EXPORTER] ✗ 未找到 get_version 函数")
            
            _cpp_module = module
            _cpp_module_loaded = True
            
            return _cpp_module
            
        except ImportError as e:
            print(f"[STEP EXPORTER] 模块名 {module_name} 导入失败: {e}")
        except Exception as e:
            print(f"[STEP EXPORTER] 模块名 {module_name} 加载错误: {e}")
            traceback.print_exc()
        finally:
            # 恢复原始sys.path
            sys.path = original_sys_path
    
    # 如果所有尝试都失败
    _cpp_module_error = "所有模块名尝试都失败"
    print(f"[STEP EXPORTER ERROR] {_cpp_module_error}")
    return None

def get_cpp_module():
    """获取C++扩展模块"""
    return load_cpp_module_safe()

class STEP_EXPORTER_OT_export(Operator, ExportHelper):
    """导出到STEP格式"""
    bl_idname = "export.step"
    bl_label = "导出 STEP"
    
    filename_ext = ".step"
    
    filter_glob: StringProperty(
        default="*.step;*.stp",
        options={'HIDDEN'},
    )
    
    use_selected: BoolProperty(
        name="仅导出选中对象",
        description="仅导出选中的对象",
        default=False,
    )
    
    scale: FloatProperty(
        name="缩放比例",
        description="导出缩放比例",
        default=1.0,
        min=0.001,
        max=1000.0,
    )
    
    def draw(self, context):
        """绘制操作符界面"""
        layout = self.layout
        
        # 显示插件状态
        box = layout.box()
        box.label(text="STEP导出器状态", icon='INFO')
        
        cpp_module = get_cpp_module()
        if cpp_module:
            box.label(text="✓ C++扩展已加载", icon='CHECKMARK')
            
            # 显示版本信息
            if hasattr(cpp_module, 'get_version'):
                try:
                    version = cpp_module.get_version()
                    box.label(text=f"版本: {version}")
                except:
                    box.label(text="版本: 未知")
        else:
            box.label(text="✗ C++扩展不可用", icon='ERROR')
            if _cpp_module_error:
                box.label(text=f"错误: {_cpp_module_error[:50]}...", icon='CANCEL')
        
        # 导出设置
        box = layout.box()
        box.label(text="导出设置", icon='SETTINGS')
        box.prop(self, "use_selected")
        box.prop(self, "scale")
    
    def execute(self, context):
        """执行导出操作"""
        # 获取C++扩展模块
        cpp_module = get_cpp_module()
        
        if cpp_module is None:
            self.report({'ERROR'}, "无法加载STEP导出器C++扩展")
            if _cpp_module_error:
                self.report({'ERROR'}, f"错误: {_cpp_module_error}")
            return {'CANCELLED'}
        
        if not hasattr(cpp_module, 'export_step'):
            self.report({'ERROR'}, "C++扩展缺少export_step函数")
            return {'CANCELLED'}
        
        # 导出文件
        try:
            result = cpp_module.export_step(self.filepath)
            if result:
                self.report({'INFO'}, f"成功导出到 {self.filepath}")
                return {'FINISHED'}
            else:
                self.report({'ERROR'}, "导出失败 - 请查看控制台获取详情")
                return {'CANCELLED'}
        except Exception as e:
            self.report({'ERROR'}, f"导出错误: {str(e)[:100]}")
            print(f"[STEP EXPORTER ERROR] 导出异常: {e}")
            traceback.print_exc()
            return {'CANCELLED'}

def menu_func_export(self, context):
    """在导出菜单中添加STEP导出项"""
    self.layout.operator(STEP_EXPORTER_OT_export.bl_idname, text="STEP (.step)")

def register():
    """注册插件"""
    bpy.utils.register_class(STEP_EXPORTER_OT_export)
    bpy.types.TOPBAR_MT_file_export.append(menu_func_export)
    
    # 预加载C++扩展
    cpp_module = get_cpp_module()
    if cpp_module:
        print("[STEP EXPORTER] 插件注册成功")
    else:
        print("[STEP EXPORTER WARNING] 插件已注册，但C++扩展未加载")

def unregister():
    """注销插件"""
    bpy.utils.unregister_class(STEP_EXPORTER_OT_export)
    bpy.types.TOPBAR_MT_file_export.remove(menu_func_export)
    
    # 清理C++扩展引用
    global _cpp_module, _cpp_module_loaded, _cpp_module_error
    _cpp_module = None
    _cpp_module_loaded = False
    _cpp_module_error = None
    print("[STEP EXPORTER] 插件已注销")

if __name__ == "__main__":
    register()
'''
    
    with open(init_file, 'w', encoding='utf-8') as f:
        f.write(fixed_content)
    
    print(f"[SUCCESS] 创建修复后的插件文件: {init_file}")
    
    # 5. 创建诊断工具
    print("\n5. 创建诊断工具...")
    
    diag_script = plugin_dir / "diagnose_cpp_ext.py"
    diag_content = '''"""
诊断C++扩展问题
在Blender文本编辑器中运行此脚本
"""

import sys
import os
import traceback
import importlib.util

print("=" * 60)
print("C++扩展诊断工具")
print("=" * 60)

# 获取插件目录
plugin_dir = os.path.dirname(__file__)
lib_dir = os.path.join(plugin_dir, "lib")

print(f"插件目录: {plugin_dir}")
print(f"库目录: {lib_dir}")

# 查找.pyd文件
pyd_files = [f for f in os.listdir(lib_dir) if f.lower().endswith('.pyd')]
if not pyd_files:
    print("[ERROR] 未找到.pyd文件")
    sys.exit(1)

pyd_file = pyd_files[0]
pyd_path = os.path.join(lib_dir, pyd_file)

print(f"\\n找到C++扩展: {pyd_file}")
print(f"完整路径: {pyd_path}")

# 设置DLL搜索路径
os.environ['PATH'] = lib_dir + ';' + os.environ.get('PATH', '')

# 尝试不同的初始化函数名
print("\\n尝试不同的初始化函数名...")

# 保存原始sys.path
original_sys_path = sys.path.copy()

# 添加lib目录到sys.path
if lib_dir not in sys.path:
    sys.path.insert(0, lib_dir)

# 可能的模块名列表
possible_names = [
    "step_exporter",      # 原始名称
    "_step_exporter",     # 带下划线
    "step_exporter_cpp",  # 带_cpp后缀
    "_step_cpp_ext",      # 之前尝试的名称
    "step_cpp_module",    # 新尝试
    "_cpp_module",        # 简化
    "step_export_cpp",    # 变体
]

for module_name in possible_names:
    print(f"\\n尝试模块名: {module_name}")
    
    try:
        # 从sys.modules中移除可能的冲突
        if module_name in sys.modules:
            del sys.modules[module_name]
        
        # 使用importlib加载
        spec = importlib.util.spec_from_file_location(module_name, pyd_path)
        if spec is None:
            print(f"  [ERROR] 无法创建规范")
            continue
        
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
        if hasattr(module, 'export_step'):
            print(f"  ✓ export_step函数存在")
            
            # 测试导出
            import tempfile
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
                    
                    # 清理
                    os.remove(test_file)
            except Exception as e:
                print(f"  [ERROR] 导出测试失败: {e}")
        else:
            print(f"  ✗ export_step函数不存在")
        
        if hasattr(module, 'get_version'):
            print(f"  ✓ get_version函数存在")
            try:
                version = module.get_version()
                print(f"  版本: {version}")
            except Exception as e:
                print(f"  [ERROR] 获取版本失败: {e}")
        else:
            print(f"  ✗ get_version函数不存在")
        
        # 成功找到，不再尝试其他名称
        break
        
    except ImportError as e:
        print(f"  [ERROR] 导入失败: {e}")
    except Exception as e:
        print(f"  [ERROR] 加载错误: {e}")
        traceback.print_exc()

# 恢复原始sys.path
sys.path = original_sys_path

print("\\n" + "=" * 60)
print("诊断完成")
print("=" * 60)
'''
    
    with open(diag_script, 'w', encoding='utf-8') as f:
        f.write(diag_content)
    
    print(f"[OK] 创建诊断脚本: {diag_script}")
    
    # 6. 提供操作指南
    print("\n" + "=" * 60)
    print("修复完成 - 下一步操作")
    print("=" * 60)
    print("""
修复已完成！以下是下一步操作：

1. 重启Blender或重新加载插件
2. 在Blender中运行诊断脚本:
   - 文本编辑器 -> 打开 -> 选择: step_exporter/diagnose_cpp_ext.py
   - 点击"运行脚本"

3. 诊断脚本会尝试不同的模块名，并显示哪个能够成功加载
4. 如果诊断成功，尝试导出STEP文件:
   - 文件 -> 导出 -> STEP (.step)

5. 如果仍然失败，请查看控制台输出，并注意:
   - 哪个模块名成功加载了C++扩展
   - 是否找到了export_step函数
   - 是否有任何错误信息

6. 回滚选项:
   如果需要恢复原始插件，使用备份文件:
   - 将 __init__.py.backup 重命名为 __init__.py
""")
    
    return True

def main():
    """主函数"""
    print("STEP导出器插件加载问题修复工具")
    print("=" * 60)
    
    # 测试C++扩展加载
    if not fix_plugin_loading():
        print("\n[WARNING] C++扩展加载测试失败，但继续创建修复文件...")
    
    # 创建修复后的插件文件
    if not create_fixed_plugin():
        print("\n[ERROR] 创建修复文件失败")
        return False
    
    print("\n" + "=" * 60)
    print("[SUCCESS] 修复完成!")
    print("=" * 60)
    print("""
修复已完成，插件文件已更新。

请按以下步骤操作：
1. 重启Blender
2. 运行诊断脚本: step_exporter/diagnose_cpp_ext.py
3. 查看诊断结果，确认C++扩展是否正确加载
4. 尝试导出STEP文件

如果问题仍然存在，请提供:
- 诊断脚本的输出
- Blender控制台的完整错误信息
""")
    
    return True

if __name__ == "__main__":
    try:
        success = main()
        if success:
            sys.exit(0)
        else:
            sys.exit(1)
    except KeyboardInterrupt:
        print("\n\n修复被用户中断")
        sys.exit(1)
    except Exception as e:
        print(f"\n[ERROR] 修复失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)