"""Staged parametric export functions."""
import sys, os, math, time
import bpy
from ..core.utils import log_to_file, _verify_step_shell, _merge_step_files, _merge_log_files
from .progress_report import update_progress, start_progress, end_progress
from ..core.mesh_data import _get_mesh_data_enhanced, _get_curve_data_enhanced
from ..core import _globals as _g


def _highlight_export_object(obj_params):
    """在 Blender 视图中高亮选中当前正在导出的物体。
    支持 cylinder params (含 'bl_obj' key) 和 regular Blender object。"""
    try:
        bl_obj = None
        if isinstance(obj_params, dict) and 'bl_obj' in obj_params:
            bl_obj = obj_params['bl_obj']
        elif hasattr(obj_params, 'select_set'):
            bl_obj = obj_params
        
        if bl_obj and hasattr(bl_obj, 'select_set'):
            # 清除所有选中，只选中当前物体
            for o in bpy.context.scene.objects:
                if hasattr(o, 'select_set'):
                    o.select_set(False)
            bl_obj.select_set(True)
            bpy.context.view_layer.objects.active = bl_obj
            # 强制刷新视图
            for area in bpy.context.screen.areas:
                if area.type == 'VIEW_3D':
                    area.tag_redraw()
    except Exception:
        pass  # 高亮失败不影响导出流程


def _export_as_mesh_fallback(cpp_exporter, temp_file, cparams, data):
    """参数化导出失败时的网格回退方案。获取 Blender 对象并作为网格 BREP 导出。"""
    bl_obj = cparams.get('bl_obj') if isinstance(cparams, dict) else None
    if bl_obj is None:
        log_to_file(f"[STEP Exporter]   ⚠ mesh fallback: no bl_obj reference, aborting")
        return False
    log_to_file(f"[STEP Exporter]   → mesh fallback for {bl_obj.name}")
    import bpy
    obj_data = _get_mesh_data_enhanced(bl_obj, bpy.context, scale=1000.0)
    if obj_data is None:
        log_to_file(f"[STEP Exporter]   ⚠ mesh fallback: _get_mesh_data_enhanced returned None")
        return False
    vert_count = len(obj_data.get('vertices', []))
    face_count = len(obj_data.get('faces', []))
    if vert_count > 50000:
        log_to_file(f"[STEP Exporter]   ⚠ mesh fallback SKIPPED: too large ({vert_count} verts)")
        return False
    log_to_file(f"[STEP Exporter]   mesh fallback: {vert_count} verts, {face_count} faces")
    _g._cpp_log_callback = lambda msg: log_to_file(msg)
    init_ok = cpp_exporter.init_incremental_export(
        temp_file, 1, 1000.0,
        1 if data['fix_geometry'] else 0,
        1 if data['create_solid'] else 0,
        1 if data['advanced_brep'] else 0,
        data['step_schema'], data['step_unit'],
        1 if data['enable_logging'] else 0,
        data.get('sew_tolerance', 0.001),
        _g._cpp_log_callback)
    if not init_ok:
        log_to_file(f"[STEP Exporter]   ⚠ mesh fallback: init_incremental_export failed")
        return False
    add_ok = cpp_exporter.add_object_to_export(obj_data, None)
    cpp_exporter.finalize_incremental_export()
    return add_ok

def _export_bottom_shells_sync(filepath, shells, step_schema, step_unit, enable_logging, context):
    """同步导出底壳（非计时器版本，直接在 execute 中调用）"""
    import _step_exporter as cpp_exporter
    
    if not shells:
        log_to_file(f"[STEP Exporter] No bottom shells to export")
        return
    
    log_to_file(f"[STEP Exporter] Exporting {len(shells)} shell(s) synchronously...")
    
    all_success = True
    total_shells = len(shells)
    temp_files = []
    
    # 导出每个底壳到临时文件
    for idx, params in enumerate(shells):
        has_holes = params.get('has_holes', False)
        shell_desc = f"with_holes" if has_holes else "no_holes"
        log_to_file(f"[STEP Exporter]   Exporting shell {idx+1}/{total_shells} ({shell_desc})...")
        
        temp_file = filepath + f".temp{idx}.step"
        temp_files.append(temp_file)
        
        if has_holes:
            success = cpp_exporter.export_bottom_shell_filleted_with_holes_step(
                temp_file,
                params['width'],
                params['depth'],
                params['outer_height'],
                params['bottom_thickness'],
                params['wall_thickness'],
                params['corner_radius'],
                params['outer_fillet_radius'],
                params['inner_fillet_radius'],
                params.get('step_height', 1.0),
                params.get('hole_radius', 1.5),
                params.get('hole_offset_x', 25.0),
                params.get('hole_offset_y', 20.0),
                params.get('pos_x', 0.0),
                params.get('pos_y', 0.0),
                params.get('pos_z', 0.0),
                step_schema,
                step_unit,
                1 if enable_logging else 0
            )
        else:
            success = cpp_exporter.export_bottom_shell_filleted_step(
                temp_file,
                params['width'],
                params['depth'],
                params['outer_height'],
                params['bottom_thickness'],
                params['wall_thickness'],
                params['corner_radius'],
                params['outer_fillet_radius'],
                params['inner_fillet_radius'],
                params.get('step_height', 1.0),
                params.get('pos_x', 0.0),
                params.get('pos_y', 0.0),
                params.get('pos_z', 0.0),
                step_schema,
                step_unit,
                1 if enable_logging else 0
            )
        
        if not success:
            all_success = False
            log_to_file(f"[STEP Exporter]   FAILED to export shell {idx+1}")
        else:
            log_to_file(f"[STEP Exporter]   Shell {idx+1} exported successfully")
    
    # 合并或复制最终文件
    if all_success and total_shells > 1:
        try:
            _merge_step_files(filepath, temp_files)
            log_to_file(f"[STEP Exporter] Merged {total_shells} shells into {filepath}")
        except Exception as merge_err:
            log_to_file(f"[STEP Exporter] Failed to merge STEP files: {merge_err}")
            import traceback
            log_to_file(traceback.format_exc())
            # 合并失败时至少保留第一个文件
            if os.path.exists(temp_files[0]):
                try:
                    import shutil
                    shutil.copy2(temp_files[0], filepath)
                except:
                    pass
        finally:
            # 清理临时文件及其日志
            for tf in temp_files:
                for ext in ('', '.log'):
                    try:
                        if os.path.exists(tf + ext):
                            os.remove(tf + ext)
                    except:
                        pass
    elif all_success and total_shells == 1:
        try:
            os.replace(temp_files[0], filepath)
        except:
            import shutil
            shutil.copy2(temp_files[0], filepath)
        finally:
            for ext in ('', '.log'):
                try:
                    if os.path.exists(temp_files[0] + ext):
                        os.remove(temp_files[0] + ext)
                except:
                    pass
    else:
        log_to_file(f"[STEP Exporter] Some shells failed to export, no output written")
    
    if all_success:
        update_progress(100, "底壳导出完成", context)
        log_to_file(f"[STEP Exporter] All {total_shells} bottom shell(s) exported successfully")
    else:
        update_progress(100, "部分底壳导出失败", context)
        log_to_file(f"[STEP Exporter] Some bottom shells failed to export")


