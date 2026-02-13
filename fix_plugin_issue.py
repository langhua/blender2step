#!/usr/bin/env python3
"""
修复 Blender 插件导入问题
"""

import os
import sys
import shutil
from pathlib import Path

def fix_blender_plugin():
    """修复 Blender 插件导入问题"""
    project_dir = Path(__file__).parent.parent
    
    print("=" * 60)
    print("Fix Blender Plugin Import Issue")
    print("=" * 60)
    
    # 1. 查找插件安装位置
    print("\n1. Finding Blender plugin location...")
    
    blender_versions = ["4.2", "4.1", "4.0", "3.6", "3.5", "3.4", "3.3", "3.2", "3.1", "3.0"]
    
    plugin_dir = None
    for version in blender_versions:
        addons_dir = Path(os.path.expanduser(f"~\\AppData\\Roaming\\Blender Foundation\\Blender\\{version}\\scripts\\addons"))
        plugin_path = addons_dir / "step_exporter"
        if plugin_path.exists():
            plugin_dir = plugin_path
            print(f"[INFO] Found plugin at: {plugin_dir}")
            break
    
    if not plugin_dir:
        print("[ERROR] Plugin not found in Blender addons directory")
        return False
    
    # 2. 检查文件
    print("\n2. Checking plugin files...")
    
    lib_dir = plugin_dir / "lib"
    if not lib_dir.exists():
        print(f"[ERROR] lib directory not found: {lib_dir}")
        return False
    
    # 检查 C++ 扩展文件
    pyd_files = list(lib_dir.glob("*.pyd"))
    if not pyd_files:
        print("[ERROR] No .pyd files found in lib directory")
        return False
    
    cpp_ext_file = pyd_files[0]
    print(f"[OK] C++ extension file: {cpp_ext_file.name}")
    
    # 3. 创建修复后的插件文件
    print("\n3. Creating fixed plugin file...")
    
    fixed_plugin_content = '''"""
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
from bpy.props import StringProperty
from bpy.types import Operator

# 存储C++扩展模块的全局变量
_cpp_extension = None

def load_cpp_extension():
    """使用 importlib 直接加载 C++ 扩展模块"""
    global _cpp_extension
    
    if _cpp_extension is not None:
        return _cpp_extension
    
    # 获取插件目录
    plugin_dir = os.path.dirname(__file__)
    lib_dir = os.path.join(plugin_dir, "lib")
    
    if not os.path.exists(lib_dir):
        print("[STEP EXPORTER ERROR] lib directory not found")
        return None
    
    # 查找 .pyd 文件
    pyd_files = [f for f in os.listdir(lib_dir) if f.lower().endswith('.pyd')]
    if not pyd_files:
        print("[STEP EXPORTER ERROR] No .pyd files found in lib directory")
        return None
    
    pyd_file = pyd_files[0]
    pyd_path = os.path.join(lib_dir, pyd_file)
    
    # 设置 DLL 搜索路径
    os.environ['PATH'] = lib_dir + ';' + os.environ.get('PATH', '')
    
    try:
        # 使用 importlib 直接加载 .pyd 文件
        spec = importlib.util.spec_from_file_location("_step_cpp_extension", pyd_path)
        cpp_module = importlib.util.module_from_spec(spec)
        
        # 将模块添加到 sys.modules
        sys.modules["_step_cpp_extension"] = cpp_module
        
        # 执行模块（加载C++扩展）
        spec.loader.exec_module(cpp_module)
        
        print(f"[STEP EXPORTER] C++ extension loaded from: {pyd_file}")
        _cpp_extension = cpp_module
        
        # 验证加载的模块
        if hasattr(_cpp_extension, 'export_step'):
            print("[STEP EXPORTER] C++ extension validated: export_step function found")
        if hasattr(_cpp_extension, 'get_version'):
            print("[STEP EXPORTER] C++ extension validated: get_version function found")
        
        return _cpp_extension
        
    except Exception as e:
        print(f"[STEP EXPORTER ERROR] Failed to load C++ extension: {e}")
        traceback.print_exc()
        return None

def get_cpp_extension():
    """获取C++扩展模块"""
    return load_cpp_extension()

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
        
        # 显示插件信息
        box = layout.box()
        box.label(text="STEP Exporter Settings")
        
        # 检查C++扩展是否可用
        cpp_ext = get_cpp_extension()
        if cpp_ext:
            box.label(text="✓ C++ extension loaded", icon='CHECKMARK')
            
            # 显示版本信息
            if hasattr(cpp_ext, 'get_version'):
                try:
                    version = cpp_ext.get_version()
                    box.label(text=f"Version: {version}")
                except:
                    pass
        else:
            box.label(text="✗ C++ extension not available", icon='ERROR')
        
        layout.label(text="Exports the current scene to STEP format")
    
    def execute(self, context):
        """执行导出操作"""
        # 获取C++扩展模块
        cpp_ext = get_cpp_extension()
        
        if cpp_ext is None:
            self.report({'ERROR'}, "Failed to load STEP exporter C++ extension")
            return {'CANCELLED'}
        
        if not hasattr(cpp_ext, 'export_step'):
            self.report({'ERROR'}, "C++ extension missing export_step function")
            return {'CANCELLED'}
        
        # 导出文件
        try:
            result = cpp_ext.export_step(self.filepath)
            if result:
                self.report({'INFO'}, f"Exported to {self.filepath}")
                return {'FINISHED'}
            else:
                self.report({'ERROR'}, "Export failed")
                return {'CANCELLED'}
        except Exception as e:
            self.report({'ERROR'}, f"Export error: {e}")
            print(f"[STEP EXPORTER ERROR] Export exception: {e}")
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
    cpp_ext = get_cpp_extension()
    if cpp_ext:
        print("[STEP EXPORTER] Plugin registered successfully")
    else:
        print("[STEP EXPORTER WARNING] Plugin registered, but C++ extension not loaded")

def unregister():
    """注销插件"""
    bpy.utils.unregister_class(STEP_EXPORTER_OT_export)
    bpy.types.TOPBAR_MT_file_export.remove(menu_func_export)
    
    # 清理C++扩展引用
    global _cpp_extension
    _cpp_extension = None
    print("[STEP EXPORTER] Plugin unregistered")

if __name__ == "__main__":
    register()
'''
    
    # 备份原插件文件
    init_file = plugin_dir / "__init__.py"
    if init_file.exists():
        backup_file = plugin_dir / "__init__.py.backup"
        shutil.copy2(init_file, backup_file)
        print(f"[INFO] Backed up original plugin to: {backup_file}")
    
    # 写入修复后的插件文件
    with open(init_file, 'w', encoding='utf-8') as f:
        f.write(fixed_plugin_content)
    
    print(f"[SUCCESS] Fixed plugin file created: {init_file}")
    
    # 4. 创建测试脚本
    print("\n4. Creating test script for Blender...")
    
    test_script = plugin_dir / "test_fix.py"
    test_content = '''"""
测试修复后的插件
在 Blender 文本编辑器中运行此脚本
"""

import bpy
import sys
import os
import traceback

print("=" * 60)
print("Testing Fixed STEP Exporter Plugin")
print("=" * 60)

# 1. 检查插件是否注册
print("\\n1. Checking if plugin operator is registered...")
if hasattr(bpy.types, 'STEP_EXPORTER_OT_export'):
    print("   [OK] Operator class found: STEP_EXPORTER_OT_export")
    op = bpy.types.STEP_EXPORTER_OT_export
    print(f"   Operator ID: {op.bl_idname}")
    print(f"   Operator label: {op.bl_label}")
else:
    print("   [ERROR] Operator class not found")

# 2. 手动测试C++扩展加载
print("\\n2. Manually testing C++ extension loading...")

# 获取插件目录
plugin_dir = os.path.dirname(__file__)
lib_dir = os.path.join(plugin_dir, "lib")

print(f"   Plugin directory: {plugin_dir}")
print(f"   Library directory: {lib_dir}")

# 检查文件
if os.path.exists(lib_dir):
    pyd_files = [f for f in os.listdir(lib_dir) if f.lower().endswith('.pyd')]
    print(f"   Found {len(pyd_files)} .pyd files in lib directory")
    
    for pyd_file in pyd_files:
        print(f"     - {pyd_file}")
else:
    print("   [ERROR] lib directory not found")

# 3. 尝试加载C++扩展
print("\\n3. Attempting to load C++ extension...")

# 设置DLL搜索路径
os.environ['PATH'] = lib_dir + ';' + os.environ.get('PATH', '')

# 添加lib目录到Python路径
if lib_dir not in sys.path:
    sys.path.insert(0, lib_dir)

try:
    # 使用 importlib 直接加载
    import importlib.util
    
    pyd_path = os.path.join(lib_dir, pyd_files[0])
    spec = importlib.util.spec_from_file_location("_test_cpp_ext", pyd_path)
    cpp_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cpp_module)
    
    print(f"   [SUCCESS] C++ extension loaded: {pyd_files[0]}")
    
    # 检查函数
    print("   Available functions in C++ extension:")
    for attr in dir(cpp_module):
        if not attr.startswith('_'):
            print(f"     - {attr}")
    
    # 测试函数
    if hasattr(cpp_module, 'get_version'):
        try:
            version = cpp_module.get_version()
            print(f"   Version: {version}")
        except Exception as e:
            print(f"   Error getting version: {e}")
    
    if hasattr(cpp_module, 'export_step'):
        print("   [OK] export_step function found")
    else:
        print("   [ERROR] export_step function NOT found")
    
except Exception as e:
    print(f"   [ERROR] Failed to load C++ extension: {e}")
    traceback.print_exc()

print("\\n" + "=" * 60)
print("Test complete!")
print("=" * 60)
'''
    
    with open(test_script, 'w', encoding='utf-8') as f:
        f.write(test_content)
    
    print(f"[OK] Test script created: {test_script}")
    
    # 5. 提供操作指南
    print("\n" + "=" * 60)
    print("FIX COMPLETE - NEXT STEPS")
    print("=" * 60)
    print("\n1. Restart Blender to load the fixed plugin")
    print("\n2. In Blender, open Text Editor and load:")
    print(f"   {test_script}")
    print("\n3. Run the test script to verify the fix")
    print("\n4. Try exporting a STEP file from:")
    print("   File > Export > STEP (.step)")
    
    return True

if __name__ == "__main__":
    try:
        success = fix_blender_plugin()
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