#!/usr/bin/env python3
"""
VSCode Blender 插件开发部署脚本
用于将 STEP 导出器部署到项目目录，VSCode Blender 插件会通过硬链接将其链接到 Blender
"""

import os
import sys
import shutil
import subprocess
import tempfile
from pathlib import Path

def deploy_for_vscode_blender():
    """为 VSCode Blender 插件开发部署"""
    project_dir = Path(__file__).parent.parent
    
    print("=" * 60)
    print("VSCode Blender Plugin Development Deployment")
    print("=" * 60)
    print("此脚本将插件部署到项目目录，VSCode Blender 插件会自动处理硬链接")
    print()
    
    # 1. 查找构建目录
    print("1. 查找构建目录...")
    
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
                print(f"   [OK] 找到构建目录: {build_dir}")
                break
    
    if not build_dir:
        print("   [ERROR] 未找到构建目录")
        print("   请先构建项目，或确保在以下目录之一存在构建输出:")
        for dir_path in build_dirs:
            print(f"     - {dir_path}")
        return False
    
    # 2. 检查构建文件
    print("\n2. 检查构建文件...")
    
    pyd_files = list(build_dir.glob("*.pyd"))
    if not pyd_files:
        print("   [ERROR] 构建目录中没有找到 .pyd 文件")
        return False
    
    pyd_file = pyd_files[0]
    print(f"   [OK] 插件文件: {pyd_file.name}")
    print(f"        大小: {pyd_file.stat().st_size:,} 字节")
    print(f"        路径: {pyd_file}")
    
    dll_files = list(build_dir.glob("*.dll"))
    print(f"   [INFO] 找到 {len(dll_files)} 个 DLL 文件")
    
    # 显示关键DLL
    critical_dlls = ["TKernel.dll", "TKDESTEP.dll", "TKSTEP.dll", "TKMath.dll", "python311.dll"]
    for dll in critical_dlls:
        dll_path = build_dir / dll
        if dll_path.exists():
            print(f"         ✓ {dll}")
        else:
            print(f"         ✗ {dll} (缺失)")
    
    # 3. 准备项目插件目录
    print("\n3. 准备项目插件目录...")
    
    # VSCode Blender 插件期望的目录结构
    plugin_dir = project_dir / "step_exporter"
    lib_dir = plugin_dir / "lib"
    
    print(f"   插件目录: {plugin_dir}")
    print(f"   库目录: {lib_dir}")
    
    # 创建目录结构
    if plugin_dir.exists():
        print("   [INFO] 清理现有插件目录...")
        
        # 先移除 lib 目录（如果存在）
        if lib_dir.exists():
            try:
                shutil.rmtree(lib_dir)
                print("   [OK] 已清理 lib 目录")
            except Exception as e:
                print(f"   [WARN] 清理 lib 目录失败: {e}")
    else:
        plugin_dir.mkdir(parents=True, exist_ok=True)
        print("   [OK] 创建插件目录")
    
    # 确保 lib 目录存在
    lib_dir.mkdir(parents=True, exist_ok=True)
    print("   [OK] 确保 lib 目录存在")
    
    # 4. 复制文件到项目插件目录
    print("\n4. 复制文件到项目插件目录...")
    
    # 复制 .pyd 文件
    for pyd in pyd_files:
        dest_path = lib_dir / pyd.name
        shutil.copy2(pyd, dest_path)
        print(f"   [OK] 复制: {pyd.name} -> {dest_path.relative_to(project_dir)}")
    
    # 复制 DLL 文件
    dll_count = 0
    for dll in dll_files:
        dest_path = lib_dir / dll.name
        shutil.copy2(dll, dest_path)
        dll_count += 1
    
    print(f"   [OK] 复制了 {dll_count} 个 DLL 文件")
    
    # 5. 创建修复后的插件主文件
    print("\n5. 创建修复后的插件主文件...")
    
    init_file = plugin_dir / "__init__.py"
    
    # 修复后的插件主文件内容
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
    """获取C++扩展模块"""
    global _cpp_extension, _cpp_extension_loaded, _cpp_extension_error
    
    if _cpp_extension_loaded:
        return _cpp_extension
    
    if _cpp_extension_error is not None:
        return None
    
    # 获取插件目录
    plugin_dir = os.path.dirname(__file__)
    lib_dir = os.path.join(plugin_dir, "lib")
    
    if not os.path.exists(lib_dir):
        _cpp_extension_error = f"lib目录未找到: {lib_dir}"
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
        _cpp_extension_error = f"在 {lib_dir} 中未找到.pyd文件"
        print(f"[STEP EXPORTER ERROR] {_cpp_extension_error}")
        return None
    
    pyd_file = pyd_files[0]
    pyd_name = os.path.splitext(pyd_file)[0]  # 例如: step_exporter
    
    print(f"[STEP EXPORTER] 找到C++扩展: {pyd_file}")
    print(f"[STEP EXPORTER] 尝试导入模块: {pyd_name}")
    
    try:
        # 使用标准导入
        module = __import__(pyd_name)
        _cpp_extension = module
        _cpp_extension_loaded = True
        
        print(f"[STEP EXPORTER] C++扩展加载成功: {pyd_name}")
        
        # 验证函数
        if hasattr(_cpp_extension, 'export_step'):
            print("[STEP EXPORTER] ✓ 找到 export_step 函数")
        else:
            print("[STEP EXPORTER] ✗ 未找到 export_step 函数")
            
        if hasattr(_cpp_extension, 'get_version'):
            print("[STEP EXPORTER] ✓ 找到 get_version 函数")
        else:
            print("[STEP EXPORTER] ✗ 未找到 get_version 函数")
        
        return _cpp_extension
        
    except ImportError as e:
        _cpp_extension_error = f"导入错误: {e}"
        print(f"[STEP EXPORTER ERROR] 导入C++扩展失败: {e}")
        return None
    except Exception as e:
        _cpp_extension_error = f"意外错误: {e}"
        print(f"[STEP EXPORTER ERROR] 加载C++扩展时发生意外错误: {e}")
        traceback.print_exc()
        return None

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
        
        cpp_ext = get_cpp_extension()
        if cpp_ext:
            box.label(text="✓ C++扩展已加载", icon='CHECKMARK')
            
            # 显示版本信息
            if hasattr(cpp_ext, 'get_version'):
                try:
                    version = cpp_ext.get_version()
                    box.label(text=f"版本: {version}")
                except:
                    box.label(text="版本: 未知")
        else:
            box.label(text="✗ C++扩展不可用", icon='ERROR')
            if _cpp_extension_error:
                box.label(text=f"错误: {_cpp_extension_error[:50]}...", icon='CANCEL')
        
        # 导出设置
        box = layout.box()
        box.label(text="导出设置", icon='SETTINGS')
        box.prop(self, "use_selected")
        box.prop(self, "scale")
    
    def execute(self, context):
        """执行导出操作"""
        # 获取C++扩展模块
        cpp_ext = get_cpp_extension()
        
        if cpp_ext is None:
            self.report({'ERROR'}, "无法加载STEP导出器C++扩展")
            if _cpp_extension_error:
                self.report({'ERROR'}, f"错误: {_cpp_extension_error}")
            return {'CANCELLED'}
        
        if not hasattr(cpp_ext, 'export_step'):
            self.report({'ERROR'}, "C++扩展缺少export_step函数")
            return {'CANCELLED'}
        
        # 导出文件
        try:
            result = cpp_ext.export_step(self.filepath)
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
    cpp_ext = get_cpp_extension()
    if cpp_ext:
        print("[STEP EXPORTER] 插件注册成功")
    else:
        print("[STEP EXPORTER WARNING] 插件已注册，但C++扩展未加载")