def _export_cylinder_staged(cpp_exporter, temp_file, cparams, data):
    """导出单个圆柱/圆锥类型对象到临时文件，返回成功标志"""
    log_to_file(f"[STEP Exporter]   [VER:v2] _export_cylinder_staged entry, obj_type={cparams.get('obj_type', '?')}")
    obj_type = cparams.get('obj_type', 'cylinder')
    px = cparams.get('pos_x', 0.0)
    py = cparams.get('pos_y', 0.0)
    pz = cparams.get('pos_z', 0.0)
    
    if obj_type == 'cylinder':
        return cpp_exporter.export_cylinder_step(
            temp_file, cparams['radius'], cparams['height'],
            px, py, pz, data['step_schema'], data['step_unit'],
            1 if data['enable_logging'] else 0)
    elif obj_type == 'cone':
        return cpp_exporter.export_cone_step(
            temp_file, cparams['bottom_radius'], cparams['top_radius'],
            cparams['height'], px, py, pz,
            data['step_schema'], data['step_unit'],
            1 if data['enable_logging'] else 0)
    elif obj_type == 'hollow_cylinder':
        return cpp_exporter.export_hollow_cylinder_step(
            temp_file, cparams['outer_radius'], cparams['inner_radius'],
            cparams['height'], px, py, pz,
            data['step_schema'], data['step_unit'],
            1 if data['enable_logging'] else 0)
    elif obj_type == 'hollow_cylinder_tapered':
        chamfer_sz = cparams.get('top_feature_size', 0) if cparams.get('top_feature') == 'chamfer' else 0
        fillet_sz = cparams.get('top_feature_size', 0) if cparams.get('top_feature') == 'fillet' else 0
        btm_chamfer_sz = cparams.get('bottom_feature_size', 0) if cparams.get('bottom_feature') == 'chamfer' else 0
        btm_fillet_sz = cparams.get('bottom_feature_size', 0) if cparams.get('bottom_feature') == 'fillet' else 0
        return cpp_exporter.export_hollow_cylinder_tapered_step(
            temp_file, cparams['outer_radius'],
            cparams['inner_radius_top'], cparams['inner_radius_bottom'],
            cparams['height'],
            cparams.get('hole_fillet_radius', 0),
            chamfer_sz, fillet_sz, btm_chamfer_sz, btm_fillet_sz,
            px, py, pz,
            data['step_schema'], data['step_unit'],
            1 if data['enable_logging'] else 0)
    elif obj_type == 'hollow_cone':
        return cpp_exporter.export_hollow_cone_step(
            temp_file,
            cparams['outer_bottom_radius'], cparams['outer_top_radius'],
            cparams['inner_bottom_radius'], cparams['inner_top_radius'],
            cparams['height'],
            cparams.get('top_chamfer', 0), cparams.get('top_fillet', 0),
            cparams.get('bottom_chamfer', 0), cparams.get('bottom_fillet', 0),
            cparams.get('hole_fillet_radius', 0),
            px, py, pz,
            data['step_schema'], data['step_unit'],
            1 if data['enable_logging'] else 0)
    elif obj_type == 'cylinder_chamfer':
        top_sz = cparams.get('top_feature_size', 0) if cparams.get('top_feature') == 'chamfer' else 0
        btm_sz = cparams.get('bottom_feature_size', 0) if cparams.get('bottom_feature') == 'chamfer' else 0
        if btm_sz > 0.001 and top_sz < 0.001:
            # Bottom-only chamfer → use _both with only bottom
            return cpp_exporter.export_cylinder_chamfer_both_step(
                temp_file, cparams['radius'], cparams['height'],
                0.0, btm_sz, px, py, pz,
                data['step_schema'], data['step_unit'],
                1 if data['enable_logging'] else 0)
        return cpp_exporter.export_cylinder_chamfer_step(
            temp_file, cparams['radius'], cparams['height'],
            max(top_sz, btm_sz), px, py, pz,
            data['step_schema'], data['step_unit'],
            1 if data['enable_logging'] else 0)
    elif obj_type == 'cylinder_fillet':
        top_sz = cparams.get('top_feature_size', 0) if cparams.get('top_feature') == 'fillet' else 0
        btm_sz = cparams.get('bottom_feature_size', 0) if cparams.get('bottom_feature') == 'fillet' else 0
        if btm_sz > 0.001 and top_sz < 0.001:
            # Bottom-only fillet → use _both with only bottom
            return cpp_exporter.export_cylinder_fillet_both_step(
                temp_file, cparams['radius'], cparams['height'],
                0.0, btm_sz, px, py, pz,
                data['step_schema'], data['step_unit'],
                1 if data['enable_logging'] else 0)
        return cpp_exporter.export_cylinder_fillet_step(
            temp_file, cparams['radius'], cparams['height'],
            max(top_sz, btm_sz), px, py, pz,
            data['step_schema'], data['step_unit'],
            1 if data['enable_logging'] else 0)
    elif obj_type == 'cylinder_chamfer_fillet':
        reversed_flag = 1 if cparams.get('top_feature') == 'fillet' else 0
        chamfer_sz = cparams.get('top_feature_size', 0)
        fillet_sz = cparams.get('bottom_feature_size', 0)
        if reversed_flag:
            # 当 reversed_flag=1 时，top_feature 是 fillet，bottom_feature 是 chamfer
            # 传入 C++ 的参数需要对应交换：chamfer_size = bottom_feature_size, fillet_radius = top_feature_size
            chamfer_sz, fillet_sz = fillet_sz, chamfer_sz
        log_to_file(f"[STEP Exporter]   export params: r={cparams['radius']:.6f} h={cparams['height']:.6f} chamfer={chamfer_sz:.6f} fillet={fillet_sz:.6f} reversed={reversed_flag}")
        result = cpp_exporter.export_cylinder_chamfer_fillet_step(
            temp_file, cparams['radius'], cparams['height'],
            chamfer_sz, fillet_sz,
            px, py, pz,
            data['step_schema'], data['step_unit'],
            1 if data['enable_logging'] else 0, reversed_flag)
        # 验证导出结果——带倒角圆角的圆柱体应有 5 个面，最少 3 个
        if result:
            try:
                shell_cnt, face_cnts = _verify_step_shell(temp_file)
                expected = 5
                actual = face_cnts[0] if face_cnts else 0
                if actual < expected:
                    log_to_file(f"[STEP Exporter]   WARNING: expected {expected} faces, got {actual} - chamfer/fillet may have failed!")
                log_to_file(f"[STEP Exporter]   verify: {shell_cnt} shells, face counts: {face_cnts}")
            except Exception as ve:
                log_to_file(f"[STEP Exporter]   verify error: {ve}")
        return result
    elif obj_type == 'cylinder_chamfer_both':
        return cpp_exporter.export_cylinder_chamfer_both_step(
            temp_file, cparams['radius'], cparams['height'],
            cparams.get('top_feature_size', 0),
            cparams.get('bottom_feature_size', 0),
            px, py, pz,
            data['step_schema'], data['step_unit'],
            1 if data['enable_logging'] else 0)
    elif obj_type == 'cylinder_fillet_both':
        return cpp_exporter.export_cylinder_fillet_both_step(
            temp_file, cparams['radius'], cparams['height'],
            cparams.get('top_feature_size', 0),
            cparams.get('bottom_feature_size', 0),
            px, py, pz,
            data['step_schema'], data['step_unit'],
            1 if data['enable_logging'] else 0)
    elif obj_type == 'cylinder_blind_hole':
        hole_pos = cparams.get('hole_position', 'top')
        hole_r_bottom = cparams.get('hole_radius_bottom', 0.0)
        top_ch = cparams.get('top_chamfer', 0.0)
        top_fr = cparams.get('top_fillet', 0.0)
        btm_ch = cparams.get('bottom_chamfer', 0.0)
        btm_fr = cparams.get('bottom_fillet', 0.0)
        if hole_pos == 'both':
            return cpp_exporter.export_cylinder_dual_blind_holes_step(
                temp_file, cparams['radius'], cparams['height'],
                cparams['hole_radius'], cparams['hole_depth'],
                cparams.get('hole_depth_top', 0),
                cparams.get('hole_fillet_radius', 0),
                hole_r_bottom,
                top_ch, top_fr, btm_ch, btm_fr,
                px, py, pz,
                data['step_schema'], data['step_unit'],
                1 if data['enable_logging'] else 0,
                cparams.get('groove_depth', 0),
                cparams.get('groove_bottom_width', 0),
                cparams.get('groove_top_width', 0),
                cparams.get('groove_extrusion_length', 0))
        return cpp_exporter.export_cylinder_blind_hole_step(
            temp_file, cparams['radius'], cparams['height'],
            cparams['hole_radius'], cparams['hole_depth'],
            cparams.get('hole_fillet_radius', 0),
            hole_r_bottom,
            hole_pos,
            top_ch, top_fr, btm_ch, btm_fr,
            px, py, pz,
            data['step_schema'], data['step_unit'],
            1 if data['enable_logging'] else 0,
            cparams.get('groove_depth', 0),
            cparams.get('groove_bottom_width', 0),
            cparams.get('groove_top_width', 0),
            cparams.get('groove_extrusion_length', 0)),
    elif obj_type == 'cylinder_stepped_hole':
        top_ch = cparams.get('top_chamfer', 0.0)
        top_fr = cparams.get('top_fillet', 0.0)
        btm_ch = cparams.get('bottom_chamfer', 0.0)
        btm_fr = cparams.get('bottom_fillet', 0.0)
        # 安全校验：缺少关键台阶孔参数时回退到网格导出
        large_r = cparams.get('stepped_large_r', 0)
        large_h = cparams.get('stepped_large_h', 0)
        small_r = cparams.get('stepped_small_r', 0)
        if large_r <= 0 or large_h <= 0 or small_r <= 0:
            log_to_file(f"[STEP Exporter]   ⚠ cylinder_stepped_hole missing params (lr={large_r}, lh={large_h}, sr={small_r}), fallback to mesh")
            return _export_as_mesh_fallback(cpp_exporter, temp_file, cparams, data)
        return cpp_exporter.export_cylinder_stepped_hole_step(
            temp_file, cparams['radius'], cparams['height'],
            cparams['stepped_large_r'], cparams['stepped_large_h'],
            cparams['stepped_small_r'],
            cparams.get('hole_fillet_radius', 0),
            top_ch, top_fr, btm_ch, btm_fr,
            px, py, pz,
            data['step_schema'], data['step_unit'],
            1 if data['enable_logging'] else 0,
            cparams.get('groove_depth', 0),
            cparams.get('groove_bottom_width', 0),
            cparams.get('groove_top_width', 0),
            cparams.get('groove_extrusion_length', 0)),
    elif obj_type == 'cylinder_tapered_stepped_hole':
        top_ch = cparams.get('top_chamfer', 0.0)
        top_fr = cparams.get('top_fillet', 0.0)
        btm_ch = cparams.get('bottom_chamfer', 0.0)
        btm_fr = cparams.get('bottom_fillet', 0.0)
        # 安全校验：缺少关键锥形台阶孔参数时回退到网格导出
        taper_top = cparams.get('taper_top_r', 0)
        taper_step = cparams.get('taper_step_r', 0)
        stepped_small = cparams.get('stepped_small_r', 0)
        if taper_top <= 0 or taper_step <= 0 or stepped_small <= 0:
            log_to_file(f"[STEP Exporter]   ⚠ cylinder_tapered_stepped_hole missing taper params (top={taper_top}, step={taper_step}, small={stepped_small}), fallback to mesh")
            return _export_as_mesh_fallback(cpp_exporter, temp_file, cparams, data)
        return cpp_exporter.export_cylinder_tapered_stepped_hole_step(
            temp_file, cparams['radius'], cparams['height'],
            cparams['stepped_large_h'],
            cparams['taper_top_r'], cparams['taper_step_r'],
            cparams['stepped_small_r'],
            cparams.get('hole_fillet_radius', 0),
            top_ch, top_fr, btm_ch, btm_fr,
            px, py, pz,
            data['step_schema'], data['step_unit'],
            1 if data['enable_logging'] else 0,
            cparams.get('groove_depth', 0),
            cparams.get('groove_bottom_width', 0),
            cparams.get('groove_top_width', 0),
            cparams.get('groove_extrusion_length', 0)),
    elif obj_type == 'cone_groove':
        top_ch = cparams.get('top_chamfer', 0.0)
        top_fr = cparams.get('top_fillet', 0.0)
        btm_ch = cparams.get('bottom_chamfer', 0.0)
        btm_fr = cparams.get('bottom_fillet', 0.0)
        return cpp_exporter.export_cone_groove_step(
            temp_file,
            cparams['bottom_radius'], cparams['top_radius'], cparams['height'],
            cparams['groove_depth'], cparams['groove_bottom_width'],
            cparams['groove_top_width'], cparams['groove_extrusion_length'],
            top_ch, top_fr, btm_ch, btm_fr,
            px, py, pz,
            data['step_schema'], data['step_unit'],
            1 if data['enable_logging'] else 0)
    elif obj_type == 'grooved_cylinder':
        top_ch = cparams.get('top_chamfer', 0.0)
        top_fr = cparams.get('top_fillet', 0.0)
        btm_ch = cparams.get('bottom_chamfer', 0.0)
        btm_fr = cparams.get('bottom_fillet', 0.0)
        return cpp_exporter.export_cylinder_groove_step(
            temp_file, cparams['radius'], cparams['height'],
            cparams['groove_depth'], cparams['groove_bottom_width'],
            cparams['groove_top_width'], cparams['groove_extrusion_length'],
            top_ch, top_fr, btm_ch, btm_fr,
            px, py, pz,
            data['step_schema'], data['step_unit'],
            1 if data['enable_logging'] else 0)
    elif obj_type == 'cone_blind_hole':
        hole_pos = cparams.get('hole_position', 'top')
        hole_r_bottom = cparams.get('hole_radius_bottom', 0.0)
        hole_d_top = cparams.get('hole_depth_top', cparams.get('hole_depth', 0))
        top_ch = cparams.get('top_chamfer', 0.0)
        top_fr = cparams.get('top_fillet', 0.0)
        btm_ch = cparams.get('bottom_chamfer', 0.0)
        btm_fr = cparams.get('bottom_fillet', 0.0)
        return cpp_exporter.export_cone_blind_hole_step(
            temp_file, cparams['bottom_radius'], cparams['top_radius'],
            cparams['height'],
            cparams['hole_radius'], cparams['hole_depth'],
            cparams.get('hole_fillet_radius', 0),
            hole_r_bottom,
            hole_d_top,
            hole_pos,
            top_ch, top_fr, btm_ch, btm_fr,
            px, py, pz,
            data['step_schema'], data['step_unit'],
            1 if data['enable_logging'] else 0)
    elif obj_type == 'cone_blind_hole_groove':
        hole_pos = cparams.get('hole_position', 'top')
        hole_r_bottom = cparams.get('hole_radius_bottom', 0.0)
        hole_d_top = cparams.get('hole_depth_top', cparams.get('hole_depth', 0))
        top_ch = cparams.get('top_chamfer', 0.0)
        top_fr = cparams.get('top_fillet', 0.0)
        btm_ch = cparams.get('bottom_chamfer', 0.0)
        btm_fr = cparams.get('bottom_fillet', 0.0)
        # DEBUG: log all args
        _args = [
            temp_file,
            cparams['bottom_radius'], cparams['top_radius'], cparams['height'],
            cparams['hole_radius'], cparams['hole_depth'],
            cparams.get('hole_fillet_radius', 0),
            hole_r_bottom,
            hole_d_top,
            hole_pos,
            top_ch, top_fr, btm_ch, btm_fr,
            cparams['groove_depth'], cparams['groove_bottom_width'],
            cparams['groove_top_width'], cparams['groove_extrusion_length'],
            px, py, pz,
            data['step_schema'], data['step_unit'],
            1 if data['enable_logging'] else 0]
        print(f"[STEP Exporter] [DBG] cone_blind_hole_groove args: {[(type(a).__name__, a) for a in _args]}")
        return cpp_exporter.export_cone_blind_hole_groove_step(*_args)
    elif obj_type == 'cone_chamfer_fillet':
        # Determine feature order: C++ expects chamfer_size first, fillet_radius second
        # reversed=0: bottom chamfer + top fillet; reversed=1: bottom fillet + top chamfer
        bot_feat = cparams.get('bottom_feature')
        top_feat = cparams.get('top_feature')
        if bot_feat == 'fillet' and top_feat == 'chamfer':
            rev_flag = 1
            chamfer_sz = cparams.get('top_feature_size', 0)
            fillet_r = cparams.get('bottom_feature_size', 0)
        else:
            rev_flag = 0
            chamfer_sz = cparams.get('bottom_feature_size', 0)
            fillet_r = cparams.get('top_feature_size', 0)
        log_to_file(f"[STEP Exporter]   cone_chamfer_fillet: bR={cparams.get('bottom_radius',0):.4f} tR={cparams.get('top_radius',0):.4f} h={cparams['height']:.4f} chamfer_sz={chamfer_sz:.4f} fillet_r={fillet_r:.4f} reversed={rev_flag}")
        return cpp_exporter.export_cone_chamfer_fillet_step(
            temp_file,
            cparams.get('bottom_radius', cparams.get('radius', 0)),
            cparams.get('top_radius', 0), cparams['height'],
            chamfer_sz, fillet_r,
            px, py, pz,
            data['step_schema'], data['step_unit'],
            1 if data['enable_logging'] else 0,
            rev_flag)  # reversed as last optional arg
    elif obj_type == 'cone_chamfer':
        has_bottom = cparams.get('bottom_feature') == 'chamfer'
        has_top = cparams.get('top_feature') == 'chamfer'
        if has_bottom and has_top:
            bot_sz = cparams.get('bottom_feature_size', 0)
            top_sz = cparams.get('top_feature_size', 0)
            log_to_file(f"[STEP Exporter]   cone_chamfer(both): bot_sz={bot_sz:.4f} top_sz={top_sz:.4f}")
            return cpp_exporter.export_cone_chamfer_step_both(
                temp_file,
                cparams.get('bottom_radius', cparams.get('radius', 0)),
                cparams.get('top_radius', 0), cparams['height'],
                bot_sz, top_sz, px, py, pz,
                data['step_schema'], data['step_unit'],
                1 if data['enable_logging'] else 0)
        else:
            chamfer_sz = cparams.get('bottom_feature_size', 0) if has_bottom else cparams.get('top_feature_size', 0)
            is_top = 1 if has_top else 0
            log_to_file(f"[STEP Exporter]   cone_chamfer: chamfer_sz={chamfer_sz:.4f} is_top={is_top}")
            return cpp_exporter.export_cone_chamfer_fillet_step(
                temp_file,
                cparams.get('bottom_radius', cparams.get('radius', 0)),
                cparams.get('top_radius', 0), cparams['height'],
                chamfer_sz, 0,  # chamfer_size, fillet_radius=0
                px, py, pz,
                data['step_schema'], data['step_unit'],
                1 if data['enable_logging'] else 0,
                is_top)  # reversed=1 for top chamfer
    elif obj_type == 'hollow_cone_fillet':
        return cpp_exporter.export_hollow_cone_fillet_step(
            temp_file,
            cparams.get('outer_bottom_radius', cparams.get('outer_radius', 0)),
            cparams.get('outer_top_radius', cparams.get('outer_radius', 0)),
            cparams.get('inner_bottom_radius', cparams.get('inner_radius', 0)),
            cparams.get('inner_top_radius', cparams.get('inner_radius', 0)),
            cparams['height'], cparams.get('top_feature_size', 0),
            px, py, pz, data['step_schema'], data['step_unit'],
            1 if data['enable_logging'] else 0)
    elif obj_type == 'hollow_cone_fillet_grooved':
        return cpp_exporter.export_hollow_cone_fillet_with_groove_step(
            temp_file,
            cparams.get('outer_bottom_radius', cparams.get('outer_radius', 0)),
            cparams.get('outer_top_radius', cparams.get('outer_radius', 0)),
            cparams.get('inner_bottom_radius', cparams.get('inner_radius', 0)),
            cparams.get('inner_top_radius', cparams.get('inner_radius', 0)),
            cparams['height'], cparams.get('top_feature_size', 0),
            cparams.get('groove_depth', 0),
            cparams.get('groove_bottom_width', 0),
            cparams.get('groove_top_width', 0),
            cparams.get('groove_extrusion_length', 0),
            px, py, pz, data['step_schema'], data['step_unit'],
            1 if data['enable_logging'] else 0)
    elif obj_type == 'hollow_cone_grooved':
        # Hollow cone (through-hole) with trapezoidal groove
        top_ch = cparams.get('top_chamfer', 0.0)
        top_fr = cparams.get('top_fillet', 0.0)
        btm_ch = cparams.get('bottom_chamfer', 0.0)
        btm_fr = cparams.get('bottom_fillet', 0.0)
        return cpp_exporter.export_hollow_cone_fillet_with_groove_step(
            temp_file,
            cparams.get('outer_bottom_radius', cparams.get('outer_radius', 0)),
            cparams.get('outer_top_radius', cparams.get('outer_radius', 0)),
            cparams.get('inner_bottom_radius', cparams.get('inner_radius', 0)),
            cparams.get('inner_top_radius', cparams.get('inner_radius', 0)),
            cparams['height'], cparams.get('hole_fillet_radius', 0),
            cparams.get('groove_depth', 0),
            cparams.get('groove_bottom_width', 0),
            cparams.get('groove_top_width', 0),
            cparams.get('groove_extrusion_length', 0),
            top_ch, top_fr, btm_ch, btm_fr,
            px, py, pz, data['step_schema'], data['step_unit'],
            1 if data['enable_logging'] else 0)
    elif obj_type == 'hollow_cylinder_grooved':
        # Hollow cylinder (through-hole) with trapezoidal groove
        top_ch = cparams.get('top_feature_size', 0) if cparams.get('top_feature') == 'chamfer' else 0
        top_fr = cparams.get('top_feature_size', 0) if cparams.get('top_feature') == 'fillet' else 0
        btm_ch = cparams.get('bottom_feature_size', 0) if cparams.get('bottom_feature') == 'chamfer' else 0
        btm_fr = cparams.get('bottom_feature_size', 0) if cparams.get('bottom_feature') == 'fillet' else 0
        return cpp_exporter.export_hollow_cone_fillet_with_groove_step(
            temp_file,
            cparams.get('outer_bottom_radius', cparams.get('outer_radius', 0)),
            cparams.get('outer_top_radius', cparams.get('outer_radius', 0)),
            cparams.get('inner_bottom_radius', cparams.get('inner_radius', 0)),
            cparams.get('inner_top_radius', cparams.get('inner_radius', 0)),
            cparams['height'], cparams.get('hole_fillet_radius', 0),
            cparams.get('groove_depth', 0),
            cparams.get('groove_bottom_width', 0),
            cparams.get('groove_top_width', 0),
            cparams.get('groove_extrusion_length', 0),
            top_ch, top_fr, btm_ch, btm_fr,
            px, py, pz, data['step_schema'], data['step_unit'],
            1 if data['enable_logging'] else 0)
    elif obj_type == 'cone_stepped_hole':
        top_fr = cparams.get('top_feature_size', 0.0) if cparams.get('top_feature') == 'fillet' else 0.0
        btm_fr = cparams.get('bottom_feature_size', 0.0) if cparams.get('bottom_feature') == 'fillet' else 0.0
        top_ch = cparams.get('top_feature_size', 0.0) if cparams.get('top_feature') == 'chamfer' else 0.0
        btm_ch = cparams.get('bottom_feature_size', 0.0) if cparams.get('bottom_feature') == 'chamfer' else 0.0
        hole_fr = cparams.get('hole_fillet_radius', 0)
        log_to_file(f"[STEP Exporter]   cone_stepped_hole: top_ch={top_ch:.1f} top_fr={top_fr:.1f} btm_ch={btm_ch:.1f} btm_fr={btm_fr:.1f} hole_fr={hole_fr:.1f}")
        # 带外壁凹槽的锥体台阶孔：C++ 暂不支持，回退到网格导出
        if cparams.get('groove_depth', 0) > 0.01:
            log_to_file(f"[STEP Exporter]   cone_stepped_hole with groove not supported parametrically, fallback to mesh")
            return _export_as_mesh_fallback(cpp_exporter, temp_file, cparams, data)
        try:
            result = cpp_exporter.export_cone_stepped_hole_step(
                temp_file,
                cparams.get('outer_bottom_radius', cparams.get('outer_radius', 0)),
                cparams.get('outer_top_radius', cparams.get('outer_radius', 0)),
                cparams['height'],
                cparams.get('small_hole_radius', 0),
                cparams.get('small_hole_height', 0),
                cparams.get('inner_bottom_radius', cparams.get('inner_radius', 0)),
                cparams.get('inner_top_radius', cparams.get('inner_radius', 0)),
                top_fr, btm_fr, hole_fr, top_ch, btm_ch, px, py, pz, data['step_schema'], data['step_unit'],
                1 if data['enable_logging'] else 0)
            if result:
                return True
        except Exception as e:
            log_to_file(f"[STEP Exporter]   cone_stepped_hole parametric failed: {e}")
        log_to_file(f"[STEP Exporter]   cone_stepped_hole falling back to mesh export")
        return _export_as_mesh_fallback(cpp_exporter, temp_file, cparams, data)
    elif obj_type == 'cone_stepped_hole_groove':
        # C++ parametric may fail for tapered stepped holes; fall back to mesh
        try:
            top_fr = cparams.get('top_feature_size', 0.0) if cparams.get('top_feature') == 'fillet' else 0.0
            btm_fr = cparams.get('bottom_feature_size', 0.0) if cparams.get('bottom_feature') == 'fillet' else 0.0
            top_ch = cparams.get('top_feature_size', 0.0) if cparams.get('top_feature') == 'chamfer' else 0.0
            btm_ch = cparams.get('bottom_feature_size', 0.0) if cparams.get('bottom_feature') == 'chamfer' else 0.0
            hole_fr = cparams.get('hole_fillet_radius', 0)
            result = cpp_exporter.export_cone_stepped_hole_groove_step(
                temp_file,
                cparams.get('outer_bottom_radius', cparams.get('outer_radius', 0)),
                cparams.get('outer_top_radius', cparams.get('outer_radius', 0)),
                cparams['height'],
                cparams.get('small_hole_radius', 0),
                cparams.get('small_hole_height', 0),
                cparams.get('inner_bottom_radius', cparams.get('inner_radius', 0)),
                cparams.get('inner_top_radius', cparams.get('inner_radius', 0)),
                top_fr, btm_fr, hole_fr, top_ch, btm_ch,
                cparams['groove_depth'], cparams['groove_bottom_width'],
                cparams['groove_top_width'], cparams['groove_extrusion_length'],
                px, py, pz, data['step_schema'], data['step_unit'],
                1 if data['enable_logging'] else 0)
            if result:
                return True
        except Exception as e:
            log_to_file(f"[STEP Exporter]   cone_stepped_hole_groove parametric failed: {e}, fallback to mesh")
        log_to_file(f"[STEP Exporter]   cone_stepped_hole_groove falling back to mesh export")
        return _export_as_mesh_fallback(cpp_exporter, temp_file, cparams, data)
    elif obj_type == 'cone_fillet':
        has_bottom = cparams.get('bottom_feature') == 'fillet'
        has_top = cparams.get('top_feature') == 'fillet'
        if has_bottom and has_top:
            bot_r = cparams.get('bottom_feature_size', 0)
            top_r = cparams.get('top_feature_size', 0)
            log_to_file(f"[STEP Exporter]   cone_fillet(both): bot_r={bot_r:.4f} top_r={top_r:.4f}")
            return cpp_exporter.export_cone_fillet_step_both(
                temp_file,
                cparams.get('bottom_radius', cparams.get('radius', 0)),
                cparams.get('top_radius', 0), cparams['height'],
                bot_r, top_r, px, py, pz,
                data['step_schema'], data['step_unit'],
                1 if data['enable_logging'] else 0)
        else:
            # has_bottom XOR has_top: only one side has fillet
            is_bottom = has_bottom
            fr = cparams.get('bottom_feature_size', 0) if has_bottom else cparams.get('top_feature_size', 0)
            return cpp_exporter.export_cone_chamfer_fillet_step(
                temp_file,
                cparams.get('bottom_radius', 0), cparams.get('top_radius', 0),
                cparams['height'], 0.0, fr,
                px, py, pz, data['step_schema'], data['step_unit'],
                1 if data['enable_logging'] else 0,
                1 if is_bottom else 0)  # reversed=1: bottom fillet; 0: top fillet
    elif obj_type == 'hollow_cylinder_fillet':
        return cpp_exporter.export_hollow_cylinder_fillet_step(
            temp_file,
            cparams.get('outer_radius', 0), cparams.get('inner_radius', 0),
            cparams['height'], cparams.get('top_feature_size', 0),
            px, py, pz, data['step_schema'], data['step_unit'],
            1 if data['enable_logging'] else 0)
    else:
        log_to_file(f"[STEP Exporter]   Unknown cylinder type: {obj_type}")
        return False


