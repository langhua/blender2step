"""Parametric model panel."""
import bpy
from bpy.types import Panel
from ..core.i18n import _t

class STEP_EXPORTER_PT_cylinder_panel(Panel):
    """参数化模型生成面板"""
    bl_label = _t("Parametric Model")
    bl_idname = "STEP_EXPORTER_PT_cylinder_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = _t("STEP Export")
    bl_parent_id = "STEP_EXPORTER_PT_main_panel"
    
    def draw(self, context):
        layout = self.layout
        layout.operator("step_exporter.create_parametric_cylinder", text=_t("Generate Cylinder"), icon='MESH_CYLINDER')
        layout.operator("step_exporter.create_parametric_shell", text=_t("Generate Shell"), icon='MESH_CUBE')
        layout.separator()
        layout.operator("step_exporter.add_hole_to_shell", text=_t("Add Hole to Shell"), icon='MOD_BOOLEAN')


# ====================== 注册与注销 ======================

