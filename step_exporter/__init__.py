"""
STEP Exporter for Blender
Version 4.0.0 with geometry fixing
"""

bl_info = {
    "name": "STEP Exporter (Fixed)",
    "author": "Your Name",
    "version": (4, 0, 0),
    "blender": (3, 0, 0),
    "location": "File > Export > STEP (Fixed)",
    "description": "Export to STEP format with geometry fixing",
    "category": "Import-Export",
}

import bpy
import sys
import os
from bpy.types import Operator
from bpy_extras.io_utils import ExportHelper
from bpy.props import StringProperty, FloatProperty, BoolProperty

# 确保可以导入C++扩展
plugin_dir = os.path.dirname(__file__)
lib_dir = os.path.join(plugin_dir, "lib")
if lib_dir not in sys.path:
    sys.path.insert(0, lib_dir)

try:
    # 尝试直接导入 _step_exporter
    import _step_exporter
    # 如果直接导入成功，创建一个别名以便使用
    step_exporter = _step_exporter
    CPP_MODULE_LOADED = True
    print("✓ STEP Exporter C++ module loaded successfully (direct import)")
except ImportError as e:
    print(f"✗ Failed to load C++ module (direct import): {e}")
    
    # 尝试从lib目录导入
    try:
        import sys
        import os
        plugin_dir = os.path.dirname(__file__)
        lib_dir = os.path.join(plugin_dir, "lib")
        
        if lib_dir not in sys.path:
            sys.path.insert(0, lib_dir)
        
        import _step_exporter
        step_exporter = _step_exporter
        CPP_MODULE_LOADED = True
        print("✓ STEP Exporter C++ module loaded successfully (from lib)")
    except ImportError as e2:
        CPP_MODULE_LOADED = False
        print(f"✗ Failed to load C++ module (from lib): {e2}")

class STEP_EXPORTER_OT_export(Operator, ExportHelper):
    """Export to STEP format with geometry fixing"""
    bl_idname = "export.step_fixed"
    bl_label = "Export STEP (Fixed)"
    bl_options = {'PRESET'}
    
    filename_ext = ".step"
    filter_glob: StringProperty(default="*.step;*.stp", options={'HIDDEN'})
    
    scale: FloatProperty(
        name="Scale",
        description="Scale factor for export",
        default=0.001,  # 毫米到米转换
        min=0.0001,
        max=10000.0,
    )
    
    fix_geometry: BoolProperty(
        name="Fix Geometry",
        description="Enable geometry fixing (recommended)",
        default=True,
    )
    
    def execute(self, context):
        if not CPP_MODULE_LOADED:
            self.report({'ERROR'}, "C++ extension not loaded")
            return {'CANCELLED'}
        
        # 收集场景中的网格对象
        objects_data = []
        for obj in context.selected_objects:
            if obj.type == 'MESH':
                mesh_data = get_mesh_data(obj, self.scale)
                if mesh_data:
                    objects_data.append(mesh_data)
        
        if not objects_data:
            self.report({'ERROR'}, "No mesh objects selected")
            return {'CANCELLED'}
        
        try:
            # 调用C++导出函数
            success = step_exporter.export_scene(
                self.filepath,
                objects_data,
                self.scale,
                1 if self.fix_geometry else 0
            )
            
            if success:
                self.report({'INFO'}, f"Exported {len(objects_data)} objects to {self.filepath}")
                return {'FINISHED'}
            else:
                self.report({'ERROR'}, "Export failed - see console for details")
                return {'CANCELLED'}
                
        except Exception as e:
            self.report({'ERROR'}, f"Export error: {str(e)[:100]}")
            return {'CANCELLED'}
    
    def draw(self, context):
        layout = self.layout
        layout.label(text="STEP Export Settings", icon='SETTINGS')
        layout.prop(self, "scale")
        layout.prop(self, "fix_geometry")
        
        if not CPP_MODULE_LOADED:
            layout.label(text="⚠ C++ extension not loaded", icon='ERROR')

