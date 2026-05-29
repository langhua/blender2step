import bpy
import blf
import os


# 全局操作符引用（由 __init__.py 的 execute() 设置，modal() 清除）
_operator_instance = None

# 3D视图进度条绘制相关
_draw_handle = None
_progress_value = 0.0
_progress_text = ""
_progress_visible = False
_draw_region = None  # 保存3D视图区域引用


def set_operator(op):
    """设置当前操作符实例，用于 report() 调用"""
    global _operator_instance
    _operator_instance = op

def clear_operator():
    """清除操作符实例"""
    global _operator_instance
    _operator_instance = None


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


def _draw_progress_callback():
    """在3D视图左上角绘制进度条"""
    global _progress_value, _progress_text, _progress_visible, _draw_region
    
    if not _progress_visible:
        return
    
    try:
        import gpu
        from gpu_extras.batch import batch_for_shader
        
        # 进度条位置（左上角，已调整）
        margin_x = 160
        margin_y = 40
        bar_width = 500
        bar_height = 20
        
        # 使用保存的区域引用
        region = _draw_region
        
        # 如果区域引用失效，尝试重新获取
        if region is None:
            try:
                if hasattr(bpy.context, 'screen') and bpy.context.screen:
                    for area in bpy.context.screen.areas:
                        if area.type == 'VIEW_3D':
                            for r in area.regions:
                                if r.type == 'WINDOW':
                                    _draw_region = r
                                    region = r
                                    break
                            if region:
                                break
            except:
                pass
        
        # 如果仍然找不到区域，使用默认位置
        if region is None:
            x = margin_x
            y = 500
            _draw_progress_bar(x, y, bar_width, bar_height, _progress_value, _progress_text)
            return
        
        x = margin_x
        y = region.height - margin_y - bar_height
        _draw_progress_bar(x, y, bar_width, bar_height, _progress_value, _progress_text)
    except Exception as e:
        # 静默失败，避免影响Blender性能
        pass


def _draw_progress_bar(x, y, width, height, progress, text):
    """绘制进度条（蓝色=未导出，红色=已导出）"""
    try:
        import gpu
        from gpu_extras.batch import batch_for_shader
        
        # 背景着色器
        shader = gpu.shader.from_builtin('UNIFORM_COLOR')
        
        # 背景矩形（半透明黑色）
        vertices_bg = (
            (x - 5, y - 5),
            (x + width + 5, y - 5),
            (x + width + 5, y + height + 5),
            (x - 5, y + height + 5),
        )
        batch_bg = batch_for_shader(shader, 'TRI_FAN', {"pos": vertices_bg})
        shader.bind()
        shader.uniform_float("color", (0.0, 0.0, 0.0, 0.7))
        batch_bg.draw(shader)
        
        # 进度条背景（蓝色 - 表示未导出部分）
        vertices_bar_bg = (
            (x, y),
            (x + width, y),
            (x + width, y + height),
            (x, y + height),
        )
        batch_bar_bg = batch_for_shader(shader, 'TRI_FAN', {"pos": vertices_bar_bg})
        shader.uniform_float("color", (0.3, 0.6, 1.0, 0.9))  # 蓝色
        batch_bar_bg.draw(shader)
        
        # 进度条前景（红色 - 表示已导出部分）
        progress_width = width * min(progress, 100) / 100.0
        vertices_progress = (
            (x, y),
            (x + progress_width, y),
            (x + progress_width, y + height),
            (x, y + height),
        )
        batch_progress = batch_for_shader(shader, 'TRI_FAN', {"pos": vertices_progress})
        shader.uniform_float("color", (0.9, 0.3, 0.2, 0.95))  # 红色
        batch_progress.draw(shader)
        
        # 边框
        vertices_border = (
            (x, y),
            (x + width, y),
            (x + width, y + height),
            (x, y + height),
        )
        indices_border = (
            (0, 1), (1, 2), (2, 3), (3, 0),
        )
        batch_border = batch_for_shader(shader, 'LINES', {"pos": vertices_border}, indices=indices_border)
        shader.uniform_float("color", (0.5, 0.5, 0.5, 0.9))
        batch_border.draw(shader)
        
        # 文字
        font_id = 0
        blf.size(font_id, 14)
        
        display_text = f"{int(progress)}% {text}"
        text_width, text_height = blf.dimensions(font_id, display_text)
        
        text_x = x + (width - text_width) / 2
        text_y = y + (height - text_height) / 2 + 3
        
        # 文字阴影
        blf.color(font_id, 0.0, 0.0, 0.0, 0.8)
        blf.position(font_id, text_x + 1, text_y - 1, 0)
        blf.draw(font_id, display_text)
        
        # 文字主体
        blf.color(font_id, 1.0, 1.0, 1.0, 1.0)
        blf.position(font_id, text_x, text_y, 0)
        blf.draw(font_id, display_text)
        
    except Exception as e:
        pass


