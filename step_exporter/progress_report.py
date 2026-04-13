"""
STEP 导出进度报告系统
基于 Fritzing Gerber 导入器的进度条实现
"""

import bpy
from bpy.props import FloatProperty, StringProperty
from bpy.types import Operator, Scene
import time
import sys
import os

# 保存原始VIEW3D_HT_tool_header.draw函数
step_info_header_draw = lambda s, c: None

def update_ui(self, context):
    """更新UI，标记需要重绘的区域"""
    areas = context.window.screen.areas
    for area in areas:
        if area.type == 'VIEW_3D':
            area.tag_redraw()

# 全局进度数据
class STEPProgressData:
    def __init__(self):
        self.progress = -1.0  # -1 表示隐藏，-100 表示进度
        self.text = "正在导出 STEP 文件..."
        self.is_running = False
        self.log_file = None
        self.use_c_stdout = False  # 标记是否使用 C++ 重定向的 stdout
    
    def log(self, message):
        """日志输出函数，自动选择输出到日志文件或 stdout"""
        log_msg = f"[STEP Progress] {message}"
        if self.log_file:
            print(log_msg, file=self.log_file, flush=True)
        elif self.use_c_stdout:
            # 使用 C++ 重定向的 stdout（直接 print 会到 C++ 的 stdout）
            print(log_msg, flush=True)
        else:
            print(log_msg)
    
    def set_log_file(self, log_file_path):
        """设置日志文件路径"""
        try:
            self.log_file = open(log_file_path, 'a')
            self.log(f"Redirected progress output to log file: {log_file_path}")
        except Exception as e:
            step_progress_data.log(f"WARNING: Failed to open log file: {e}")
    
    def set_use_c_stdout(self, use_c_stdout):
        """设置是否使用 C++ 重定向的 stdout"""
        self.use_c_stdout = use_c_stdout
        if use_c_stdout:
            self.log("Using C++ redirected stdout")
    
    def close_log_file(self):
        """关闭日志文件"""
        if self.log_file:
            try:
                self.log_file.close()
                self.log_file = None
                print(f"[STEP Progress] Closed log file", file=sys.__stdout__, flush=True)
            except Exception as e:
                step_progress_data.log(f"WARNING: Failed to close log file: {e}")
    
    def update(self, progress, text=None, context=None):
        self.progress = progress
        if text:
            self.text = text
        # 记录更新（用于调试）
        log_msg = f"[STEP Progress] Data updated: {progress:.1f}%, text: {text}"
        if self.log_file:
            print(log_msg, file=self.log_file, flush=True)
        else:
            print(log_msg)
        
        # 更新场景属性（如果已注册）
        try:
            # 尝试使用提供的上下文，否则使用bpy.context
            scene = None
            if context and hasattr(context, 'scene'):
                scene = context.scene
            else:
                # 回退到bpy.context，但注意这可能在窗口失焦时无效
                scene = bpy.context.scene
            
            if scene and hasattr(scene, 'step_progress_indicator'):
                scene.step_progress_indicator = progress
                log_msg = f"[STEP Progress] Scene property updated via context"
                if self.log_file:
                    print(log_msg, file=self.log_file, flush=True)
                else:
                    print(log_msg)
            if text and scene and hasattr(scene, 'step_progress_indicator_text'):
                scene.step_progress_indicator_text = text
        except Exception as e:
            # 忽略上下文错误，数据已存储在对象中，定时器会尝试更新
            log_msg = f"[STEP Progress] Context update failed: {e}"
            if self.log_file:
                print(log_msg, file=self.log_file, flush=True)
            else:
                print(log_msg)
        
        # 强制UI刷新（尝试所有窗口）
        self._force_ui_refresh()
    
    def _force_ui_refresh(self):
        """强制刷新所有窗口的UI"""
        try:
            windows_updated = 0
            areas_updated = 0
            for window_manager in bpy.data.window_managers:
                for window in window_manager.windows:
                    screen = window.screen
                    if not screen:
                        continue
                    
                    # 更新该窗口的场景属性
                    try:
                        scene = screen.scene
                        if scene and hasattr(scene, 'step_progress_indicator'):
                            scene.step_progress_indicator = self.progress
                            windows_updated += 1
                        if scene and hasattr(scene, 'step_progress_indicator_text'):
                            scene.step_progress_indicator_text = self.text
                    except:
                        pass
                    
                    # 标记所有3D视图区域需要重绘
                    for area in screen.areas:
                        if area.type == 'VIEW_3D':
                            try:
                                area.tag_redraw()
                                areas_updated += 1
                            except:
                                pass
            
            log_msg = f"[STEP Progress] UI refresh forced: {windows_updated} windows, {areas_updated} areas"
            if self.log_file:
                print(log_msg, file=self.log_file, flush=True)
            else:
                print(log_msg)
        except Exception as e:
            log_msg = f"[STEP Progress] UI refresh error: {e}"
            if self.log_file:
                print(log_msg, file=self.log_file, flush=True)
            else:
                print(log_msg)