def get_mesh_data(obj, scale):
    """获取网格数据"""
    mesh = obj.data
    
    print(f"\n[Python] Getting mesh data for: {obj.name}")
    print(f"[Python]  Vertex count: {len(mesh.vertices)}")
    
    # 确保有三角面数据
    if not mesh.loop_triangles:
        mesh.calc_loop_triangles()
    
    print(f"[Python]  Triangle count: {len(mesh.loop_triangles)}")
    
    # 获取顶点（应用变换矩阵）
    vertices = []
    for i, vert in enumerate(mesh.vertices):
        world_co = obj.matrix_world @ vert.co
        vertices.append([world_co.x, world_co.y, world_co.z])
        
        # 打印前几个顶点的坐标
        if i < 3:
            print(f"[Python]  Vertex {i}: ({world_co.x:.3f}, {world_co.y:.3f}, {world_co.z:.3f})")
    
    # 获取三角面
    faces = []
    for i, tri in enumerate(mesh.loop_triangles):
        face_indices = list(tri.vertices)
        faces.append(face_indices)
        
        # 打印前几个面的索引
        if i < 3:
            print(f"[Python]  Face {i}: vertices {face_indices}")
    
    return {
        'name': obj.name,
        'vertices': vertices,
        'faces': faces
    }

class STEP_EXPORTER_OT_test_simple(Operator):
    """Test with a simple cube"""
    bl_idname = "export.test_simple_cube"
    bl_label = "Test Simple Cube Export"
    
    def execute(self, context):
        if not CPP_MODULE_LOADED or step_exporter is None:
            self.report({'ERROR'}, "C++ extension not loaded")
            return {'CANCELLED'}
        
        import tempfile
        import os
        
        # 创建简单的立方体数据
        cube_vertices = [
            [0, 0, 0], [1, 0, 0], [1, 1, 0], [0, 1, 0],  # 底面
            [0, 0, 1], [1, 0, 1], [1, 1, 1], [0, 1, 1]   # 顶面
        ]
        
        cube_faces = [
            [0, 1, 2, 3],  # 底面
            [4, 5, 6, 7],  # 顶面
            [0, 4, 7, 3],  # 前面
            [1, 5, 6, 2],  # 后面
            [0, 1, 5, 4],  # 左面
            [3, 2, 6, 7]   # 右面
        ]
        
        cube_data = [{
            'name': 'TestCube',
            'vertices': cube_vertices,
            'faces': cube_faces
        }]
        
        # 使用临时文件
        temp_file = os.path.join(tempfile.gettempdir(), "test_cube.step")
        
        try:
            success = step_exporter.export_scene(
                temp_file,
                cube_data,
                1.0,  # scale
                1     # fix_geometry
            )
            
            if success:
                self.report({'INFO'}, f"Test cube exported to: {temp_file}")
                print(f"✓ Test cube exported to: {temp_file}")
                print(f"  File exists: {os.path.exists(temp_file)}")
                if os.path.exists(temp_file):
                    print(f"  File size: {os.path.getsize(temp_file)} bytes")
            else:
                self.report({'ERROR'}, "Test cube export failed")
                
        except Exception as e:
            self.report({'ERROR'}, f"Test error: {str(e)[:100]}")
            import traceback
            traceback.print_exc()
            
        return {'FINISHED'}

def menu_func_export(self, context):
    self.layout.operator(STEP_EXPORTER_OT_export.bl_idname, text="STEP (.step)")

def register():
    bpy.utils.register_class(STEP_EXPORTER_OT_export)
    bpy.utils.register_class(STEP_EXPORTER_OT_test_simple)
    bpy.types.TOPBAR_MT_file_export.append(menu_func_export)

def unregister():
    bpy.utils.unregister_class(STEP_EXPORTER_OT_export)
    bpy.utils.unregister_class(STEP_EXPORTER_OT_test_simple)
    bpy.types.TOPBAR_MT_file_export.remove(menu_func_export)

if __name__ == "__main__":
    register()