def _parametric_export_staged():
    """分阶段异步导出参数化物体。
    每个对象在独立的 timer tick 中处理，保证 Blender UI 能刷新进度条。
    返回正数表示继续下一个 tick，返回 None 表示完成/停止。
    """
    
    import time
    
    if not _g._bottom_shell_export_data:
        return None
    
    data = None
    try:
        data = _g._bottom_shell_export_data
        context = data['context']
        shells = data.get('shells', [])
        top_shells_data = data.get('top_shells', [])
        cylinders = data.get('cylinders', [])
        regular_objects = data.get('regular_objects', [])
        
        import _step_exporter as cpp_exporter
        
        # === Stage 0: Init — 构建对象列表 ===
        if _g._parametric_export_stage == 0:
            _g._export_start_time = time.time()
            _g._stage_start_time = time.time()
            
            total_objects = len(shells) + len(top_shells_data) + len(cylinders) + len(regular_objects)
            if total_objects == 0:
                log_to_file(f"[STEP Exporter] No objects to export")
                end_progress(context)
                _g._bottom_shell_export_data = None
                _g._export_complete = True
                _g._export_success = True
                return None
            
            log_to_file(f"[STEP Exporter] Staged export: {len(shells)} bottom + {len(top_shells_data)} top + {len(cylinders)} cyl + {len(regular_objects)} mesh")
            _g._parametric_export_stage = 1
            _g._parametric_export_idx = 0
            _g._parametric_temp_files = []
            _g._parametric_progress_val = 10.0
            update_progress(10, f"开始导出 ({total_objects}个对象)...", context)
            
            elapsed = time.time() - _g._stage_start_time
            log_to_file(f"[STEP Exporter] [TIMING] Stage 0 (Init) completed in {elapsed:.3f}s")
            return 0.05
        
        # 构建扁平化对象列表（只在 stage 1 需要）
        all_objects = []
        for params in shells:
            all_objects.append(('bottom_shell', params))
        for tparams in top_shells_data:
            all_objects.append(('top_shell', tparams))
        for cparams in cylinders:
            all_objects.append(('cylinder', cparams))
        for obj in regular_objects:
            all_objects.append(('regular', obj))
        total_objects = len(all_objects)
        
        # === Stage 1: 逐个导出对象 ===
        if _g._parametric_export_stage == 1:
            if _g._parametric_export_idx == 0:
                _g._stage_start_time = time.time()
            
            if _g._parametric_export_idx >= total_objects:
                _g._parametric_export_stage = 2
                elapsed = time.time() - _g._stage_start_time
                log_to_file(f"[STEP Exporter] [TIMING] Stage 1 (Export {total_objects} objects) completed in {elapsed:.3f}s")
                return 0.05
            
            obj_type, obj_params = all_objects[_g._parametric_export_idx]
            obj_num = _g._parametric_export_idx + 1
            temp_file = data['filepath'] + f".temp{_g._parametric_export_idx}.step"
            _g._parametric_temp_files.append(temp_file)
            success = False
            
            # === 高亮当前正在导出的 Blender 物体 ===
            _highlight_export_object(obj_params)
            
            obj_start = time.time()
            try:
                if obj_type == 'bottom_shell':
                    params = obj_params
                    has_holes = params.get('has_holes', False)
                    desc = "with_holes" if has_holes else "no_holes"
                    log_to_file(f"[STEP Exporter] Exporting bottom shell {obj_num}/{total_objects} ({desc})...")
                    
                    if has_holes:
                        success = cpp_exporter.export_bottom_shell_filleted_with_holes_step(
                            temp_file, params['width'], params['depth'], params['outer_height'],
                            params['bottom_thickness'], params['wall_thickness'],
                            params['corner_radius'], params['outer_fillet_radius'],
                            params['inner_fillet_radius'],
                            params.get('step_height', 1.0), params.get('hole_radius', 1.5),
                            params.get('hole_offset_x', 25.0), params.get('hole_offset_y', 20.0),
                            params.get('pos_x', 0.0), params.get('pos_y', 0.0), params.get('pos_z', 0.0),
                            data['step_schema'], data['step_unit'],
                            1 if data['enable_logging'] else 0)
                    else:
                        success = cpp_exporter.export_bottom_shell_filleted_step(
                            temp_file, params['width'], params['depth'], params['outer_height'],
                            params['bottom_thickness'], params['wall_thickness'],
                            params['corner_radius'], params['outer_fillet_radius'],
                            params['inner_fillet_radius'],
                            params.get('step_height', 1.0),
                            params.get('pos_x', 0.0), params.get('pos_y', 0.0), params.get('pos_z', 0.0),
                            data['step_schema'], data['step_unit'],
                            1 if data['enable_logging'] else 0)
                
                elif obj_type == 'top_shell':
                    tparams = obj_params
                    log_to_file(f"[STEP Exporter] Exporting top shell {obj_num}/{total_objects}...")
                    success = cpp_exporter.export_top_shell_filleted_step(
                        temp_file, tparams['width'], tparams['depth'], tparams['outer_height'],
                        tparams['top_thickness'], tparams['wall_thickness'],
                        tparams['corner_radius'], tparams['outer_fillet_radius'],
                        tparams['inner_fillet_radius'], tparams['top_recess'],
                        tparams['top_offset_y'],
                        tparams.get('window_len', 0.0), tparams.get('window_wid', 0.0),
                        tparams.get('step_ring_height', 0.0), tparams.get('step_ring_width', 0.0),
                        tparams.get('pos_x', 0.0), tparams.get('pos_y', 0.0), tparams.get('pos_z', 0.0),
                        data['step_schema'], data['step_unit'], tparams.get('window_data', ''),
                        1 if data['enable_logging'] else 0)
                
                elif obj_type == 'cylinder':
                    cparams = obj_params
                    obj_subtype = cparams.get('obj_type', 'cylinder')
                    log_to_file(f"[STEP Exporter] Exporting {obj_subtype} {obj_num}/{total_objects}...")
                    success = _export_cylinder_staged(cpp_exporter, temp_file, cparams, data)
                
                elif obj_type == 'regular':
                    obj = obj_params
                    log_to_file(f"[STEP Exporter] Exporting mesh {obj_num}/{total_objects}: {obj.name}...")
                    obj_data = _get_mesh_data_enhanced(obj, context, scale=1000.0)
                    if obj_data is None:
                        raise RuntimeError("_get_mesh_data_enhanced returned None")
                    
                    # 网格大小安全检查：超大网格会导致 C++ OCCT 内核崩溃
                    vert_count = len(obj_data.get('vertices', []))
                    face_count = len(obj_data.get('faces', []))
                    MAX_SAFE_VERTS = 50000
                    if vert_count > MAX_SAFE_VERTS:
                        log_to_file(f"[STEP Exporter]   ⚠ SKIPPING {obj.name}: mesh too large ({vert_count} verts, {face_count} faces > limit {MAX_SAFE_VERTS})")
                        log_to_file(f"[STEP Exporter]   Object {obj_num}/{total_objects} SKIPPED (large mesh)")
                        success = False
                        # 更新进度后继续下一个
                    else:
                        _g._cpp_log_callback = lambda msg: log_to_file(msg)
                        init_ok = cpp_exporter.init_incremental_export(
                            temp_file, 1, 1000.0,
                            1 if data['fix_geometry'] else 0,
                            1 if data['create_solid'] else 0,
                            1 if data['advanced_brep'] else 0,
                            data['step_schema'], data['step_unit'],
                            1 if data['enable_logging'] else 0,
                            data.get('sew_tolerance', 0.001),
                            _g._cpp_log_callback)
                        if init_ok:
                            add_ok = cpp_exporter.add_object_to_export(obj_data, None)
                            cpp_exporter.finalize_incremental_export()
                            if add_ok:
                                log_to_file(f"[STEP Exporter]   Mesh {obj.name} exported ({len(obj_data['vertices'])} verts, {len(obj_data['faces'])} tris)")
                                success = True
                            else:
                                log_to_file(f"[STEP Exporter]   FAILED to add mesh {obj.name}")
                        else:
                            log_to_file(f"[STEP Exporter]   FAILED init incremental for {obj.name}")
                
                if success:
                    log_to_file(f"[STEP Exporter]   Object {obj_num}/{total_objects} OK ({time.time()-obj_start:.3f}s)")
                    # 验证导出结果
                    shell_cnt, face_cnts = _verify_step_shell(temp_file)
                    log_to_file(f"[STEP Exporter]   verify: {shell_cnt} shells, face counts: {face_cnts}")
                else:
                    log_to_file(f"[STEP Exporter]   Object {obj_num}/{total_objects} FAILED ({time.time()-obj_start:.3f}s)")
            except Exception as obj_err:
                log_to_file(f"[STEP Exporter]   ERROR exporting object {obj_num}: {obj_err} ({time.time()-obj_start:.3f}s)")
                import traceback
                log_to_file(traceback.format_exc())
            
            # 更新进度（10%-90% 之间均匀分布）
            _g._parametric_progress_val = 10.0 + (80.0 / max(total_objects, 1)) * obj_num
            type_names = {'bottom_shell': '底壳', 'top_shell': '顶壳', 'cylinder': '圆柱', 'regular': '网格'}
            type_name = type_names.get(obj_type, obj_type)
            update_progress(int(_g._parametric_progress_val), f"导出{type_name} {obj_num}/{total_objects}", context)
            
            _g._parametric_export_idx += 1
            return 0.05  # 继续下一个 tick
        
        # === Stage 2: 合并临时文件 ===
        elif _g._parametric_export_stage == 2:
            _g._stage_start_time = time.time()
            update_progress(90, "正在合并文件...", context)
            
            successful_temp_files = [tf for tf in _g._parametric_temp_files if os.path.exists(tf)]
            successful_count = len(successful_temp_files)
            
            if successful_count > 1:
                try:
                    # Python merge (fixed entity renumbering) as primary
                    _merge_step_files(data['filepath'], successful_temp_files)
                    log_to_file(f"[STEP Exporter] Python merge: {successful_count} objects into {data['filepath']}")
                except Exception as merge_err:
                    log_to_file(f"[STEP Exporter] Python merge failed: {merge_err}, trying C++ fallback")
                    import traceback
                    log_to_file(traceback.format_exc())
                    try:
                        result = cpp_exporter.merge_step_files(data['filepath'], successful_temp_files,
                            data['step_schema'], data['step_unit'],
                            1 if data['enable_logging'] else 0)
                        if result and result > 0:
                            log_to_file(f"[STEP Exporter] C++ fallback: merged {result} shapes")
                        else:
                            log_to_file(f"[STEP Exporter] Both merges failed")
                    except Exception as cpp_err:
                        log_to_file(f"[STEP Exporter] C++ fallback also failed: {cpp_err}")
                        if os.path.exists(successful_temp_files[0]):
                            try:
                                import shutil
                                shutil.copy2(successful_temp_files[0], data['filepath'])
                            except:
                                pass
                finally:
                    try:
                        _merge_log_files(os.path.dirname(data['filepath']), data['filepath'])
                    except:
                        pass
            elif successful_count == 1:
                try:
                    temp_file = successful_temp_files[0]
                    temp_size = os.path.getsize(temp_file) if os.path.exists(temp_file) else -1
                    log_to_file(f"[STEP Exporter] Merging single file: {temp_file} ({temp_size} bytes) -> {data['filepath']}")
                    os.replace(temp_file, data['filepath'])
                    log_to_file(f"[STEP Exporter] Single file merge OK")
                except Exception as merge_err:
                    log_to_file(f"[STEP Exporter] os.replace failed: {merge_err}, trying shutil.copy2")
                    import shutil
                    try:
                        shutil.copy2(temp_file, data['filepath'])
                        log_to_file(f"[STEP Exporter] shutil.copy2 fallback OK")
                    except Exception as copy_err:
                        log_to_file(f"[STEP Exporter] shutil.copy2 also failed: {copy_err}")
                finally:
                    try:
                        _merge_log_files(os.path.dirname(data['filepath']), data['filepath'])
                    except:
                        pass
            
            # 清理临时文件
            for tf in _g._parametric_temp_files:
                for ext in ('', '.log'):
                    try:
                        if os.path.exists(tf + ext):
                            os.remove(tf + ext)
                    except:
                        pass
            
            _g._parametric_temp_success_count = successful_count  # 保存成功计数供 Stage 3 使用
            _g._parametric_export_stage = 3
            elapsed = time.time() - _g._stage_start_time
            log_to_file(f"[STEP Exporter] [TIMING] Stage 2 (Merge) completed in {elapsed:.3f}s")
            # 合并后验证输出文件
            if successful_count > 0:
                out_shell_cnt, out_face_cnts = _verify_step_shell(data['filepath'])
                log_to_file(f"[STEP Exporter] post-merge verify: {out_shell_cnt} shells, face counts: {out_face_cnts}")
            return 0.05  # 进入完成阶段
        
        # === Stage 3: 完成 ===
        elif _g._parametric_export_stage == 3:
            successful_count = _g._parametric_temp_success_count
            total_for_count = max(total_objects, 1)
            
            if successful_count == total_for_count:
                update_progress(100, "参数化导出完成", context)
            elif successful_count > 0:
                update_progress(100, f"部分导出: {successful_count}/{total_for_count}个成功", context)
            else:
                update_progress(100, "参数化导出失败", context)
            
            end_progress(context)
            _g._bottom_shell_export_data = None
            _g._export_success = (successful_count > 0)
            _g._export_complete = True
            
            total_elapsed = time.time() - _g._export_start_time
            log_to_file(f"[STEP Exporter] [TIMING] Total export completed in {total_elapsed:.3f}s")
            
            if _g._export_log_file and not _g._export_log_file.closed:
                try:
                    _g._export_log_file.close()
                except:
                    pass
            return None  # 停止 timer
        
        return None  # 未知阶段，安全停止
        
    except Exception as e:
        log_to_file(f"[STEP Exporter] CRITICAL ERROR in staged parametric export: {e}")
        import traceback
        log_to_file(traceback.format_exc())
        try:
            if data and 'context' in data:
                end_progress(data['context'])
        except:
            pass
        _g._bottom_shell_export_data = None
        _g._export_complete = True
        _g._export_success = False
        if _g._export_log_file and not _g._export_log_file.closed:
            try:
                _g._export_log_file.close()
            except:
                pass
        return None


