"""Cylinder panel."""
import bpy
from bpy.types import Panel
from ..core.i18n import _t

class STEP_EXPORTER_PT_cylinder_panel(Panel):
    """参数化圆柱生成面板"""
    bl_label = _t("Parametric Cylinder")
    bl_idname = "STEP_EXPORTER_PT_cylinder_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = _t("STEP Export")
    bl_parent_id = "STEP_EXPORTER_PT_main_panel"
    bl_options = {'DEFAULT_CLOSED'}
    
    def draw(self, context):
        layout = self.layout
        layout.operator("step_exporter.create_parametric_cylinder", text=_t("Generate Cylinder"), icon='MESH_CYLINDER')


# ====================== 注册与注销 ======================

