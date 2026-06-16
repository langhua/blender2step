"""Sample geometry operators."""
import sys, os
import bpy
from bpy.types import Operator

class STEP_EXPORTER_OT_create_top_shell(Operator):
    """创建带开窗的塑料顶壳样品"""
    bl_idname = "step_exporter.create_top_shell"
    bl_label = "Create Top Shell"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        script_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'test', 'create_top_shell.py')
        exec(compile(open(script_path).read(), script_path, 'exec'), {'__name__': '__main__', '__file__': script_path})
        self.report({'INFO'}, "Top shell created")
        return {'FINISHED'}


class STEP_EXPORTER_OT_create_bottom_shell(Operator):
    """创建带螺栓孔的塑料底壳样品"""
    bl_idname = "step_exporter.create_bottom_shell"
    bl_label = "Create Bottom Shell"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        script_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'test', 'create_bottom_shell.py')
        old_argv = sys.argv
        try:
            sys.argv = [sys.argv[0] if len(sys.argv) > 0 else "", "with_holes"]
            exec(compile(open(script_path).read(), script_path, 'exec'), {'__name__': '__main__'})
        finally:
            sys.argv = old_argv
        self.report({'INFO'}, "Bottom shell created")
        return {'FINISHED'}


class STEP_EXPORTER_OT_create_cylinder(Operator):
    """创建机械圆柱体样品"""
    bl_idname = "step_exporter.create_cylinder"
    bl_label = "Create Cylinder"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        script_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'test', 'create_mesh_cylinder.py')
        exec(compile(open(script_path).read(), script_path, 'exec'), {'__name__': '__main__', '__file__': script_path})
        self.report({'INFO'}, "Cylinder created")
        return {'FINISHED'}


# ====================== 参数化圆柱生成 Operator ======================

