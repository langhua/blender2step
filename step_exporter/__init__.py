"""
STEP Exporter for Blender (Enhanced)
Version 4.1.0 with advanced BREP and solid creation support
"""

bl_info = {
    "name": "STEP Exporter (Enhanced)",
    "author": "Blender STEP Exporter",
    "version": (4, 1, 0),
    "blender": (3, 0, 0),
    "location": "File > Export > STEP (Enhanced)",
    "description": "Export to STEP format with advanced BREP, solid creation and geometry fixing",
    "category": "Import-Export",
}

import bpy
import sys
import os
from bpy.types import Operator, Panel
from bpy_extras.io_utils import ExportHelper
from bpy.props import StringProperty, FloatProperty, BoolProperty, EnumProperty

# ====================== C++ 模块加载检查 ======================

# 初始化模块状态变量
CPP_MODULE_LOADED = False
step_exporter = None
MODULE_LOAD_ERROR = ""

# 尝试加载 C++ 扩展模块
try:
    # 显式添加当前脚本所在目录到 Python 路径
    script_dir = os.path.dirname(os.path.realpath(__file__))
    if script_dir not in sys.path:
        sys.path.insert(0, script_dir)
    
    # 尝试导入 _step_exporter 模块
    import _step_exporter
    step_exporter = _step_exporter
    
    # 验证模块功能
    if hasattr(step_exporter, 'get_version'):
        module_version = step_exporter.get_version()
        print(f"[STEP Exporter] ✓ C++ extension module loaded successfully (direct import)")
        print(f"[STEP Exporter] Module version: {module_version}")
        CPP_MODULE_LOADED = True
    else:
        MODULE_LOAD_ERROR = "C++ module missing required functions"
        print(f"[STEP Exporter] ✗ C++ module loaded but missing functions")
        
except ImportError as e:
    MODULE_LOAD_ERROR = f"ImportError: {str(e)}"
    print(f"[STEP Exporter] ✗ Failed to import C++ module directly: {e}")
    
    # 尝试从 lib 子目录导入
    try:
        lib_path = os.path.join(script_dir, "lib")
        if os.path.exists(lib_path) and lib_path not in sys.path:
            sys.path.insert(0, lib_path)
            import _step_exporter as step_exporter_lib
            step_exporter = step_exporter_lib
            
            if hasattr(step_exporter, 'get_version'):
                module_version = step_exporter.get_version()
                print(f"[STEP Exporter] ✓ C++ extension module loaded successfully (from lib)")
                print(f"[STEP Exporter] Module version: {module_version}")
                CPP_MODULE_LOADED = True
            else:
                MODULE_LOAD_ERROR = "C++ module from lib missing required functions"
                print(f"[STEP Exporter] ✗ C++ module from lib missing functions")
                
    except ImportError as e2:
        MODULE_LOAD_ERROR = f"ImportError from lib: {str(e2)}"
        print(f"[STEP Exporter] ✗ Failed to import C++ module from lib: {e2}")
        
except Exception as e:
    MODULE_LOAD_ERROR = f"Unexpected error: {str(e)}"
    print(f"[STEP Exporter] ✗ Unexpected error loading C++ module: {e}")

# ====================== 导出操作类 ======================

