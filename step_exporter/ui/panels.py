"""UI panels."""
import bpy
from bpy.types import Panel
from ..core import _globals as _g

def menu_func_export_enhanced(self, context):
    self.layout.operator(STEP_EXPORTER_OT_export_enhanced.bl_idname, text="STEP Enhanced (.step)")

# ====================== 面板类 ======================

class STEP_EXPORTER_PT_main_panel(Panel):
    bl_label = "STEP Exporter"
    bl_idname = "STEP_EXPORTER_PT_main_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "STEP Export"
    
    def draw(self, context):
        layout = self.layout
        
        # 状态显示
        box = layout.box()
        box.label(text="Module Status", icon='INFO')
        
        if _g.CPP_MODULE_LOADED and _g.step_exporter:
            try:
                version = _g.step_exporter.get_version()
                box.label(text=f"✓ Module v{version} loaded", icon='CHECKMARK')
                oc_ver = _g.step_exporter.get_occt_version() if hasattr(_g.step_exporter, 'get_occt_version') else "7.7.2"
                box.label(text=f"✓ OpenCASCADE {oc_ver} ready", icon='CHECKMARK')
            except:
                box.label(text="✓ C++ module loaded", icon='CHECKMARK')
        else:
            box.label(text="✗ C++ extension not loaded", icon='ERROR')
            box.label(text="Check system console", icon='ERROR')
        
        # 快速导出按钮
        layout.separator()
        if _g.CPP_MODULE_LOADED:
            col = layout.column(align=True)
            col.operator("export_scene.step_enhanced", text="Quick Export (Enhanced)", icon='EXPORT')
        else:
            box = layout.box()
            box.label(text="C++ module required", icon='ERROR')
            box.label(text="Compile and install first")
        
        # 样品生成
        layout.separator()
        layout.label(text="Sample Generators", icon='MESH_DATA')
        col = layout.column(align=True)
        col.operator("step_exporter.create_top_shell", text="Create Top Shell", icon='MESH_PLANE')
        col.operator("step_exporter.create_bottom_shell", text="Create Bottom Shell", icon='MESH_PLANE')
        col.operator("step_exporter.create_cylinder", text="Create Cylinder", icon='MESH_CYLINDER')

# ====================== 样品生成 Operators ======================

