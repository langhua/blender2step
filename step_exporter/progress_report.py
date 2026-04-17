import bpy
import os
from bpy.props import FloatProperty, StringProperty
from bpy.types import Operator, Scene


# a variable where we can store the original draw function
step_info_header_draw = lambda s, c: None

def update(self, context):
    areas = context.window.screen.areas
    for area in areas:
        if area.type == 'VIEW_3D':
            area.tag_redraw()

def log_progress(msg):
    """输出进度相关日志到日志文件"""
    try:
        from . import _export_log_file
        if _export_log_file and not _export_log_file.closed:
            if not msg.endswith("\n"):
                _export_log_file.write(msg + "\n")
            else:
                _export_log_file.write(msg)
            _export_log_file.flush()
    except:
        pass


class STEPProgressReport(Operator):
    bl_idname = 'step_exporter.progress_report'
    bl_label = 'STEP Export Progress Report'
    bl_options = {'REGISTER'}

    _timer = None
    _export_function = None

    def modal(self, context, event):
        log_progress(f"[STEP Progress] modal called, event.type={event.type}")
        if event.type == 'TIMER':
            log_progress(f"[STEP Progress] TIMER event received!")
            # 检查是否完成
            if context and hasattr(context.scene, 'step_progress_indicator'):
                log_progress(f"[STEP Progress] step_progress_indicator={context.scene.step_progress_indicator}")
                if context.scene.step_progress_indicator >= 101:
                    log_progress(f"[STEP Progress] Export complete, cleaning up...")
                    # 完成，清理
                    if context:
                        context.window_manager.event_timer_remove(self._timer)
                    # 恢复原始绘制函数
                    global step_info_header_draw
                    bpy.types.VIEW3D_HT_tool_header.draw = step_info_header_draw
                    return {'CANCELLED'}

        return {'PASS_THROUGH'}
    
    def invoke(self, context, event):
        log_progress(f"[STEP Progress] invoke called!")
        # save the original draw method of the Info header
        global step_info_header_draw
        step_info_header_draw = bpy.types.VIEW3D_HT_tool_header.draw
        log_progress(f"[STEP Progress] Saved original draw function")

        # create a new draw function
        def newdraw(self, context):
            # first call the original stuff
            # step_info_header_draw(self, context)
            # then add the prop that acts as a progress indicator
            if context.scene.step_progress_indicator >= 0 and context.scene.step_progress_indicator <= 100:
                layout = self.layout
                layout.ui_units_x = 40
                layout.alert = True
                layout.separator()
                text = context.scene.step_progress_indicator_text
                layout.prop(context.scene,
                                property='step_progress_indicator',
                                text=text,
                                slider=True)

        # replace it
        bpy.types.VIEW3D_HT_tool_header.draw = newdraw
        log_progress(f"[STEP Progress] Replaced draw function")

        if context:
            wm = context.window_manager
            self._timer = wm.event_timer_add(0.1, window=context.window)
            log_progress(f"[STEP Progress] Timer added: {self._timer}")
            wm.modal_handler_add(self)
            log_progress(f"[STEP Progress] Modal handler added")
        return {'RUNNING_MODAL'}


def register():
    bpy.utils.register_class(STEPProgressReport)

    # a value between [0,100] will show the slider
    setattr(Scene, 'step_progress_indicator', FloatProperty(
                                    default=-1,
                                    subtype='PERCENTAGE',
                                    precision=1,
                                    min=-1,
                                    soft_min=0,
                                    soft_max=100,
                                    max=101,
                                    update=update))

    # the label in front of the slider can be configured
    setattr(Scene, 'step_progress_indicator_text', StringProperty(
                                    default="正在导出 STEP 文件...",
                                    update=update))


def unregister():
    global step_info_header_draw
    bpy.types.VIEW3D_HT_tool_header.draw = step_info_header_draw
    bpy.utils.unregister_class(STEPProgressReport)
    try:
        if hasattr(Scene, 'step_progress_indicator_text'):
            delattr(Scene, 'step_progress_indicator_text')
    except:
        pass
    try:
        if hasattr(Scene, 'step_progress_indicator'):
            delattr(Scene, 'step_progress_indicator')
    except:
        pass


def start_progress(context, text="正在导出 STEP 文件..."):
    """启动进度条显示"""
    if context and hasattr(context.scene, 'step_progress_indicator'):
        context.scene.step_progress_indicator = 0
    if context and hasattr(context.scene, 'step_progress_indicator_text'):
        context.scene.step_progress_indicator_text = text


def update_progress(progress, text=None, context=None):
    """更新进度"""
    if context and hasattr(context.scene, 'step_progress_indicator'):
        context.scene.step_progress_indicator = progress
    if text and context and hasattr(context.scene, 'step_progress_indicator_text'):
        context.scene.step_progress_indicator_text = text


def end_progress(context):
    """结束进度条显示"""
    if context and hasattr(context.scene, 'step_progress_indicator'):
        context.scene.step_progress_indicator = 101  # done
    if context and hasattr(context.scene, 'step_progress_indicator_text'):
        context.scene.step_progress_indicator_text = "导出完成"
