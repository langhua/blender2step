"""
Shared global state for the STEP Exporter addon.
All sub-modules import state from here to avoid circular imports.
"""

import os

# ====================== Export State ======================
_export_params = None
_export_stage = 0  # 0=未开始，1=准备数据，2=调用 C++，3=完成
_export_objects = []
_export_objects_data = []
_export_current_index = 0
_cpp_progress = -1.0  # 存储 C++ 回调传递的进度
_export_log_file = None  # 日志文件句柄
_log_buffer = []  # 日志缓冲区（文件打开前的消息暂存于此）
_cpp_log_callback = None  # C++日志回调函数
_bottom_shell_export_data = None  # 底壳参数化导出数据
_export_complete = False  # 异步导出完成标志
_export_success = False   # 异步导出成功标志
_export_start_time = 0.0  # 导出开始时间
_stage_start_time = 0.0   # 阶段开始时间

# 参数化异步导出状态（分阶段，每个对象一个timer tick）
_parametric_export_stage = 0
_parametric_export_idx = 0
_parametric_temp_files = []
_parametric_progress_val = 0.0
_parametric_temp_success_count = 0

# ====================== C++ Module State ======================
CPP_MODULE_LOADED = False
step_exporter = None
MODULE_LOAD_ERROR = ""

# All symbols exported via "from _globals import *"
__all__ = [
    '_export_params', '_export_stage', '_export_objects', '_export_objects_data',
    '_export_current_index', '_cpp_progress', '_export_log_file', '_log_buffer',
    '_cpp_log_callback', '_bottom_shell_export_data', '_export_complete',
    '_export_success', '_export_start_time', '_stage_start_time',
    '_parametric_export_stage', '_parametric_export_idx', '_parametric_temp_files',
    '_parametric_progress_val', '_parametric_temp_success_count',
    'CPP_MODULE_LOADED', 'step_exporter', 'MODULE_LOAD_ERROR',
]
