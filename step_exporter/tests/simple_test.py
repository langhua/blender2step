"""
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
