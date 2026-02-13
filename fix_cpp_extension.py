#!/usr/bin/env python3
"""
修复C++扩展加载问题
此脚本修改插件加载机制，确保正确加载C++扩展
"""

import os
import sys
import shutil
import subprocess
from pathlib import Path

def fix_cpp_extension_loading():
    """修复C++扩展加载问题"""
    project_dir = Path(__file__).parent
    plugin_dir = project_dir / "step_exporter"
    
    print("=" * 60)
    print("Fix C++ Extension Loading Issue")
    print("=" * 60)
    
    if not plugin_dir.exists():
        print(f"[ERROR] Plugin directory not found: {plugin_dir}")
        return False
    
    # 1. 检查lib目录
    lib_dir = plugin_dir / "lib"
    if not lib_dir.exists():
        print(f"[ERROR] lib directory not found: {lib_dir}")
        return False
    
    # 2. 查找.pyd文件
    pyd_files = list(lib_dir.glob("*.pyd"))
    if not pyd_files:
        print("[ERROR] No .pyd files found in lib directory")
        return False
    
    pyd_file = pyd_files[0]
    print(f"[INFO] Found C++ extension: {pyd_file.name}")
    
    # 3. 创建修复后的插件主文件
    print("\nCreating fixed plugin file...")
    
    # 使用ctypes直接加载C++扩展
    fixed_init_content = '''"""
STEP Exporter for Blender
Export 3D models to STEP format using OpenCASCADE
Fixed version that properly loads C++ extension
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
import ctypes
import traceback
from bpy_extras.io_utils import ExportHelper
from bpy.props import StringProperty, BoolProperty, FloatProperty
from bpy.types import Operator, Panel

# 全局变量存储C++扩展的函数指针
_cpp_functions = {}
_cpp_extension_loaded = False
_cpp_extension_error = None

def load_cpp_functions():
    """使用ctypes直接加载C++扩展函数"""
    global _cpp_functions, _cpp_extension_loaded, _cpp_extension_error
    
    if _cpp_extension_loaded:
        return _cpp_functions
    
    if _cpp_extension_error is not None:
        return None
    
    # 获取插件目录
    plugin_dir = os.path.dirname(__file__)
    lib_dir = os.path.join(plugin_dir, "lib")
    
    if not os.path.exists(lib_dir):
        _cpp_extension_error = f"lib directory not found: {lib_dir}"
        print(f"[STEP EXPORTER ERROR] {_cpp_extension_error}")
        return None
    
    # 查找.pyd文件
    pyd_files = [f for f in os.listdir(lib_dir) if f.lower().endswith('.pyd')]
    if not pyd_files:
        _cpp_extension_error = f"No .pyd files found in {lib_dir}"
        print(f"[STEP EXPORTER ERROR] {_cpp_extension_error}")
        return None
    
    pyd_file = pyd_files[0]
    pyd_path = os.path.join(lib_dir, pyd_file)
    
    # 设置DLL搜索路径
    original_path = os.environ.get('PATH', '')
    os.environ['PATH'] = lib_dir + ';' + original_path
    
    print(f"[STEP EXPORTER] Attempting to load C++ extension: {pyd_file}")
    
    try:
        # 使用ctypes加载.pyd文件
        cpp_lib = ctypes.CDLL(pyd_path)
        print(f"[STEP EXPORTER] C++ extension loaded via ctypes")
        
        # 尝试获取函数
        # 注意：由于Python/C API的限制，我们不能直接调用Python C扩展中的函数
        # 但我们可以尝试通过Python解释器加载它
        
        # 方法2：通过Python导入系统，但使用不同的名称
        import importlib.util
        
        # 创建一个唯一的模块名
        module_name = '_step_cpp_ext'
        
        # 从文件加载模块
        spec = importlib.util.spec_from_file_location(module_name, pyd_path)
        if spec is None:
            _cpp_extension_error = f"Could not create spec from {pyd_file}"
            print(f"[STEP EXPORTER ERROR] {_cpp_extension_error}")
            return None
        
        # 创建模块
        module = importlib.util.module_from_spec(spec)
        
        # 在sys.modules中注册模块
        sys.modules[module_name] = module
        
        # 执行模块（这会调用PyInit_step_exporter）
        spec.loader.exec_module(module)
        
        print(f"[STEP EXPORTER] Module loaded successfully")
        
        # 检查函数
        if hasattr(module, 'export_step'):
            _cpp_functions['export_step'] = module.export_step
            print("[STEP EXPORTER] ✓ Found export_step function")
        else:
            print("[STEP EXPORTER] ✗ export_step function NOT found")
            
        if hasattr(module, 'get_version'):
            _cpp_functions['get_version'] = module.get_version
            print("[STEP EXPORTER] ✓ Found get_version function")
        else:
            print("[STEP EXPORTER] ✗ get_version function NOT found")
        
        _cpp_extension_loaded = True
        return _cpp_functions
        
    except Exception as e:
        _cpp_extension_error = f"Error loading C++ extension: {e}"
        print(f"[STEP EXPORTER ERROR] {_cpp_extension_error}")
        traceback.print_exc()
        return None

def get_cpp_extension():
    """获取C++扩展功能"""
    funcs = load_cpp_functions()
    if funcs is None:
        return None
    
    # 创建一个简单的包装器
    class CppExtensionWrapper:
        @staticmethod
        def export_step(filename):
            if 'export_step' in funcs:
                return funcs['export_step'](filename)
            return False
        
        @staticmethod
        def get_version():
            if 'get_version' in funcs:
                return funcs['get_version']()
            return "Unknown"
    
    return CppExtensionWrapper()

class STEP_EXPORTER_OT_export(Operator, ExportHelper):
    """Export to STEP format"""
    bl_idname = "export.step"
    bl_label = "Export STEP"
    
    filename_ext = ".step"
    
    filter_glob: StringProperty(
        default="*.step;*.stp",
        options={'HIDDEN'},
    )
    
    def draw(self, context):
        """绘制操作符界面"""
        layout = self.layout
        
        # 显示插件状态
        box = layout.box()
        box.label(text="STEP Exporter Status", icon='INFO')
        
        cpp_ext = get_cpp_extension()
        if cpp_ext:
            box.label(text="✓ C++ extension loaded", icon='CHECKMARK')
            
            # 显示版本信息
            try:
                version = cpp_ext.get_version()
                box.label(text=f"Version: {version}")
            except:
                box.label(text="Version: Unknown")
        else:
            box.label(text="✗ C++ extension not available", icon='ERROR')
            if _cpp_extension_error:
                box.label(text=f"Error: {_cpp_extension_error[:50]}...", icon='CANCEL')
        
        # 导出设置
        box = layout.box()
        box.label(text="Export Settings", icon='SETTINGS')
        box.prop(self, "use_selected")
        box.prop(self, "scale")
    
    def execute(self, context):
        """执行导出操作"""
        # 获取C++扩展
        cpp_ext = get_cpp_extension()
        
        if cpp_ext is None:
            self.report({'ERROR'}, "Failed to load STEP exporter C++ extension")
            if _cpp_extension_error:
                self.report({'ERROR'}, f"Error: {_cpp_extension_error}")
            return {'CANCELLED'}
        
        # 导出文件
        try:
            result = cpp_ext.export_step(self.filepath)
            if result:
                self.report({'INFO'}, f"Successfully exported to {self.filepath}")
                return {'FINISHED'}
            else:
                self.report({'ERROR'}, "Export failed - see console for details")
                return {'CANCELLED'}
        except Exception as e:
            self.report({'ERROR'}, f"Export error: {str(e)[:100]}")
            print(f"[STEP EXPORTER ERROR] Export exception: {e}")
            traceback.print_exc()
            return {'CANCELLED'}
    
    use_selected: BoolProperty(
        name="Selected Only",
        description="Export selected objects only",
        default=False,
    )
    
    scale: FloatProperty(
        name="Scale",
        description="Scale factor for export",
        default=1.0,
        min=0.001,
        max=1000.0,
    )

def menu_func_export(self, context):
    """在导出菜单中添加STEP导出项"""
    self.layout.operator(STEP_EXPORTER_OT_export.bl_idname, text="STEP (.step)")

def register():
    """注册插件"""
    bpy.utils.register_class(STEP_EXPORTER_OT_export)
    bpy.types.TOPBAR_MT_file_export.append(menu_func_export)
    
    # 预加载C++扩展
    cpp_ext = get_cpp_extension()
    if cpp_ext:
        print("[STEP EXPORTER] Plugin registered successfully")
    else:
        print("[STEP EXPORTER WARNING] Plugin registered, but C++ extension not loaded")

def unregister():
    """注销插件"""
    bpy.utils.unregister_class(STEP_EXPORTER_OT_export)
    bpy.types.TOPBAR_MT_file_export.remove(menu_func_export)
    
    # 清理全局变量
    global _cpp_functions, _cpp_extension_loaded, _cpp_extension_error
    _cpp_functions = {}
    _cpp_extension_loaded = False
    _cpp_extension_error = None
    print("[STEP EXPORTER] Plugin unregistered")

if __name__ == "__main__":
    register()
'''
    
    # 备份原文件
    init_file = plugin_dir / "__init__.py"
    if init_file.exists():
        backup_file = plugin_dir / "__init__.py.backup"
        shutil.copy2(init_file, backup_file)
        print(f"[INFO] Backed up original plugin to: {backup_file}")
    
    # 写入修复后的文件
    with open(init_file, 'w', encoding='utf-8') as f:
        f.write(fixed_init_content)
    
    print(f"[SUCCESS] Fixed plugin file created: {init_file}")
    
    # 4. 创建诊断工具
    print("\nCreating diagnostic tool...")
    
    diag_script = plugin_dir / "diagnose_import.py"
    diag_content = '''"""
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
print(f"\\nFound {len(pyd_files)} .pyd files:")
for pyd in pyd_files:
    pyd_path = os.path.join(lib_dir, pyd)
    print(f"  - {pyd} ({os.path.getsize(pyd_path):,} bytes)")

if not pyd_files:
    print("[ERROR] No .pyd files found")
    sys.exit(1)

# 设置DLL搜索路径
os.environ['PATH'] = lib_dir + ';' + os.environ.get('PATH', '')

# 方法1: 尝试标准导入
print("\\n1. Trying standard import...")
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
print("\\n2. Trying importlib...")
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

print("\\n" + "=" * 60)
print("Diagnosis complete")
print("=" * 60)
'''
    
    with open(diag_script, 'w', encoding='utf-8') as f:
        f.write(diag_content)
    
    print(f"[OK] Created diagnostic script: {diag_script}")
    
    # 5. 创建简单的测试插件
    print("\nCreating simple test plugin...")
    
    simple_plugin = plugin_dir / "simple_test.py"
    simple_content = '''"""
简单的测试插件，直接加载C++扩展
"""

import bpy
import sys
import os
import importlib.util
from bpy_extras.io_utils import ExportHelper
from bpy.props import StringProperty
from bpy.types import Operator

class SIMPLE_STEP_EXPORTER_OT_export(Operator, ExportHelper):
    """Simple STEP Export"""
    bl_idname = "export.simple_step"
    bl_label = "Export STEP (Simple)"
    
    filename_ext = ".step"
    
    filter_glob: StringProperty(
        default="*.step;*.stp",
        options={'HIDDEN'},
    )
    
    def execute(self, context):
        # 加载C++扩展
        plugin_dir = os.path.dirname(__file__)
        lib_dir = os.path.join(plugin_dir, "lib")
        
        # 查找.pyd文件
        pyd_files = [f for f in os.listdir(lib_dir) if f.lower().endswith('.pyd')]
        if not pyd_files:
            self.report({'ERROR'}, "No C++ extension found")
            return {'CANCELLED'}
        
        pyd_path = os.path.join(lib_dir, pyd_files[0])
        
        # 设置DLL搜索路径
        os.environ['PATH'] = lib_dir + ';' + os.environ.get('PATH', '')
        
        # 使用importlib加载
        try:
            spec = importlib.util.spec_from_file_location("_simple_step_cpp", pyd_path)
            module = importlib.util.module_from_spec(spec)
            sys.modules["_simple_step_cpp"] = module
            spec.loader.exec_module(module)
            
            if hasattr(module, 'export_step'):
                result = module.export_step(self.filepath)
                if result:
                    self.report({'INFO'}, f"Exported to {self.filepath}")
                    return {'FINISHED'}
                else:
                    self.report({'ERROR'}, "Export failed")
                    return {'CANCELLED'}
            else:
                self.report({'ERROR'}, "C++ extension missing export_step")
                return {'CANCELLED'}
                
        except Exception as e:
            self.report({'ERROR'}, f"Error: {str(e)[:100]}")
            import traceback
            traceback.print_exc()
            return {'CANCELLED'}

def register():
    bpy.utils.register_class(SIMPLE_STEP_EXPORTER_OT_export)
    bpy.types.TOPBAR_MT_file_export.append(
        lambda self, context: self.layout.operator(
            SIMPLE_STEP_EXPORTER_OT_export.bl_idname, 
            text="STEP Simple (.step)"
        )
    )

def unregister():
    bpy.utils.unregister_class(SIMPLE_STEP_EXPORTER_OT_export)
    menu_items = bpy.types.TOPBAR_MT_file_export
    for i, item in enumerate(menu_items._dynamic_items):
        if hasattr(item, 'operator') and item.operator == "export.simple_step":
            menu_items._dynamic_items.pop(i)
            break

if __name__ == "__main__":
    register()
'''
    
    with open(simple_plugin, 'w', encoding='utf-8') as f:
        f.write(simple_content)
    
    print(f"[OK] Created simple test plugin: {simple_plugin}")
    
    # 6. 提供操作指南
    print("\n" + "=" * 60)
    print("FIX COMPLETE - NEXT STEPS")
    print("=" * 60)
    print("""
修复已完成！以下是下一步操作：

1. 重启Blender或重新加载插件
2. 在Blender中运行诊断脚本:
   - 文本编辑器 -> 打开 -> 选择: step_exporter/diagnose_import.py
   - 点击"运行脚本"

3. 如果诊断成功，尝试导出STEP文件:
   - 文件 -> 导出 -> STEP (.step)

4. 如果仍然失败，尝试简单测试插件:
   - 文本编辑器 -> 打开 -> 选择: step_exporter/simple_test.py
   - 点击"运行脚本"
   - 然后使用: 文件 -> 导出 -> STEP Simple (.step)

5. 常见问题解决:
   - 如果出现DLL错误，确保所有DLL都在lib目录中
   - 如果出现权限错误，以管理员身份运行Blender
   - 如果导入失败，检查Python版本是否匹配(3.11)

6. 回滚选项:
   如果需要恢复原始插件，使用备份文件:
   - 将 __init__.py.backup 重命名为 __init__.py
""")
    
    return True

if __name__ == "__main__":
    try:
        success = fix_cpp_extension_loading()
        if success:
            print("\n✅ Fix applied successfully!")
        else:
            print("\n❌ Fix failed")
        
        input("\nPress Enter to exit...")
        
    except Exception as e:
        print(f"\n[ERROR] Fix failed: {e}")
        import traceback
        traceback.print_exc()
        input("\nPress Enter to exit...")