class STEP_EXPORTER_OT_export_enhanced(Operator, ExportHelper):
    """Export to STEP format with advanced BREP and solid creation"""
    bl_idname = "export_scene.step_enhanced"
    bl_label = "Export STEP (Enhanced)"
    bl_description = "Export to STEP format with advanced BREP representation"
    bl_options = {'PRESET', 'UNDO'}
    
    filename_ext = ".step"
    filter_glob: StringProperty(
        default="*.step;*.stp",
        options={'HIDDEN'},
    )
    
    # 基本参数
    scale: FloatProperty(
        name="Scale",
        description="Scale factor for export (Blender units to mm)",
        default=0.001,  # 米到毫米转换
        min=0.000001,
        max=10000.0,
        precision=6,
    )
    
    fix_geometry: BoolProperty(
        name="Fix Geometry",
        description="Enable geometry fixing (repair gaps, small edges, etc.)",
        default=True,
    )
    
    # 高级 BREP 参数
    create_solid: BoolProperty(
        name="Create Solid",
        description="Attempt to create solid bodies instead of surfaces. Yields better compatibility with CAD software",
        default=True,
    )
    
    advanced_brep: BoolProperty(
        name="Advanced BREP",
        description="Use advanced BREP representation (includes PCURVE, parametric surfaces). Recommended for best compatibility",
        default=True,
    )
    
    step_schema: EnumProperty(
        name="STEP Schema",
        description="STEP application protocol",
        items=[
            ('AP214', "AP214", "ISO 10303-214: Core data for automotive mechanical design processes (supports colors and layers)"),
            ('AP203', "AP203", "ISO 10303-203: Configuration controlled 3D designs of mechanical parts and assemblies (widely supported)"),
            ('AP242', "AP242", "ISO 10303-242: Managed model-based 3D engineering (most modern)"),
        ],
        default='AP214',
    )
    
    sew_tolerance: FloatProperty(
        name="Sewing Tolerance",
        description="Tolerance for sewing faces together (in mm). Smaller values = more precise but slower",
        default=0.01,
        min=0.0001,
        max=1.0,
        precision=4,
        subtype='DISTANCE',
    )
    
    use_selected: BoolProperty(
        name="Selected Only",
        description="Export only selected objects",
        default=False,
    )
    
    apply_modifiers: BoolProperty(
        name="Apply Modifiers",
        description="Apply all modifiers before export",
        default=True,
    )
    
    def draw(self, context):
        layout = self.layout
        
        # 状态信息
        box = layout.box()
        box.label(text="Module Status", icon='INFO')
        if CPP_MODULE_LOADED:
            try:
                version = step_exporter.get_version()
                box.label(text=f"✓ Module v{version} loaded", icon='CHECKMARK')
            except:
                box.label(text="✓ C++ module loaded", icon='CHECKMARK')
        else:
            box.label(text="✗ C++ extension not loaded", icon='ERROR')
            if MODULE_LOAD_ERROR:
                box.label(text=f"Error: {MODULE_LOAD_ERROR[:50]}...", icon='ERROR')
            box.label(text="Check system console for details", icon='ERROR')
        
        # 基本设置
        box = layout.box()
        box.label(text="Basic Settings", icon='SETTINGS')
        box.prop(self, "scale")
        box.prop(self, "fix_geometry")
        box.prop(self, "use_selected")
        box.prop(self, "apply_modifiers")
        
        # 高级 BREP 设置
        box = layout.box()
        box.label(text="Advanced BREP & Solid Creation", icon='MOD_SOLIDIFY')
        box.prop(self, "create_solid")
        box.prop(self, "advanced_brep")
        
        # 只有当 advanced_brep 启用时才显示这些选项
        if self.advanced_brep:
            box.prop(self, "step_schema")
            box.prop(self, "sew_tolerance")
        
        # 导出按钮
        layout.separator()
        row = layout.row()
        row.scale_y = 2.0
        if CPP_MODULE_LOADED:
            row.operator("export_scene.step_enhanced", text="Export STEP (Enhanced)", icon='EXPORT')
        else:
            row.enabled = False
            row.operator("export_scene.step_enhanced", text="C++ Module Not Loaded", icon='CANCEL')
    
    def execute(self, context):
        if not CPP_MODULE_LOADED:
            self.report({'ERROR'}, "C++ extension module '_step_exporter' not loaded. Check console for details.")
            return {'CANCELLED'}
        
        # 收集要导出的对象
        objects_data = []
        
        # 确定要导出的对象列表
        if self.use_selected and context.selected_objects:
            export_objects = [obj for obj in context.selected_objects if obj.type == 'MESH']
        else:
            export_objects = [obj for obj in context.scene.objects if obj.type == 'MESH']
        
        if not export_objects:
            self.report({'ERROR'}, "No mesh objects found to export.")
            return {'CANCELLED'}
        
        print(f"\n[STEP Exporter] Starting enhanced export of {len(export_objects)} objects...")
        print(f"[STEP Exporter] Parameters: Scale={self.scale}, FixGeometry={self.fix_geometry}, CreateSolid={self.create_solid}, AdvancedBREP={self.advanced_brep}")
        
        for obj in export_objects:
            mesh_data = self.get_mesh_data_enhanced(obj, context, self.scale, self.apply_modifiers)
            if mesh_data:
                objects_data.append(mesh_data)
        
        if not objects_data:
            self.report({'ERROR'}, "No valid mesh data to export.")
            return {'CANCELLED'}
        
        try:
            # 调用 C++ 增强版导出函数
            success = step_exporter.export_scene_enhanced(
                self.filepath,
                objects_data,
                self.scale,
                1 if self.fix_geometry else 0,
                1 if self.create_solid else 0,
                1 if self.advanced_brep else 0
            )
            
            if success:
                self.report({'INFO'}, f"Successfully exported {len(objects_data)} object(s) to {self.filepath}")
                return {'FINISHED'}
            else:
                self.report({'ERROR'}, "Export failed. Check the System Console (Window > Toggle System Console) for details.")
                return {'CANCELLED'}
                
        except Exception as e:
            error_msg = str(e)
            self.report({'ERROR'}, f"Export error: {error_msg[:100]}")
            import traceback
            traceback.print_exc()
            return {'CANCELLED'}
    
    def get_mesh_data_enhanced(self, obj, context, scale, apply_modifiers=True):
        """获取网格数据（增强版，包含更多检查和信息）"""
        if obj.type != 'MESH':
            return None
        
        mesh = obj.data
        
        # 获取最终几何（应用修改器）
        depsgraph = context.evaluated_depsgraph_get() if apply_modifiers else None
        if depsgraph:
            eval_obj = obj.evaluated_get(depsgraph)
            eval_mesh = eval_obj.data
        else:
            eval_obj = obj
            eval_mesh = mesh
        
        # 确保是三角网格
        if not eval_mesh.loop_triangles:
            eval_mesh.calc_loop_triangles()
        
        # 获取顶点（应用世界变换）
        vertices = []
        for vert in eval_mesh.vertices:
            world_co = eval_obj.matrix_world @ vert.co
            vertices.append([world_co.x * scale, world_co.y * scale, world_co.z * scale])
        
        # 获取三角面
        faces = []
        for tri in eval_mesh.loop_triangles:
            face_indices = list(tri.vertices)
            if len(face_indices) >= 3:
                faces.append(face_indices)
        
        # 简单的流形检查
        if len(vertices) == 0 or len(faces) == 0:
            print(f"[Python] Skipping object '{obj.name}': no valid geometry.")
            return None
        
        print(f"[Python] Prepared '{obj.name}': {len(vertices)} vertices, {len(faces)} faces")
        
        return {
            'name': obj.name,
            'vertices': vertices,
            'faces': faces
        }