def _verify_step_shell(filepath):
    """快速验证 STEP 文件中的 CLOSED_SHELL 面数，用于诊断导出问题。
    返回 (shell_count, face_counts_list) 或 (0, []) 如果文件不存在."""
    import re
    if not os.path.exists(filepath):
        return 0, []
    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        # 查找所有 CLOSED_SHELL 定义: #N=CLOSED_SHELL('name',(#F1,#F2,...));
        shells = re.findall(r'#\d+\s*=\s*CLOSED_SHELL\s*\([^,]*,\s*\(([^)]*)\)', content)
        face_counts = []
        for s in shells:
            faces = [x.strip() for x in s.split(',') if x.strip().startswith('#')]
            face_counts.append(len(faces))
        return len(shells), face_counts
    except Exception:
        return 0, []


def _merge_log_files(output_dir, output_path):
    """将同目录下其他 .step.log 文件中的 [STEP Exporter] 行合并到主日志文件"""
    import re
    
    if not _g._export_log_file or _g._export_log_file.closed:
        return
    
    try:
        log_dir = os.path.dirname(output_path)
        main_log_basename = os.path.basename(output_path) + ".log"
        
        # 查找同目录下所有 .step.log 文件
        for fname in sorted(os.listdir(log_dir)):
            if fname == main_log_basename:
                continue
            if not fname.endswith('.step.log') and not fname.endswith('.step.log.temp'):
                continue
            
            log_path = os.path.join(log_dir, fname)
            try:
                with open(log_path, 'r', encoding='utf-8', errors='ignore') as lf:
                    content = lf.read()
                # 提取 [STEP Exporter] 开头的行
                step_lines = re.findall(r'\[STEP Exporter\].*', content)
                if step_lines:
                    _g._export_log_file.write(f"\n--- Merged from {fname} ---\n")
                    for line in step_lines:
                        if not line.endswith('\n'):
                            line += '\n'
                        _g._export_log_file.write(line)
                    _g._export_log_file.flush()
            except:
                pass
    except:
        pass


