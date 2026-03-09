"""
STEP 导出进度报告系统
基于 Fritzing Gerber 导入器的进度条实现
"""

import bpy
from bpy.props import FloatProperty, StringProperty
from bpy.types import Operator, Scene

# 保存原始的 draw 函数
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
        self.progress = -1.0  # -1 表示隐藏，0-100 表示进度
        self.text = "正在导出 STEP 文件..."
        self.is_running = False
    
    def update(self, progress, text=None):
        self.progress = progress
        if text:
            self.text = text
        # 更新场景属性（如果已注册）
        if hasattr(bpy.context.scene, 'step_progress_indicator'):
            bpy.context.scene.step_progress_indicator = progress
        if text and hasattr(bpy.context.scene, 'step_progress_indicator_text'):
            bpy.context.scene.step_progress_indicator_text = text

step_progress_data = STEPProgressData()

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
            # 恢复原始绘制函数
            bpy.types.VIEW3D_HT_tool_header.draw = step_info_header_draw
            return {'CANCELLED'}
        
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
        # 保存原始绘制函数
        global step_info_header_draw
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
        self.timer = wm.event_timer_add(0.1, window=context.window)  # 每0.1秒更新一次
        wm.modal_handler_add(self)
        
        return {'RUNNING_MODAL'}
    
    def stop(self, context):
        """停止进度条"""
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
    # 进度值：-1 表示隐藏，0-100 表示进度
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
    step_progress_data.is_running = True
    step_progress_data.update(0, "正在准备导出...")
    # 启动模态操作符
    if context:
        bpy.ops.export_scene.step_progress_report('INVOKE_DEFAULT')
    return step_progress_data

def update_progress(progress, text=None):
    """更新进度条"""
    step_progress_data.update(progress, text)

def end_progress(context):
    """结束进度条显示"""
    if step_progress_data.is_running:
        step_progress_data.is_running = False
        step_progress_data.update(-1, "导出完成")
        if context and hasattr(context.scene, 'step_progress_indicator'):
            context.scene.step_progress_indicator = -1
        update_ui(None, context)