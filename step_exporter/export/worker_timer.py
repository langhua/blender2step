"""Export worker timer for regular mesh export."""
import sys, os, math, time
import bpy
from ..core.utils import log_to_file
from .progress_report import start_progress, update_progress, end_progress
from ..core import _globals as _g

def _export_worker_timer():
    """导出工作器，在 timer 中运行，分阶段执行"""
    
    if not _g._export_params:
        return None
    
    try:
        params = _g._export_params
        context = params['context']
        
        # 阶段 1: 准备数据（一次性处理所有对象）
        if _g._export_stage == 1:
            log_to_file(f"\n[STEP Exporter] Stage 1: Preparing data...")
            
            if params['unit'] == 'mm':
                scale = 1000.0
            else:
                scale = 1.0
            
            for idx, obj in enumerate(_g._export_objects):
                log_to_file(f"[Python DEBUG] Processing object {idx}: '{obj.name}' (type: {obj.type})")
                
                obj_data = None
                if obj.type == 'MESH':
                    obj_data = _get_mesh_data_enhanced(obj, context, scale, params['apply_modifiers'])
                elif obj.type == 'CURVE':
                    obj_data = _get_curve_data_enhanced(obj, context, scale, params['apply_modifiers'])
                
                if obj_data:
                    _g._export_objects_data.append(obj_data)
                
                object_progress = ((idx + 1) / len(_g._export_objects)) * 20
                update_progress(object_progress, f"正在处理对象 {idx+1}/{len(_g._export_objects)}", context)
            
            _g._export_stage = 2
            log_to_file(f"[STEP Exporter] Data preparation complete: {len(_g._export_objects_data)} objects")
            return 0.1
        
        # 阶段 2: 初始化增量导出
        elif _g._export_stage == 2:
            log_to_file(f"\n[STEP Exporter] Stage 2: Initializing incremental export...")
            
            step_unit = 'MILLIMETER' if params['unit'] == 'mm' else 'METER'
            sew_tolerance_m = params['sew_tolerance']
            
            # 创建日志回调函数，供C++调用以写入日志文件
            _g._cpp_log_callback = lambda msg: log_to_file(msg)
            
            success = _g.step_exporter.init_incremental_export(
                params['filepath'],
                len(_g._export_objects_data),
                params['scale'],
                1 if params['fix_geometry'] else 0,
                1 if params['create_solid'] else 0,
                1 if params['advanced_brep'] else 0,
                params['step_schema'],
                step_unit,
                1 if params['enable_logging'] else 0,
                sew_tolerance_m,
                _g._cpp_log_callback
            )
            
            if not success:
                log_to_file(f"[STEP Exporter] Failed to initialize incremental export")
                update_progress(100, "导出失败", context)
                end_progress(context)
                return None
            
            _g._export_current_index = 0
            _g._export_stage = 3
            log_to_file(f"[STEP Exporter] Incremental export initialized")
            return 0.1  # 立即进入下一阶段
        
        # 阶段 3: 逐个添加对象到导出（异步模式）
        elif _g._export_stage == 3:
            if _g._export_current_index >= len(_g._export_objects_data):
                # 所有对象已处理完成，进入阶段 4
                _g._export_stage = 4
                log_to_file(f"[STEP Exporter] All objects processed, finalizing export...")
                return 0.1
            
            # 创建回调函数更新进度
            def callback(progress):
                # 映射进度：20-100%
                mapped_progress = 20.0 + (progress / 100.0) * 80.0
                update_progress(mapped_progress, f"正在导出对象 {_g._export_current_index+1}/{len(_g._export_objects_data)}", context)
            
            obj_data = _g._export_objects_data[_g._export_current_index]
            log_to_file(f"[STEP Exporter] Adding object {_g._export_current_index+1}/{len(_g._export_objects_data)}: {obj_data.get('name', 'Unknown')}")
            
            success = _g.step_exporter.add_object_to_export(obj_data, callback)
            
            if not success:
                log_to_file(f"[STEP Exporter] Failed to add object {_g._export_current_index+1}")
            
            _g._export_current_index += 1
            
            # 更新进度：基于已完成对象数量计算百分比
            # 第一个对象完成后：1/9 = 11.1%，映射到 20-100% 范围 = 20 + 11.1% * 80 = 28.9%
            # 第九个对象完成后：9/9 = 100%，映射到 20-100% 范围 = 20 + 100% * 80 = 100%
            object_progress = (_g._export_current_index / len(_g._export_objects_data)) * 80 + 20
            update_progress(object_progress, f"已导出对象 {_g._export_current_index}/{len(_g._export_objects_data)}", context)
            
            # 返回 timer 继续处理下一个对象
            return 0.1
        
        # 阶段 4: 完成导出并写入文件
        elif _g._export_stage == 4:
            log_to_file(f"\n[STEP Exporter] Stage 4: Finalizing export...")
            
            success = _g.step_exporter.finalize_incremental_export()
            
            _g._export_stage = 5
            
            # 更新进度为 100%
            update_progress(100, "导出完成", context)
            
            # 结束进度条
            end_progress(context)
            
            if success:
                log_to_file(f"[STEP Exporter] Successfully exported {len(_g._export_objects_data)} object(s)")
            else:
                log_to_file(f"[STEP Exporter] Export failed")
            
            # 合并C++子进程产出的log文件
            try:
                _merge_log_files(os.path.dirname(params['filepath']), params['filepath'])
            except:
                pass
            
            # 关闭日志文件
            if _g._export_log_file and not _g._export_log_file.closed:
                _g._export_log_file.close()
            
            return None  # 停止 timer
        
        # 初始调用，设置阶段 1
        if _g._export_stage == 0:
            # 日志文件已在 execute() 中打开，此处不再重复打开
            _g._export_stage = 1
            return 0.1
            
    except Exception as e:
        error_msg = str(e)
        log_to_file(f"[STEP Exporter] Export error: {error_msg}")
        import traceback
        traceback.print_exc()
        end_progress(context)
        if _g._export_log_file and not _g._export_log_file.closed:
            _g._export_log_file.close()
        return None

# ====================== 导出操作类 ======================
