#!/usr/bin/env python3
"""
修复STEP导出器插件部署
"""

import os
import sys
import shutil
from pathlib import Path

def fix_deploy_to_blender():
    """修复部署到Blender"""
    project_dir = Path(__file__).parent.parent
    
    print("=" * 60)
    print("Fix Deployment for STEP Exporter")
    print("=" * 60)
    
    # 1. 查找构建目录
    print("\n1. Finding build directory...")
    
    build_dirs = [
        project_dir / "out" / "build" / "x64-Release",
        project_dir / "out" / "build" / "x64-RelWithDebInfo",
        project_dir / "build" / "Release",
        project_dir / "build2" / "Release",
    ]
    
    build_dir = None
    for dir_path in build_dirs:
        if dir_path.exists():
            pyd_files = list(dir_path.glob("*.pyd"))
            if pyd_files:
                build_dir = dir_path
                print(f"[INFO] Found build directory: {build_dir}")
                break
    
    if not build_dir:
        print("[ERROR] No build directory found")
        return False
    
    # 2. 创建修复后的插件目录
    print("\n2. Creating fixed plugin directory...")
    
    fixed_plugin_dir = project_dir / "step_exporter_fixed"
    
    # 清理旧目录
    if fixed_plugin_dir.exists():
        print(f"[INFO] Removing old directory: {fixed_plugin_dir}")
        shutil.rmtree(fixed_plugin_dir, ignore_errors=True)
    
    # 创建目录结构
    lib_dir = fixed_plugin_dir / "lib"
    lib_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"[OK] Created directory: {fixed_plugin_dir}")
    
    # 3. 复制所有文件
    print("\n3. Copying all files from build directory...")
    
    # 复制.pyd文件
    pyd_files = list(build_dir.glob("*.pyd"))
    if not pyd_files:
        print("[ERROR] No .pyd files in build directory")
        return False
    
    for pyd_file in pyd_files:
        shutil.copy2(pyd_file, lib_dir / pyd_file.name)
        print(f"[OK] Copied: {pyd_file.name}")
    
    # 复制所有DLL文件
    dll_files = list(build_dir.glob("*.dll"))
    for dll_file in dll_files:
        shutil.copy2(dll_file, lib_dir / dll_file.name)
        print(f"[OK] Copied: {dll_file.name}")
    
    print(f"[INFO] Copied {len(pyd_files)} .pyd files and {len(dll_files)} DLL files")
    
    # 4. 复制修复后的插件主文件
    print("\n4. Copying fixed plugin files...")
    
    # 创建修复后的__init__.py文件
    init_file = fixed_plugin_dir / "__init__.py"
    init_content = '''"""
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
from bpy_extras.io_utils import ExportHelper
from bpy.props import StringProperty, BoolProperty, FloatProperty
from bpy.types import Operator, Panel

# 全局变量存储C++扩展模块
_cpp_extension = None
_cpp_extension_loaded = False
_cpp_extension_error = None

def get_cpp_extension():
    """获取C++扩展模块 - 使用正确的导入方法"""
    global _cpp_extension, _cpp_extension_loaded, _cpp_extension_error
    
    if _cpp_extension_loaded:
        return _cpp_extension
    
    if _cpp_extension_error is not None:
        return None
    
    # 获取插件目录
    plugin_dir = os.path.dirname(__file__)
    lib_dir = os.path.join(plugin_dir, "lib")
    
    if not os.path.exists(lib_dir):
        _cpp_extension_error = f"lib directory not found: {lib_dir}"
        print(f"[STEP EXPORTER ERROR] {_cpp_extension_error}")
        return None
    
    # 设置DLL搜索路径
    original_path = os.environ.get('PATH', '')
    os.environ['PATH'] = lib_dir + ';' + original_path
    
    # 添加lib目录到Python路径
    if lib_dir not in sys.path:
        sys.path.insert(0, lib_dir)
    
    # 查找.pyd文件
    pyd_files = [f for f in os.listdir(lib_dir) if f.lower().endswith('.pyd')]
    if not pyd_files:
        _cpp_extension_error = f"No .pyd files found in {lib_dir}"
        print(f"[STEP EXPORTER ERROR] {_cpp_extension_error}")
        return None
    
    pyd_file = pyd_files[0]
    pyd_name = os.path.splitext(pyd_file)[0]  # 例如: step_exporter
    
    print(f"[STEP EXPORTER] Found C++ extension: {pyd_file}")
    print(f"[STEP EXPORTER] Attempting to import module: {pyd_name}")
    
    try:
        # 使用__import__直接导入
        module = __import__(pyd_name)
        _cpp_extension = module
        _cpp_extension_loaded = True
        
        print(f"[STEP EXPORTER] C++ extension loaded successfully: {pyd_name}")
        
        # 验证模块
        if hasattr(_cpp_extension, 'export_step'):
            print("[STEP EXPORTER] ✓ export_step function found")
        else:
            print("[STEP EXPORTER] ✗ export_step function NOT found")
            
        if hasattr(_cpp_extension, 'get_version'):
            print("[STEP EXPORTER] ✓ get_version function found")
        else:
            print("[STEP EXPORTER] ✗ get_version function NOT found")
        
        return _cpp_extension
        
    except ImportError as e:
        _cpp_extension_error = f"ImportError: {e}"
        print(f"[STEP EXPORTER ERROR] Failed to import C++ extension: {e}")
        
        # 尝试诊断问题
        print("[STEP EXPORTER DEBUG] sys.path:")
        for i, path in enumerate(sys.path[:5]):  # 只显示前5个路径
            print(f"  {i}: {path}")
        
        print(f"[STEP EXPORTER DEBUG] Files in {lib_dir}:")
        for f in os.listdir(lib_dir):
            if f.endswith(('.pyd', '.dll')):
                print(f"  - {f}")
        
        return None
    except Exception as e:
        _cpp_extension_error = f"Unexpected error: {e}"
        print(f"[STEP EXPORTER ERROR] Unexpected error loading C++ extension: {e}")
        traceback.print_exc()
        return None

class STEP_EXPORTER_OT_export(Operator, ExportHelper):
    """Export to STEP format"""
    bl_idname = "export.step"
    bl_label = "Export STEP"
    
    filename_ext = ".step"
    
    filter_glob: StringProperty(
        default="*.step;*.stp",
        options={'HIDDEN'},
    )
    
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
            if hasattr(cpp_ext, 'get_version'):
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
        # 获取C++扩展模块
        cpp_ext = get_cpp_extension()
        
        if cpp_ext is None:
            self.report({'ERROR'}, "Failed to load STEP exporter C++ extension")
            if _cpp_extension_error:
                self.report({'ERROR'}, f"Error: {_cpp_extension_error}")
            return {'CANCELLED'}
        
        if not hasattr(cpp_ext, 'export_step'):
            self.report({'ERROR'}, "C++ extension missing export_step function")
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

class STEP_EXPORTER_PT_panel(Panel):
    """STEP导出器面板"""
    bl_label = "STEP Exporter"
    bl_idname = "STEP_EXPORTER_PT_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "STEP"
    
    def draw(self, context):
        layout = self.layout
        
        # 插件状态
        box = layout.box()
        box.label(text="Plugin Status", icon='INFO')
        
        cpp_ext = get_cpp_extension()
        if cpp_ext:
            box.label(text="✓ C++ extension loaded", icon='CHECKMARK')
            
            if hasattr(cpp_ext, 'get_version'):
                try:
                    version = cpp_ext.get_version()
                    box.label(text=f"Version: {version}")
                except:
                    pass
        else:
            box.label(text="✗ C++ extension not loaded", icon='ERROR')
        
        # 快速导出按钮
        layout.separator()
        layout.operator("export.step", text="Export STEP", icon='EXPORT')

def menu_func_export(self, context):
    """在导出菜单中添加STEP导出项"""
    self.layout.operator(STEP_EXPORTER_OT_export.bl_idname, text="STEP (.step)")

def register():
    """注册插件"""
    bpy.utils.register_class(STEP_EXPORTER_OT_export)
    bpy.utils.register_class(STEP_EXPORTER_PT_panel)
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
    bpy.utils.unregister_class(STEP_EXPORTER_PT_panel)
    bpy.types.TOPBAR_MT_file_export.remove(menu_func_export)
    
    # 清理C++扩展引用
    global _cpp_extension, _cpp_extension_loaded, _cpp_extension_error
    _cpp_extension = None
    _cpp_extension_loaded = False
    _cpp_extension_error = None
    print("[STEP EXPORTER] Plugin unregistered")

if __name__ == "__main__":
    register()
'''
    
    with open(init_file, 'w', encoding='utf-8') as f:
        f.write(init_content)
    
    print(f"[OK] Created fixed __init__.py")
    
    # 5. 部署到Blender
    print("\n5. Deploying to Blender...")
    
    # 查找Blender插件目录
    blender_versions = ["4.2", "4.1", "4.0", "3.6", "3.5", "3.4", "3.3", "3.2", "3.1", "3.0"]
    
    blender_addons_dir = None
    for version in blender_versions:
        addons_dir = Path(os.path.expanduser(f"~\\AppData\\Roaming\\Blender Foundation\\Blender\\{version}\\scripts\\addons"))
        if addons_dir.exists():
            blender_addons_dir = addons_dir
            print(f"[INFO] Found Blender addons directory: {blender_addons_dir}")
            break
    
    if blender_addons_dir:
        # 部署到Blender
        target_dir = blender_addons_dir / "step_exporter"
        
        if target_dir.exists():
            print(f"[INFO] Removing existing plugin: {target_dir}")
            shutil.rmtree(target_dir, ignore_errors=True)
        
        shutil.copytree(fixed_plugin_dir, target_dir)
        print(f"[SUCCESS] Fixed plugin deployed to: {target_dir}")
        
        # 创建测试脚本
        test_script = target_dir / "test_deployment.py"
        test_content = '''"""
测试部署后的插件
在Blender文本编辑器中运行此脚本
"""

import bpy
import sys
import os
import traceback

print("=" * 60)
print("Testing Deployed STEP Exporter Plugin")
print("=" * 60)

# 检查插件是否注册
print("\\n1. Checking plugin registration...")

if hasattr(bpy.types, 'STEP_EXPORTER_OT_export'):
    print("   [SUCCESS] Operator class found")
else:
    print("   [ERROR] Operator class not found")

# 检查C++扩展
print("\\n2. Checking C++ extension...")

# 尝试导入插件模块
plugin_dir = os.path.dirname(__file__)
lib_dir = os.path.join(plugin_dir, "lib")

if os.path.exists(lib_dir):
    print(f"   [INFO] lib directory exists: {lib_dir}")
    
    # 列出文件
    pyd_files = [f for f in os.listdir(lib_dir) if f.lower().endswith('.pyd')]
    print(f"   [INFO] Found {len(pyd_files)} .pyd files")
    
    for pyd_file in pyd_files:
        print(f"     - {pyd_file}")
else:
    print("   [ERROR] lib directory not found")

print("\\n" + "=" * 60)
print("Test complete!")
print("=" * 60)
'''
        
        with open(test_script, 'w', encoding='utf-8') as f:
            f.write(test_content)
        
        print(f"[OK] Created test script: {test_script}")
        
        print("\n" + "=" * 60)
        print("DEPLOYMENT COMPLETE")
        print("=" * 60)
        print("\nNext steps:")
        print("1. Restart Blender")
        print("2. Enable the plugin in Edit > Preferences > Add-ons")
        print("3. Search for 'STEP Exporter' and enable it")
        print("4. Test the plugin by exporting a STEP file")
        print("5. Run the test script in Blender's text editor")
        
        return True
    else:
        print("\n[WARNING] Blender addons directory not found")
        print("\n" + "=" * 60)
        print("MANUAL DEPLOYMENT REQUIRED")
        print("=" * 60)
        print(f"\nFixed plugin created at: {fixed_plugin_dir}")
        print("\nTo install manually:")
        print(f"1. Copy the folder: {fixed_plugin_dir}")
        print("2. Paste it into Blender's addons directory")
        print("3. Typically located at: %APPDATA%\\Blender Foundation\\Blender\\<version>\\scripts\\addons\\")
        print("4. Rename the folder to: step_exporter")
        print("5. Enable the plugin in Blender Preferences > Add-ons")
        
        return True

if __name__ == "__main__":
    try:
        success = fix_deploy_to_blender()
        if success:
            sys.exit(0)
        else:
            sys.exit(1)
    except KeyboardInterrupt:
        print("\n\nDeployment interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n[ERROR] Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)