# ====================== 旧版导出操作类（保持兼容性） ======================

class STEP_EXPORTER_OT_export_legacy(Operator, ExportHelper):
    """Export to STEP format (Legacy version)"""
    bl_idname = "export_scene.step_legacy"
    bl_label = "Export STEP (Legacy)"
    bl_description = "Export to STEP format using legacy method"
    bl_options = {'PRESET'}
    
    filename_ext = ".step"
    filter_glob: StringProperty(
        default="*.step;*.stp",
        options={'HIDDEN'},
    )
    
    scale: FloatProperty(
        name="Scale",
        description="Scale factor for export",
        default=0.001,
        min=0.000001,
        max=10000.0,
        precision=6,
    )
    
    fix_geometry: BoolProperty(
        name="Fix Geometry",
        description="Enable geometry fixing",
        default=True,
    )
    
    def execute(self, context):
        if not CPP_MODULE_LOADED:
            self.report({'ERROR'}, "C++ extension module not loaded.")
            return {'CANCELLED'}
        
        # 收集所有网格对象
        objects_data = []
        for obj in context.scene.objects:
            if obj.type == 'MESH':
                mesh_data = self.get_mesh_data(obj, self.scale)
                if mesh_data:
                    objects_data.append(mesh_data)
        
        if not objects_data:
            self.report({'ERROR'}, "No mesh objects found.")
            return {'CANCELLED'}
        
        try:
            success = step_exporter.export_scene(
                self.filepath,
                objects_data,
                self.scale,
                1 if self.fix_geometry else 0
            )
            
            if success:
                self.report({'INFO'}, f"Exported {len(objects_data)} object(s)")
                return {'FINISHED'}
            else:
                self.report({'ERROR'}, "Export failed.")
                return {'CANCELLED'}
                
        except Exception as e:
            self.report({'ERROR'}, f"Error: {str(e)[:100]}")
            return {'CANCELLED'}
    
    def get_mesh_data(self, obj, scale):
        """获取网格数据（简化版）"""
        if obj.type != 'MESH':
            return None
        
        mesh = obj.data
        if not mesh.loop_triangles:
            mesh.calc_loop_triangles()
        
        vertices = []
        for vert in mesh.vertices:
            world_co = obj.matrix_world @ vert.co
            vertices.append([world_co.x * scale, world_co.y * scale, world_co.z * scale])
        
        faces = []
        for tri in mesh.loop_triangles:
            faces.append(list(tri.vertices))
        
        if len(vertices) == 0 or len(faces) == 0:
            return None
        
        return {
            'name': obj.name,
            'vertices': vertices,
            'faces': faces
        }

