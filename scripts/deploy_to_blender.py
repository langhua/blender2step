#!/usr/bin/env python3
"""
部署 STEP 导出器插件到 Blender
"""

import os
import sys
import shutil
from pathlib import Path

def deploy_to_blender():
    """部署插件到 Blender"""
    project_dir = Path(__file__).parent.parent
    
    print("=" * 60)
    print("Deploy STEP Exporter to Blender")
    print("=" * 60)
    
    # 查找插件文件
    print("\n1. Looking for plugin files...")
    
    build_dirs = [
        project_dir / "out" / "build" / "x64-Release",
        project_dir / "out" / "build" / "x64-RelWithDebInfo",
        project_dir / "build" / "Release",
        project_dir / "build2" / "Release",
    ]
    
    plugin_dir = None
    for build_dir in build_dirs:
        if build_dir.exists():
            pyd_files = list(build_dir.glob("*.pyd"))
            if pyd_files:
                plugin_dir = build_dir
                print(f"[INFO] Found plugin in: {plugin_dir}")
                break
    
    if not plugin_dir:
        print("[ERROR] No plugin directory found. Please build the project first.")
        return False
    
    # 检查插件文件
    pyd_files = list(plugin_dir.glob("*.pyd"))
    if not pyd_files:
        print("[ERROR] No .pyd files found in plugin directory")
        return False
    
    plugin_file = pyd_files[0]
    print(f"[INFO] Plugin file: {plugin_file.name}")
    
    # 检查 DLL 文件
    dll_files = list(plugin_dir.glob("*.dll"))
    print(f"[INFO] Found {len(dll_files)} DLL files")
    
    # 创建 Blender 插件目录结构
    print("\n2. Creating Blender plugin structure...")
    
    blender_plugin_dir = project_dir / "step_exporter"
    lib_dir = blender_plugin_dir / "lib"
    
    # 清理旧目录
    if blender_plugin_dir.exists():
        print(f"[INFO] Cleaning existing directory: {blender_plugin_dir}")
        shutil.rmtree(blender_plugin_dir, ignore_errors=True)
    
    # 创建目录
    lib_dir.mkdir(parents=True, exist_ok=True)
    print(f"[INFO] Created directory: {blender_plugin_dir}")
    
    # 复制文件
    print("\n3. Copying files...")
    
    # 复制插件文件
    shutil.copy2(plugin_file, lib_dir / plugin_file.name)
    print(f"[OK] Copied: {plugin_file.name}")
    
    # 复制 DLL 文件
    for dll_file in dll_files:
        shutil.copy2(dll_file, lib_dir / dll_file.name)
        print(f"[OK] Copied: {dll_file.name}")
    
    # 复制 Python DLL
    python_dll = Path(r"C:\Python311\python311.dll")
    if python_dll.exists():
        shutil.copy2(python_dll, lib_dir / "python311.dll")
        print("[OK] Copied: python311.dll")
    else:
        print("[WARN] Python DLL not found at: C:\\Python311\\python311.dll")
    
    # 创建 Blender 插件主文件
    print("\n4. Creating Blender plugin file...")
    
    init_py = blender_plugin_dir / "__init__.py"
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
from bpy_extras.io_utils import ExportHelper
from bpy.props import StringProperty
from bpy.types import Operator

class STEP_EXPORTER_OT_export(Operator, ExportHelper):
    """Export to STEP format"""
    bl_idname = "export.step"
    bl_label = "Export STEP"
    
    filename_ext = ".step"
    
    filter_glob: StringProperty(
        default="*.step;*.stp",
        options={'HIDDEN'},
    )
    
    def execute(self, context):
        # Add plugin library directory to paths
        lib_dir = os.path.join(os.path.dirname(__file__), "lib")
        
        if lib_dir not in sys.path:
            sys.path.insert(0, lib_dir)
        
        os.environ['PATH'] = lib_dir + ';' + os.environ.get('PATH', '')
        
        try:
            import step_exporter
        except ImportError as e:
            self.report({'ERROR'}, f"Failed to load STEP exporter: {e}")
            return {'CANCELLED'}
        
        # Export the file
        try:
            result = step_exporter.export_step(self.filepath)
            if result:
                self.report({'INFO'}, f"Exported to {self.filepath}")
                return {'FINISHED'}
            else:
                self.report({'ERROR'}, "Export failed")
                return {'CANCELLED'}
        except Exception as e:
            self.report({'ERROR'}, f"Export error: {e}")
            return {'CANCELLED'}