def register():
    """注册（兼容旧代码，无实际操作）"""
    pass


def unregister():
    """注销（兼容旧代码，无实际操作）"""
    global _draw_handle
    if _draw_handle is not None:
        bpy.types.SpaceView3D.draw_handler_remove(_draw_handle, 'WINDOW')
        _draw_handle = None


def start_progress(context, text="正在导出 STEP 文件..."):
    """启动进度条显示"""
    global _progress_value, _progress_text, _progress_visible, _draw_handle, _draw_region
    
    _progress_value = 0.0
    _progress_text = text
    _progress_visible = True
    
    # 在注册draw handler前，先获取并保存3D视图区域引用
    if _draw_region is None:
        try:
            if hasattr(context, 'screen') and context.screen:
                for area in context.screen.areas:
                    if area.type == 'VIEW_3D':
                        for r in area.regions:
                            if r.type == 'WINDOW':
                                _draw_region = r
                                break
                        if _draw_region:
                            break
        except:
            pass
    
    try:
        # 使用 wm.progress API（Blender 官方状态栏进度条）
        wm = context.window_manager if context else None
        if wm:
            wm.progress_begin(0, 100)
            wm.progress_update(0)
        
        # 同时通过 operator.report 显示文本提示（更可见）
        global _operator_instance
        if _operator_instance and text:
            try:
                _operator_instance.report({'INFO'}, text)
            except:
                pass
        
        # 注册3D视图绘制回调
        if _draw_handle is None:
            _draw_handle = bpy.types.SpaceView3D.draw_handler_add(
                _draw_progress_callback, (), 'WINDOW', 'POST_PIXEL'
            )
        
        log_progress(f"[STEP Progress] start_progress: '{text}' wm={'ok' if wm else 'None'}")
    except Exception as e:
        log_progress(f"[STEP Progress] start_progress failed: {e}")


def update_progress(progress, text=None, context=None):
    """更新进度"""
    global _progress_value, _progress_text
    
    _progress_value = progress
    if text:
        _progress_text = text
    
    try:
        wm = context.window_manager if context else None
        if wm:
            try:
                wm.progress_update(int(progress))
            except:
                pass
        
        # 同时通过 operator.report 显示文本进度（更可见）
        global _operator_instance
        if _operator_instance and text:
            try:
                _operator_instance.report({'INFO'}, f"{int(progress)}% {text}")
            except:
                pass
        
        # 强制刷新3D视图UI以确保进度条更新可见
        try:
            if context and hasattr(context, 'screen') and context.screen:
                for area in context.screen.areas:
                    if area.type == 'VIEW_3D':
                        area.tag_redraw()
                        break
        except:
            pass
        
        log_progress(f"[STEP Progress] update: {int(progress)}% - {text if text else ''}")
    except Exception as e:
        log_progress(f"[STEP Progress] update_progress failed: {e}")


def end_progress(context):
    """结束进度条显示"""
    global _progress_visible, _draw_handle, _draw_region
    
    _progress_visible = False
    
    try:
        wm = context.window_manager if context else None
        if wm:
            wm.progress_end()
        
        global _operator_instance
        if _operator_instance:
            try:
                _operator_instance.report({'INFO'}, "STEP 导出完成")
            except:
                pass
        
        # 移除3D视图绘制回调
        if _draw_handle is not None:
            try:
                bpy.types.SpaceView3D.draw_handler_remove(_draw_handle, 'WINDOW')
            except:
                pass
            _draw_handle = None
        
        # 清除区域引用
        _draw_region = None
        
        # 强制刷新UI以确保进度条消失
        try:
            for area in context.screen.areas:
                if area.type == 'VIEW_3D':
                    area.tag_redraw()
                    break
        except:
            pass
        
        log_progress(f"[STEP Progress] end_progress")
    except Exception as e:
        log_progress(f"[STEP Progress] end_progress failed: {e}")
