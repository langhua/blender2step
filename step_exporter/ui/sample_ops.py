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
        script_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'examples', 'create_top_shell.py')
        exec(compile(open(script_path).read(), script_path, 'exec'), {'__name__': '__main__', '__file__': script_path})
        self.report({'INFO'}, "Top shell created")
        return {'FINISHED'}


class STEP_EXPORTER_OT_create_bottom_shell(Operator):
    """创建带螺栓孔的塑料底壳样品"""
    bl_idname = "step_exporter.create_bottom_shell"
    bl_label = "Create Bottom Shell"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        script_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'examples', 'create_bottom_shell.py')
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
        script_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'examples', 'create_mesh_cylinder.py')
        exec(compile(open(script_path).read(), script_path, 'exec'), {'__name__': '__main__', '__file__': script_path})
        self.report({'INFO'}, "Cylinder created")
        return {'FINISHED'}


class STEP_EXPORTER_OT_create_cylinder_gallery(Operator):
    """创建圆柱体组合样品（不同半径/高度 × 孔洞类型）"""
    bl_idname = "step_exporter.create_cylinder_gallery"
    bl_label = "Create Cylinder Gallery"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        import sys as _sys
        _sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), 'examples'))
        import create_cylinder_gallery
        create_cylinder_gallery.build()
        self.report({'INFO'}, "Cylinder gallery created — 80 items")
        return {'FINISHED'}


class STEP_EXPORTER_OT_create_cone_gallery(Operator):
    """创建锥体组合样品（倒角/圆角/孔）- 正锥形（上细下粗）"""
    bl_idname = "step_exporter.create_cone_gallery"
    bl_label = "Create Cone Gallery"
    bl_options = {'REGISTER', 'UNDO'}

    _timer = None
    _shelf_idx = 0
    _item_idx = 0
    _total = 0
    _done = 0
    _mod = None
    _phase = 0  # 0=creating items, 1=modifiers
    _cones = None  # cones with modifiers to process
    _mod_idx = 0

    def modal(self, context, event):
        if event.type != 'TIMER':
            return {'PASS_THROUGH'}

        m = self._mod
        from ..export.progress_report import update_progress, end_progress

        if self._phase == 1:
            # Phase 2: apply modifiers incrementally (80% → 100%)
            if self._mod_idx < len(self._cones):
                obj = self._cones[self._mod_idx]
                bpy.ops.object.select_all(action='DESELECT')
                obj.select_set(True)
                bpy.context.view_layer.objects.active = obj
                for mod in reversed(list(obj.modifiers)):
                    try:
                        obj.modifiers.move(obj.modifiers.find(mod.name), 0)
                        bpy.ops.object.modifier_apply(modifier=mod.name)
                    except RuntimeError:
                        pass
                self._mod_idx += 1
                pct = 80 + (self._mod_idx / len(self._cones)) * 15
                update_progress(pct, f"应用修改器: {self._mod_idx}/{len(self._cones)}", context)
                return {'RUNNING_MODAL'}
            # Modifiers done, now hole bevels
            update_progress(96, "添加孔口圆倒角...", context)
            m._bevel_hole_openings()
            # Cleanup cutters
            for obj in list(bpy.data.objects):
                if obj.name.startswith('CUT_'):
                    bpy.data.objects.remove(obj, do_unlink=True)
            update_progress(100, "完成!", context)
            context.window_manager.event_timer_remove(self._timer)
            end_progress(context)
            context.window.cursor_set('DEFAULT')
            self.report({'INFO'}, f"Cone gallery created — {self._total} items")
            return {'FINISHED'}

        if self._shelf_idx >= len(m.SHELVES):
            # Gather cones with modifiers
            self._cones = [o for o in bpy.data.objects
                           if o.name.startswith('S') and not o.name.startswith('CUT_')
                           and not o.name.startswith('L') and o.modifiers]
            self._mod_idx = 0
            self._phase = 1
            update_progress(80, "应用修改器...", context)
            return {'RUNNING_MODAL'}

        shelf_label, base_ctype, base_fr, items = m.SHELVES[self._shelf_idx]
        if self._item_idx == 0:
            z = m.Z_TOP - self._shelf_idx * m.Z_GAP
            n = len(items)
            start_y = -((n - 1) * m.STEP_Y) / 2
            label_y = start_y + m.STEP_Y * (n - 1) / 2
            m.add_shelf_label(label_y, z, shelf_label)

        if self._item_idx < len(items):
            name_sfx, hole, hd, he, label = items[self._item_idx]
            z = m.Z_TOP - self._shelf_idx * m.Z_GAP
            n = len(items)
            start_y = -((n - 1) * m.STEP_Y) / 2
            y = start_y + self._item_idx * m.STEP_Y
            m.add_cone(y, z, f"S{self._shelf_idx+1}_{name_sfx}",
                       m.BOT_R, m.TOP_R, base_ctype, base_fr, hole, hd, he)
            m.add_label(y, z, label)
            self._done += 1
            pct = self._done / self._total * 80
            update_progress(pct, f"生成对象: {self._done}/{self._total}", context)
            self._item_idx += 1
        else:
            self._item_idx = 0
            self._shelf_idx += 1
        return {'RUNNING_MODAL'}

    def execute(self, context):
        import sys as _sys
        _sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), 'examples'))
        import create_cone_gallery as m
        m.clear()
        self._mod = m
        self._shelf_idx = 0
        self._item_idx = 0
        self._total = sum(len(s[3]) for s in m.SHELVES)
        self._done = 0
        self._phase = 0
        context.window.cursor_set('WAIT')
        from ..export.progress_report import start_progress
        start_progress(context, "创建正锥形库...")
        wm = context.window_manager
        self._timer = wm.event_timer_add(0.001, window=context.window)
        wm.modal_handler_add(self)
        return {'RUNNING_MODAL'}