def menu_func_export(self, context):
    self.layout.operator(STEP_EXPORTER_OT_export.bl_idname, text="STEP (.step)")

def register():
    bpy.utils.register_class(STEP_EXPORTER_OT_export)
    bpy.types.TOPBAR_MT_file_export.append(menu_func_export)

def unregister():
    bpy.utils.unregister_class(STEP_EXPORTER_OT_export)
    bpy.types.TOPBAR_MT_file_export.remove(menu_func_export)

if __name__ == "__main__":
    register()
'''
    
    with open(init_py, 'w', encoding='utf-8') as f:
        f.write(init_content)
    
    print(f"[OK] Created: {init_py.name}")
    
    # 查找 Blender 插件目录
    print("\n5. Finding Blender addons directory...")
    
    blender_versions = ["4.2", "4.1", "4.0", "3.6", "3.5", "3.4", "3.3", "3.2", "3.1", "3.0", "2.93", "2.92", "2.91", "2.90", "2.83"]
    
    blender_addons_dir = None
    for version in blender_versions:
        addons_dir = Path(os.path.expanduser(f"~\\AppData\\Roaming\\Blender Foundation\\Blender\\{version}\\scripts\\addons"))
        if addons_dir.exists():
            blender_addons_dir = addons_dir
            print(f"[INFO] Found Blender addons directory: {blender_addons_dir}")
            break
    
    if not blender_addons_dir:
        # 尝试其他可能的路径
        possible_paths = [
            Path(os.path.expanduser("~\\AppData\\Roaming\\Blender Foundation\\Blender\\scripts\\addons")),
            Path("C:\\Program Files\\Blender Foundation\\Blender\\scripts\\addons"),
            Path("C:\\Program Files (x86)\\Blender Foundation\\Blender\\scripts\\addons"),
        ]
        
        for path in possible_paths:
            if path.exists():
                blender_addons_dir = path
                print(f"[INFO] Found Blender addons directory: {blender_addons_dir}")
                break
    
    if blender_addons_dir:
        # 部署到 Blender
        print("\n6. Deploying to Blender...")
        
        target_dir = blender_addons_dir / "step_exporter"
        
        if target_dir.exists():
            print(f"[INFO] Removing existing plugin: {target_dir}")
            shutil.rmtree(target_dir, ignore_errors=True)
        
        shutil.copytree(blender_plugin_dir, target_dir)
        print(f"[SUCCESS] Plugin deployed to: {target_dir}")
        
        print("\n" + "=" * 60)
        print("DEPLOYMENT COMPLETE")
        print("=" * 60)
        print("\nTo enable the plugin in Blender:")
        print("1. Open Blender")
        print("2. Go to Edit > Preferences > Add-ons")
        print("3. Search for 'STEP Exporter'")
        print("4. Enable the checkbox")
        print("5. Find the export option in: File > Export > STEP (.step)")
        
        return True
    else:
        print("\n[WARNING] Blender addons directory not found")
        print("\n" + "=" * 60)
        print("MANUAL DEPLOYMENT REQUIRED")
        print("=" * 60)
        print(f"\nPlugin created at: {blender_plugin_dir}")
        print("\nTo install manually:")
        print(f"1. Copy the folder: {blender_plugin_dir}")
        print("2. Paste it into Blender's addons directory")
        print("3. Typically located at: %APPDATA%\\Blender Foundation\\Blender\\<version>\\scripts\\addons\\")
        print("4. Enable the plugin in Blender Preferences > Add-ons")
        
        return True

if __name__ == "__main__":
    try:
        success = deploy_to_blender()
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
