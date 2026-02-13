"""
STEP Exporter for Blender
Export 3D models to STEP format using OpenCASCADE
"""

bl_info = {
    "name": "STEP Exporter",
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

# 插件注册状态
_plugin_registered = False
_plugin_menu_item_added = False

def load_cpp_module_safe():
    """安全加载C++扩展模块，处理符号链接和路径问题"""
    global _cpp_module, _cpp_module_loaded, _cpp_module_error
    
    if _cpp_module_loaded:
        return _cpp_module
    
    if _cpp_module_error is not None:
        return None
    
    # 获取插件目录 - 使用绝对路径并解析符号链接
    try:
        # 首先获取当前文件的真实路径（解析符号链接）
        current_file = os.path.abspath(__file__)
        
        # 尝试解析符号链接
        if hasattr(os.path, 'readlink'):
            try:
                real_path = os.path.realpath(current_file)
                if real_path != current_file:
                    current_file = real_path
            except:
                pass
        
        plugin_dir = os.path.dirname(current_file)
    except Exception as e:
        _cpp_module_error = f"获取插件目录失败: {e}"
        print(f"[STEP EXPORTER ERROR] {_cpp_module_error}")
        return None
    
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
        "step_exporter",      # 原始名称
        "_step_exporter",     # 带下划线
        "step_exporter_cpp",  # 带_cpp后缀
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
    ) # type: ignore
    
    use_selected: BoolProperty(
        name="仅导出选中对象",
        description="仅导出选中的对象",
        default=False,
    ) # type: ignore
    
    scale: FloatProperty(
        name="缩放比例",
        description="导出缩放比例",
        default=1.0,
        min=0.001,
        max=1000.0,
    ) # type: ignore
    
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
    # 检查是否已经添加了菜单项
    if not _plugin_menu_item_added:
        return
    
    # 添加菜单项
    self.layout.operator(STEP_EXPORTER_OT_export.bl_idname, text="STEP (.step)")

def register():
    """注册插件 - 防止重复注册"""
    global _plugin_registered, _plugin_menu_item_added
    
    if _plugin_registered:
        print("[STEP EXPORTER] 插件已经注册，跳过重复注册")
        return
    
    try:
        # 首先尝试取消注册，以防之前有残留
        try:
            bpy.utils.unregister_class(STEP_EXPORTER_OT_export)
            print("[STEP EXPORTER] 清理了之前的注册")
        except:
            pass
        
        # 注册操作符
        bpy.utils.register_class(STEP_EXPORTER_OT_export)
        _plugin_registered = True
        
        # 从导出菜单中移除可能存在的重复项
        try:
            bpy.types.TOPBAR_MT_file_export.remove(menu_func_export)
        except:
            pass
        
        # 添加菜单项
        bpy.types.TOPBAR_MT_file_export.append(menu_func_export)
        _plugin_menu_item_added = True
        
        # 预加载C++扩展
        cpp_module = get_cpp_module()
        if cpp_module:
            print("[STEP EXPORTER] 插件注册成功")
        else:
            print("[STEP EXPORTER WARNING] 插件已注册，但C++扩展未加载")
            
    except Exception as e:
        print(f"[STEP EXPORTER ERROR] 注册插件时出错: {e}")
        traceback.print_exc()
        _plugin_registered = False
        _plugin_menu_item_added = False

def unregister():
    """注销插件"""
    global _plugin_registered, _plugin_menu_item_added
    
    try:
        # 从菜单中移除菜单项
        if _plugin_menu_item_added:
            try:
                bpy.types.TOPBAR_MT_file_export.remove(menu_func_export)
            except:
                pass
            _plugin_menu_item_added = False
        
        # 注销操作符
        if _plugin_registered:
            bpy.utils.unregister_class(STEP_EXPORTER_OT_export)
            _plugin_registered = False
        
        # 清理C++扩展引用
        global _cpp_module, _cpp_module_loaded, _cpp_module_error
        _cpp_module = None
        _cpp_module_loaded = False
        _cpp_module_error = None
        
        print("[STEP EXPORTER] 插件已注销")
        
    except Exception as e:
        print(f"[STEP EXPORTER ERROR] 注销插件时出错: {e}")
        traceback.print_exc()

# 检查是否重复加载
if __name__ in locals() or __name__ in sys.modules:
    print(f"[STEP EXPORTER WARNING] 检测到可能的重复加载: {__name__}")
    
    # 尝试清理旧的注册
    try:
        unregister()
    except:
        pass

if __name__ == "__main__":
    register()