step_progress_data = STEPProgressData()

# 全局后台定时器句柄
step_app_timer = None

class STEPProgressReport(Operator):
    """STEP 导出进度报告操作符"""
    bl_idname = 'export_scene.step_progress_report'
    bl_label = 'STEP Export Progress Report'
    bl_options = {'REGISTER', 'INTERNAL'}
    
    # 模态操作符的定时器
    timer = None
    
    def modal(self, context, event):
        # 检查是否应该结束
        if not step_progress_data.is_running:
            if self.timer and context:
                context.window_manager.event_timer_remove(self.timer)
            # 移除后台定时器
            global step_app_timer
            if step_app_timer:
                try:
                    bpy.app.timers.remove(step_app_timer)
                except:
                    pass
                step_app_timer = None
            # 恢复原始绘制函数
            bpy.types.VIEW3D_HT_tool_header.draw = step_info_header_draw
            return {'CANCELLED'}
        
        # 处理窗口激活事件（当Blender重新获得焦点时）
        if event.type == 'WINDOW_DEACTIVATE':
            # 窗口失去焦点，记录状态但不停止
            if step_progress_data.is_running:
                log_msg = f"[STEP Progress] Window deactivated, progress: {step_progress_data.progress:.1f}%"
                if step_progress_data.log_file:
                    print(log_msg, file=step_progress_data.log_file, flush=True)
                else:
                    print(log_msg)
        elif event.type == 'WINDOW_ACTIVATE':
            # 窗口重新获得焦点，强制立即更新UI
            if step_progress_data.is_running:
                log_msg = f"[STEP Progress] Window activated, forcing UI refresh, progress: {step_progress_data.progress:.1f}%"
                if step_progress_data.log_file:
                    print(log_msg, file=step_progress_data.log_file, flush=True)
                else:
                    print(log_msg)
            if hasattr(context.scene, 'step_progress_indicator'):
                context.scene.step_progress_indicator = step_progress_data.progress
            if hasattr(context.scene, 'step_progress_indicator_text'):
                context.scene.step_progress_indicator_text = step_progress_data.text
            # 强制更新所有3D视图区域
            areas = context.window.screen.areas
            for area in areas:
                if area.type == 'VIEW_3D':
                    area.tag_redraw()
            # 额外调用一次update_ui确保刷新
            update_ui(self, context)
        
        if event.type == 'TIMER':
            # 更新进度显示
            if hasattr(context.scene, 'step_progress_indicator'):
                context.scene.step_progress_indicator = step_progress_data.progress
            if hasattr(context.scene, 'step_progress_indicator_text'):
                context.scene.step_progress_indicator_text = step_progress_data.text
            
            # 触发UI更新
            update_ui(self, context)
        
        return {'PASS_THROUGH'}
    
    def invoke(self, context, event):
        log_msg = f"[STEP Progress] Progress operator invoked, window: {context.window}"
        if step_progress_data.log_file:
            print(log_msg, file=step_progress_data.log_file, flush=True)
        else:
            print(log_msg)
        # 保存原始绘制函数
        global step_info_header_draw, step_app_timer
        step_info_header_draw = bpy.types.VIEW3D_HT_tool_header.draw
        
        # 创建新的绘制函数
        def new_draw(self, context):
            # 先调用原始函数
            # step_info_header_draw(self, context)
            # 添加进度指示器
            if hasattr(context.scene, 'step_progress_indicator'):
                progress = context.scene.step_progress_indicator
                if 0 <= progress <= 100:
                    layout = self.layout
                    layout.ui_units_x = 40
                    layout.alert = True
                    layout.separator()
                    text = getattr(context.scene, 'step_progress_indicator_text', '导出 STEP 文件...')
                    layout.prop(context.scene,
                                property='step_progress_indicator',
                                text=text,
                                slider=True)
        
        # 替换绘制函数
        bpy.types.VIEW3D_HT_tool_header.draw = new_draw
        
        # 启动定时器
        step_progress_data.is_running = True
        wm = context.window_manager
        
        # 启动事件定时器（用于模态操作符，处理窗口事件）
        self.timer = wm.event_timer_add(0.1, window=context.window)  # 0.1秒更新一次
        
        # 启动后台定时器（即使窗口失去焦点也会运行）
        # 使用闭包变量存储状态
        background_timer_call_count = 0
        last_logged_progress = -999
        
        def background_timer():
            nonlocal background_timer_call_count, last_logged_progress
            background_timer_call_count += 1
            
            # 第一次调用时打印
            if background_timer_call_count == 1:
                step_progress_data.log(f"Background timer first call, progress: {step_progress_data.progress:.1f}%")
            
            if not step_progress_data.is_running:
                # 停止定时器
                global step_app_timer
                step_app_timer = None
                step_progress_data.log("Background timer stopped")
                return None
            
            # 每10次调用或进度变化超过1%时输出调试信息
            log_this_time = False
            progress_changed = abs(step_progress_data.progress - last_logged_progress) > 1.0
            if background_timer_call_count % 10 == 0 or progress_changed:
                log_this_time = True
                last_logged_progress = step_progress_data.progress
            
            if log_this_time:
                step_progress_data.log(f"Background timer running (call #{background_timer_call_count}), progress: {step_progress_data.progress:.1f}%, text: {step_progress_data.text}")
            
            # 更新UI（使用所有可用窗口的上下文）
            try:
                # 获取所有窗口管理器（通常只有一个）
                windows_updated = 0
                areas_updated = 0
                
                # 调试信息：打印窗口管理器数量
                if log_this_time:
                    step_progress_data.log(f"Window managers count: {len(bpy.data.window_managers)}")
                
                for window_manager in bpy.data.window_managers:
                    # 调试信息：打印窗口数量
                    if log_this_time:
                        step_progress_data.log(f"Windows count in manager: {len(window_manager.windows)}")
                    
                    for window in window_manager.windows:
                        # 获取该窗口的屏幕和场景
                        screen = window.screen
                        if not screen:
                            continue
                        
                        # 调试信息：打印屏幕信息
                        if log_this_time:
                            step_progress_data.log(f"Screen name: {screen.name}, areas count: {len(screen.areas)}")
                        
                        # 尝试更新该窗口的场景属性
                        try:
                            # 使用temp_override为该窗口设置上下文
                            with bpy.context.temp_override(window=window, area=screen.areas[0] if screen.areas else None):
                                scene = bpy.context.scene
                                if hasattr(scene, 'step_progress_indicator'):
                                    scene.step_progress_indicator = step_progress_data.progress
                                    windows_updated += 1
                                    if log_this_time:
                                        step_progress_data.log(f"Updated scene property for window {window.as_pointer()}")
                                if hasattr(scene, 'step_progress_indicator_text'):
                                    scene.step_progress_indicator_text = step_progress_data.text
                        except Exception as e:
                            # 如果temp_override失败，尝试直接设置屏幕的场景
                            try:
                                scene = screen.scene
                                if scene and hasattr(scene, 'step_progress_indicator'):
                                    scene.step_progress_indicator = step_progress_data.progress
                                    windows_updated += 1
                                    if log_this_time:
                                        step_progress_data.log(f"Updated scene property via screen.scene for window {window.as_pointer()}")
                                if scene and hasattr(scene, 'step_progress_indicator_text'):
                                    scene.step_progress_indicator_text = step_progress_data.text
                            except Exception as e2:
                                if log_this_time:
                                    step_progress_data.log(f"Failed to update window {window.as_pointer()}: {e2}")
                        
                        # 标记所有3D视图区域需要重绘
                        for area in screen.areas:
                            if area.type == 'VIEW_3D':
                                try:
                                    area.tag_redraw()
                                    areas_updated += 1
                                    if log_this_time:
                                        step_progress_data.log(f"Tagged redraw for area {area.as_pointer()}")
                                except Exception as e:
                                    if log_this_time:
                                        step_progress_data.log(f"Failed to tag redraw for area {area.as_pointer()}: {e}")
                
                if log_this_time:
                    step_progress_data.log(f"Updated {windows_updated} window(s), {areas_updated} area(s)")
            except Exception as e:
                # 记录所有错误
                step_progress_data.log(f"Error in background timer: {e}")
                import traceback
                traceback.print_exc()
            
            # 返回下一次调用的间隔（秒）
            return 0.1  # 0.1秒运行一次，提高响应速度
        
        # 注册后台定时器
        if step_app_timer:
            try:
                bpy.app.timers.remove(step_app_timer)
            except:
                pass
        step_app_timer = bpy.app.timers.register(background_timer)
        step_progress_data.log(f"Background timer registered: {step_app_timer}")
        
        wm.modal_handler_add(self)
        
        return {'RUNNING_MODAL'}
    
    def stop(self, context):
        """停止进度报告"""
        step_progress_data.is_running = False
        step_progress_data.update(-1, "导出完成")
        if context and hasattr(context.scene, 'step_progress_indicator'):
            context.scene.step_progress_indicator = -1
        update_ui(self, context)
        # 定时器将在下一次modal调用时移除

