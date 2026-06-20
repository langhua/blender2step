"""UI panels."""
import bpy
from bpy.types import Panel
from ..core import _globals as _g
from .export_operator import STEP_EXPORTER_OT_export_enhanced

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

# ====================== Sample Generators 子面板 ======================

class STEP_EXPORTER_PT_sample_generators(Panel):
    bl_label = "Sample Generators"
    bl_idname = "STEP_EXPORTER_PT_sample_generators"
    bl_parent_id = "STEP_EXPORTER_PT_main_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "STEP Export"
    bl_order = 1  # 放在 Cylinder Panel 下面
    
    def draw(self, context):
        layout = self.layout
        # 注意：通过 bl_parent_id 嵌套时，不用 self.layout 直接放子项
        # 子面板已自带折叠箭头
        col = layout.column(align=True)
        col.operator("step_exporter.create_top_shell", text="Top Shell", icon='MESH_PLANE')
        col.operator("step_exporter.create_bottom_shell", text="Bottom Shell", icon='MESH_PLANE')
        col.operator("step_exporter.create_cylinder", text="Cylinder", icon='MESH_CYLINDER')
        col.operator("step_exporter.create_cylinder_gallery", text="Cylinder Gallery", icon='MESH_CYLINDER')
        col.operator("step_exporter.create_cone_gallery", text="Cone Gallery △", icon='MESH_CONE')
        col.operator("step_exporter.create_cone_gallery_inverted", text="Cone Gallery ▽", icon='MESH_CONE')

# ====================== 样品生成 Operators ======================