# ====================== 菜单函数 ======================

def menu_func_export_enhanced(self, context):
    self.layout.operator(STEP_EXPORTER_OT_export_enhanced.bl_idname, text="STEP Enhanced (.step)")

def menu_func_export_legacy(self, context):
    self.layout.operator(STEP_EXPORTER_OT_export_legacy.bl_idname, text="STEP Legacy (.step)")

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
        
        if CPP_MODULE_LOADED:
            try:
                version = step_exporter.get_version()
                box.label(text=f"✓ Module v{version} loaded", icon='CHECKMARK')
                box.label(text=f"✓ OpenCASCADE 7.7.2 ready", icon='CHECKMARK')
            except:
                box.label(text="✓ C++ module loaded", icon='CHECKMARK')
        else:
            box.label(text="✗ C++ extension not loaded", icon='ERROR')
            box.label(text="Check system console", icon='ERROR')
        
        # 快速导出按钮
        layout.separator()
        if CPP_MODULE_LOADED:
            col = layout.column(align=True)
            col.operator("export_scene.step_enhanced", text="Quick Export (Enhanced)", icon='EXPORT')
            col.operator("export_scene.step_legacy", text="Quick Export (Legacy)", icon='EXPORT')
        else:
            box = layout.box()
            box.label(text="C++ module required", icon='ERROR')
            box.label(text="Compile and install first")

# ====================== 注册与注销 ======================

classes = [
    STEP_EXPORTER_OT_export_enhanced,
    STEP_EXPORTER_OT_export_legacy,
    STEP_EXPORTER_PT_main_panel,
]

def register():
    # 注册所有类
    for cls in classes:
        bpy.utils.register_class(cls)
    
    # 添加到导出菜单
    bpy.types.TOPBAR_MT_file_export.append(menu_func_export_enhanced)
    bpy.types.TOPBAR_MT_file_export.append(menu_func_export_legacy)
    
    print("[STEP Exporter] Enhanced plugin registered successfully")

def unregister():
    # 从导出菜单移除
    bpy.types.TOPBAR_MT_file_export.remove(menu_func_export_enhanced)
    bpy.types.TOPBAR_MT_file_export.remove(menu_func_export_legacy)
    
    # 注销所有类
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    
    print("[STEP Exporter] Plugin unregistered")

# 直接运行时的测试
if __name__ == "__main__":
    # 清理之前的注册（如果存在）
    try:
        unregister()
    except:
        pass
    
    # 重新注册
    register()