def register():
    """注册进度报告系统"""
    bpy.utils.register_class(STEPProgressReport)
    
    # 添加场景属性用于进度显示
    # 进度值：-1 表示隐藏，-100 表示进度
    setattr(Scene, 'step_progress_indicator', FloatProperty(
        default=-1.0,
        subtype='PERCENTAGE',
        precision=1,
        min=-1,
        soft_min=0,
        soft_max=100,
        max=101,
        update=update_ui
    ))
    
    # 进度条文本标签
    setattr(Scene, 'step_progress_indicator_text', StringProperty(
        default="正在导出 STEP 文件...",
        update=update_ui
    ))
    
    print("[STEP Exporter] 进度报告系统已注册")

def unregister():
    """注销进度报告系统"""
    global step_info_header_draw
    # 恢复原始绘制函数
    if step_info_header_draw:
        bpy.types.VIEW3D_HT_tool_header.draw = step_info_header_draw
    
    bpy.utils.unregister_class(STEPProgressReport)
    
    # 移除场景属性
    if hasattr(Scene, 'step_progress_indicator_text'):
        delattr(Scene, 'step_progress_indicator_text')
    if hasattr(Scene, 'step_progress_indicator'):
        delattr(Scene, 'step_progress_indicator')
    
    print("[STEP Exporter] 进度报告系统已注销")