class STEP_EXPORTER_OT_create_cone_gallery_inverted(Operator):
    """创建锥体组合样品（倒角/圆角/孔）- 倒锥形（上粗下细）"""
    bl_idname = "step_exporter.create_cone_gallery_inverted"
    bl_label = "Create Cone Gallery (Inverted)"
    bl_options = {'REGISTER', 'UNDO'}

    _timer = None
    _shelf_idx = 0
    _item_idx = 0
    _total = 0
    _done = 0
    _mod = None
    _phase = 0
    _cones = None
    _mod_idx = 0

    def modal(self, context, event):
        if event.type != 'TIMER':
            return {'PASS_THROUGH'}

        m = self._mod
        from ..export.progress_report import update_progress, end_progress

        if self._phase == 1:
            if self._mod_idx < len(self._cones):
                obj = self._cones[self._mod_idx]
                bpy.ops.object.select_all(action='DESELECT')
                obj.select_set(True)
                bpy.context.view_layer.objects.active = obj
                for mod in reversed(list(obj.modifiers)):
                    try:
                        obj.modifiers.move(obj.modifiers.find(mod.name), 0)
                        bpy.ops.object.modifier_apply(modifier=mod.name)
                    except RuntimeError:
                        pass
                self._mod_idx += 1
                pct = 80 + (self._mod_idx / len(self._cones)) * 15
                update_progress(pct, f"应用修改器: {self._mod_idx}/{len(self._cones)}", context)
                return {'RUNNING_MODAL'}
            update_progress(96, "添加孔口圆倒角...", context)
            m._bevel_hole_openings()
            for obj in list(bpy.data.objects):
                if obj.name.startswith('CUT_'):
                    bpy.data.objects.remove(obj, do_unlink=True)
            update_progress(100, "完成!", context)
            context.window_manager.event_timer_remove(self._timer)
            end_progress(context)
            context.window.cursor_set('DEFAULT')
            self.report({'INFO'}, f"Inverted cone gallery created — {self._total} items")
            return {'FINISHED'}

        if self._shelf_idx >= len(m.SHELVES):
            self._cones = [o for o in bpy.data.objects
                           if o.name.startswith('S') and not o.name.startswith('CUT_')
                           and not o.name.startswith('L') and o.modifiers]
            self._mod_idx = 0
            self._phase = 1
            update_progress(80, "应用修改器...", context)
            return {'RUNNING_MODAL'}

        shelf_label, base_ctype, base_fr, items = m.SHELVES[self._shelf_idx]
        if self._item_idx == 0:
            z = m.Z_TOP - self._shelf_idx * m.Z_GAP
            n = len(items)
            start_y = -((n - 1) * m.STEP_Y) / 2
            label_y = start_y + m.STEP_Y * (n - 1) / 2
            m.add_shelf_label(label_y, z, shelf_label)

        if self._item_idx < len(items):
            name_sfx, hole, hd, he, label = items[self._item_idx]
            z = m.Z_TOP - self._shelf_idx * m.Z_GAP
            n = len(items)
            start_y = -((n - 1) * m.STEP_Y) / 2
            y = start_y + self._item_idx * m.STEP_Y
            m.add_cone(y, z, f"S{self._shelf_idx+1}_{name_sfx}",
                       m.TOP_R, m.BOT_R, base_ctype, base_fr, hole, hd, he)
            m.add_label(y, z, label)
            self._done += 1
            pct = self._done / self._total * 80
            update_progress(pct, f"生成对象: {self._done}/{self._total}", context)
            self._item_idx += 1
        else:
            self._item_idx = 0
            self._shelf_idx += 1
        return {'RUNNING_MODAL'}

    def execute(self, context):
        import sys as _sys
        _sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), 'examples'))
        import create_cone_gallery_inverted as m
        m.clear()
        self._mod = m
        self._shelf_idx = 0
        self._item_idx = 0
        self._total = sum(len(s[3]) for s in m.SHELVES)
        self._done = 0
        self._phase = 0
        context.window.cursor_set('WAIT')
        from ..export.progress_report import start_progress
        start_progress(context, "创建倒锥形库...")
        wm = context.window_manager
        self._timer = wm.event_timer_add(0.001, window=context.window)
        wm.modal_handler_add(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        import sys as _sys
        _sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), 'examples'))
        import create_cone_gallery_inverted as m
        m.clear()
        self._mod = m
        self._shelf_idx = 0
        self._item_idx = 0
        self._total = sum(len(s[3]) for s in m.SHELVES)
        self._done = 0
        context.window.cursor_set('WAIT')
        from ..export.progress_report import start_progress
        start_progress(context, "创建倒锥形库...")
        wm = context.window_manager
        self._timer = wm.event_timer_add(0.001, window=context.window)
        wm.modal_handler_add(self)
        return {'RUNNING_MODAL'}


# ====================== 参数化圆柱生成 Operator ======================
# ====================== 参数化圆柱生成 Operator ======================

