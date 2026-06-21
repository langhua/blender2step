class STEP_EXPORTER_OT_create_cylinder_gallery(Operator):
    """创建圆柱体组合样品（8种边缘特征× 10种孔洞）"""
    bl_idname = "step_exporter.create_cylinder_gallery"
    bl_label = "Create Cylinder Gallery"
    bl_options = {'REGISTER', 'UNDO'}

    _timer = None
    _mod = None
    _phase = 0

    def modal(self, context, event):
        if event.type != 'TIMER':
            return {'PASS_THROUGH'}

        from ..export.progress_report import update_progress, end_progress
        m = self._mod

        if self._phase == 0:
            m.build(progress_cb=lambda p, msg: update_progress(p, msg, context))
            self._phase = 1
            return {'RUNNING_MODAL'}

        if self._phase == 1:
            m.add_grooved_copies(progress_cb=lambda p, msg: update_progress(p, msg, context))
            self._phase = 2
            return {'RUNNING_MODAL'}

        if self._phase == 2:
            update_progress(100, "完成!", context)
            context.window_manager.event_timer_remove(self._timer)
            end_progress(context)
            context.window.cursor_set('DEFAULT')
            self.report({'INFO'}, "Cylinder gallery created — 192 items")
            return {'FINISHED'}

        return {'PASS_THROUGH'}

    def invoke(self, context, event):
        import sys as _sys
        _sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), 'examples'))
        import create_cylinder_gallery as m
        m.clear()
        self._mod = m
        self._phase = 0
        context.window.cursor_set('WAIT')
        from ..export.progress_report import start_progress
        start_progress(context, "Creating cylinder gallery (with grooves)...")
        wm = context.window_manager
        self._timer = wm.event_timer_add(0.001, window=context.window)
        wm.modal_handler_add(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        return self.invoke(context, None)