# 便捷函数
def start_progress(context):
    """启动进度条显示"""
    step_progress_data.log(f"start_progress called, context: {context}, window: {context.window if context else None}")
    step_progress_data.is_running = True
    step_progress_data.update(0, "正在准备导出...")
    
    # 启动模态操作符
    operator_success = False
    if context:
        try:
            bpy.ops.export_scene.step_progress_report('INVOKE_DEFAULT')
            step_progress_data.log(f"Progress operator invoked successfully")
            operator_success = True
        except Exception as e:
            step_progress_data.log(f"Failed to invoke progress operator: {e}")
            import traceback
            traceback.print_exc()
    else:
        step_progress_data.log(f"No context provided, cannot start progress operator")
    
    # 如果操作符启动失败，启动后备定时器
    global step_app_timer
    if not operator_success and step_app_timer is None:
        step_progress_data.log(f"Starting fallback background timer")
        step_app_timer = bpy.app.timers.register(background_progress_update)
        step_progress_data.log(f"Fallback background timer registered: {step_app_timer}")
    
    return step_progress_data

def background_progress_update():
    """后台定时器函数，独立于模态操作符"""
    global step_app_timer
    if not step_progress_data.is_running:
        # 停止定时器
        step_app_timer = None
        print("[STEP Progress] Background update timer stopped")
        return None
    
    # 强制刷新UI
    step_progress_data._force_ui_refresh()
    
    # 返回下一次调用的间隔（秒）
    return 0.1

def update_progress(progress, text=None, context=None):
    """更新进度"""
    step_progress_data.update(progress, text, context)

def end_progress(context):
    """结束进度条显示"""
    global step_app_timer
    step_progress_data.log(f"end_progress called, is_running: {step_progress_data.is_running}")
    if step_progress_data.is_running:
        step_progress_data.is_running = False
        step_progress_data.update(-1, "导出完成")
        if context and hasattr(context.scene, 'step_progress_indicator'):
            context.scene.step_progress_indicator = -1
        # 移除后台定时器
        if step_app_timer:
            try:
                bpy.app.timers.remove(step_app_timer)
                step_progress_data.log(f"Background timer removed")
            except:
                pass
            step_app_timer = None
        
        # 强制UI刷新，确保光标恢复正常
        try:
            # 更新所有窗口
            for window_manager in bpy.data.window_managers:
                for window in window_manager.windows:
                    screen = window.screen
                    if screen:
                        scene = screen.scene
                        if scene and hasattr(scene, 'step_progress_indicator'):
                            scene.step_progress_indicator = -1
                        # 标记所有区域需要重绘
                        for area in screen.areas:
                            area.tag_redraw()
            
            # 处理事件队列
            if hasattr(bpy.app, 'process_events'):
                for i in range(5):
                    bpy.app.process_events()
            
            # 调用重绘计时器
            if hasattr(bpy.ops.wm, 'redraw_timer'):
                bpy.ops.wm.redraw_timer(type='DRAW_WIN_SWAP', iterations=1)
                step_progress_data.log(f"Final redraw timer called")
                
        except Exception as e:
            step_progress_data.log(f"Final UI refresh error: {e}")
        
        update_ui(None, context)
        step_progress_data.log(f"Progress ended")