def unregister():
    """注销插件"""
    bpy.utils.unregister_class(STEP_EXPORTER_OT_export)
    bpy.types.TOPBAR_MT_file_export.remove(menu_func_export)
    
    # 清理C++扩展引用
    global _cpp_extension, _cpp_extension_loaded, _cpp_extension_error
    _cpp_extension = None
    _cpp_extension_loaded = False
    _cpp_extension_error = None
    print("[STEP EXPORTER] 插件已注销")

if __name__ == "__main__":
    register()
'''
    
    with open(init_file, 'w', encoding='utf-8') as f:
        f.write(init_content)
    
    print(f"   [OK] 创建插件主文件: {init_file.relative_to(project_dir)}")
    
    # 6. 创建测试脚本
    print("\n6. 创建测试脚本...")
    
    test_script = plugin_dir / "test_vscode_setup.py"
    test_content = '''"""
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
print("\\n1. 检查插件目录...")
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
print("\\n2. 测试C++扩展加载...")

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
print("\\n3. 检查Blender插件状态...")

# 检查插件是否注册
if hasattr(bpy.types, 'STEP_EXPORTER_OT_export'):
    print("   [OK] STEP导出器操作符已注册")
else:
    print("   [WARNING] STEP导出器操作符未注册")

# 检查菜单
print("\\n4. 测试菜单...")
print("   请在文件菜单中检查是否有'导出 > STEP (.step)'选项")

print("\\n" + "=" * 60)
print("测试完成!")
print("=" * 60)
'''
    
    with open(test_script, 'w', encoding='utf-8') as f:
        f.write(test_content)
    
    print(f"   [OK] 创建测试脚本: {test_script.relative_to(project_dir)}")
    
    # 7. 创建配置文件
    print("\n7. 创建配置文件...")
    
    # 创建 .vscode 目录
    vscode_dir = project_dir / ".vscode"
    vscode_dir.mkdir(exist_ok=True)
    
    # 创建 settings.json
    settings_file = vscode_dir / "settings.json"
    settings_content = '''{
    // VSCode Blender 插件配置
    "blender.executable": "C:\\\\Program Files\\\\Blender Foundation\\\\Blender\\\\blender.exe",
    "blender.pythonPath": "C:\\\\Python311\\\\python.exe",
    "blender.addonsDir": "step_exporter",
    
    // 调试配置
    "blender.debugAdapter.enabled": true,
    "blender.debugAdapter.host": "localhost",
    "blender.debugAdapter.port": 5678,
    
    // Python配置
    "python.defaultInterpreterPath": "C:\\\\Python311\\\\python.exe",
    "python.analysis.extraPaths": [
        "./step_exporter/lib"
    ]
}
'''
    
    with open(settings_file, 'w', encoding='utf-8') as f:
        f.write(settings_content)
    
    print(f"   [OK] 创建VSCode设置文件: {settings_file.relative_to(project_dir)}")
    
    # 8. 验证部署
    print("\n8. 验证部署...")
    
    # 检查目录结构
    print("   项目插件目录结构:")
    for root, dirs, files in os.walk(plugin_dir):
        level = root.replace(str(plugin_dir), '').count(os.sep)
        indent = '  ' * level
        rel_path = os.path.relpath(root, plugin_dir)
        if rel_path == '.':
            rel_path = plugin_dir.name
        
        print(f"    {indent}{rel_path}/")
        
        subindent = '  ' * (level + 1)
        for file in files:
            if file.endswith(('.py', '.pyd', '.dll')):
                file_size = os.path.getsize(os.path.join(root, file))
                print(f"    {subindent}{file} ({file_size:,} 字节)")
    
    # 测试C++扩展
    print("\n   测试C++扩展加载...")
    
    # 保存当前状态
    original_cwd = os.getcwd()
    original_path = os.environ.get('PATH', '')
    original_sys_path = sys.path.copy()
    
    try:
        # 切换到插件目录
        os.chdir(lib_dir)
        
        # 设置DLL搜索路径
        os.environ['PATH'] = str(lib_dir) + ';' + original_path
        sys.path.insert(0, str(lib_dir))
        
        # 查找.pyd文件
        pyd_files = [f for f in os.listdir('.') if f.lower().endswith('.pyd')]
        if pyd_files:
            pyd_name = os.path.splitext(pyd_files[0])[0]
            
            try:
                module = __import__(pyd_name)
                print(f"    [SUCCESS] C++扩展加载成功: {pyd_name}")
                
                if hasattr(module, 'get_version'):
                    try:
                        version = module.get_version()
                        print(f"        版本: {version}")
                    except:
                        pass
                
                if hasattr(module, 'export_step'):
                    print("        找到 export_step 函数")
                
            except ImportError as e:
                print(f"    [ERROR] 加载失败: {e}")
            except Exception as e:
                print(f"    [ERROR] 意外错误: {e}")
        else:
            print("    [ERROR] 未找到.pyd文件")
            
    finally:
        # 恢复原始状态
        os.chdir(original_cwd)
        os.environ['PATH'] = original_path
        sys.path = original_sys_path
    
    # 9. 完成部署
    print("\n" + "=" * 60)
    print("部署完成!")
    print("=" * 60)
    print()
    print("下一步操作:")
    print("1. 在VSCode中打开项目目录:", project_dir)
    print("2. 确保已安装 'Blender Development' 扩展")
    print("3. 在VSCode中按下 F5 启动Blender调试")
    print("4. 在Blender中启用插件: 编辑 > 偏好设置 > 插件")
    print("5. 搜索 'STEP Exporter' 并启用")
    print("6. 在VSCode中运行测试脚本:", test_script.relative_to(project_dir))
    print()
    print("目录结构:")
    print(f"  {project_dir.name}/")
    print(f"    ├── step_exporter/           # 插件目录 (VSCode Blender插件会链接此目录)")
    print(f"    │   ├── __init__.py         # 插件主文件")
    print(f"    │   ├── lib/                # C++扩展和DLL")
    print(f"    │   │   ├── *.pyd           # C++扩展模块")
    print(f"    │   │   └── *.dll           # 依赖DLL")
    print(f"    │   └── test_vscode_setup.py # 测试脚本")
    print(f"    ├── .vscode/                # VSCode配置")
    print(f"    │   └── settings.json       # 插件配置")
    print(f"    └── ...其他项目文件...")
    print()
    print("VSCode Blender 插件会自动将 'step_exporter' 目录链接到 Blender 的 addons 目录。")
    print("您对插件代码的修改会实时反映在Blender中。")
    
    return True

if __name__ == "__main__":
    try:
        success = deploy_for_vscode_blender()
        if success:
            sys.exit(0)
        else:
            sys.exit(1)
    except KeyboardInterrupt:
        print("\n\n部署被用户中断")
        sys.exit(1)
    except Exception as e:
        print(f"\n[ERROR] 部署失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
