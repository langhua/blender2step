"""Synchronous parametric export."""
import sys, os, math, time
import bpy
from ..core.utils import log_to_file
from ..core import _globals as _g

"""Parametric export functions for STEP Exporter."""
import sys, os, math, time
import bpy
from ..core.utils import log_to_file, _verify_step_shell, _merge_step_files, _merge_log_files
from .progress_report import update_progress, start_progress, end_progress
from ..core.mesh_data import _get_mesh_data_enhanced, _get_curve_data_enhanced
from ..core import _globals as _g

def _export_parametric_sync(filepath, bottom_shells, top_shells, cylinders, step_schema, step_unit, enable_logging, context):
    """同步导出所有参数化对象（底壳、顶壳、圆柱），用于后台模式回退"""
    import _step_exporter as cpp_exporter
    
    total = len(bottom_shells) + len(top_shells) + len(cylinders)
    if total == 0:
        log_to_file(f"[STEP Exporter] No parametric objects to export")
        return
    
    log_to_file(f"[STEP Exporter] Exporting {len(bottom_shells)} bottom + {len(top_shells)} top + {len(cylinders)} cylinders synchronously...")
    
    all_success = True
    temp_files = []
    temp_idx = 0
    
    # 导出底壳
    for idx, params in enumerate(bottom_shells):
        has_holes = params.get('has_holes', False)
        log_to_file(f"[STEP Exporter]   Exporting bottom shell {idx+1}/{len(bottom_shells)} ({'holes' if has_holes else 'no holes'})...")
        temp_file = filepath + f".temp{temp_idx}.step"
        temp_files.append(temp_file)
        temp_idx += 1
        
        if has_holes:
            success = cpp_exporter.export_bottom_shell_filleted_with_holes_step(
                temp_file, params['width'], params['depth'], params['outer_height'],
                params['bottom_thickness'], params['wall_thickness'], params['corner_radius'],
                params['outer_fillet_radius'], params['inner_fillet_radius'],
                params.get('step_height', 1.0), params.get('hole_radius', 1.5),
                params.get('hole_offset_x', 25.0), params.get('hole_offset_y', 20.0),
                params.get('pos_x', 0.0), params.get('pos_y', 0.0), params.get('pos_z', 0.0),
                step_schema, step_unit, 1 if enable_logging else 0)
        else:
            success = cpp_exporter.export_bottom_shell_filleted_step(
                temp_file, params['width'], params['depth'], params['outer_height'],
                params['bottom_thickness'], params['wall_thickness'], params['corner_radius'],
                params['outer_fillet_radius'], params['inner_fillet_radius'],
                params.get('step_height', 1.0), params.get('pos_x', 0.0),
                params.get('pos_y', 0.0), params.get('pos_z', 0.0),
                step_schema, step_unit, 1 if enable_logging else 0)
        if not success:
            all_success = False
            log_to_file(f"[STEP Exporter]   FAILED to export bottom shell {idx+1}")
        else:
            log_to_file(f"[STEP Exporter]   Bottom shell {idx+1} exported")
    
    # 导出顶壳
    for idx, tparams in enumerate(top_shells):
        log_to_file(f"[STEP Exporter]   Exporting top shell {idx+1}/{len(top_shells)}...")
        temp_file = filepath + f".temp{temp_idx}.step"
        temp_files.append(temp_file)
        temp_idx += 1
        
        success = cpp_exporter.export_top_shell_filleted_step(
            temp_file, tparams['width'], tparams['depth'], tparams['outer_height'],
            tparams['top_thickness'], tparams['wall_thickness'], tparams['corner_radius'],
            tparams['outer_fillet_radius'], tparams['inner_fillet_radius'],
            tparams['top_recess'], tparams['top_offset_y'],
            tparams.get('window_len', 0.0), tparams.get('window_wid', 0.0),
            tparams.get('step_ring_height', 0.0), tparams.get('step_ring_width', 0.0),
            tparams.get('pos_x', 0.0), tparams.get('pos_y', 0.0), tparams.get('pos_z', 0.0),
            step_schema, step_unit, tparams.get('window_data', ''),
            1 if enable_logging else 0)
        if not success:
            all_success = False
            log_to_file(f"[STEP Exporter]   FAILED to export top shell {idx+1}")
        else:
            log_to_file(f"[STEP Exporter]   Top shell {idx+1} exported")
    
    # 导出圆柱/圆锥
    for idx, cparams in enumerate(cylinders):
        obj_type = cparams.get('obj_type', 'cylinder')
        log_to_file(f"[STEP Exporter]   Exporting {obj_type} {idx+1}/{len(cylinders)}...")
        temp_file = filepath + f".temp{temp_idx}.step"
        temp_files.append(temp_file)
        temp_idx += 1
        
        px, py, pz = cparams.get('pos_x', 0.0), cparams.get('pos_y', 0.0), cparams.get('pos_z', 0.0)
        if obj_type == 'cylinder':
            success = cpp_exporter.export_cylinder_step(temp_file, cparams['radius'], cparams['height'],
                px, py, pz, step_schema, step_unit, 1 if enable_logging else 0)
        elif obj_type == 'cone':
            success = cpp_exporter.export_cone_step(temp_file, cparams['bottom_radius'], cparams['top_radius'],
                cparams['height'], px, py, pz, step_schema, step_unit, 1 if enable_logging else 0)
        elif obj_type == 'hollow_cylinder':
            success = cpp_exporter.export_hollow_cylinder_step(temp_file, cparams['outer_radius'],
                cparams['inner_radius'], cparams['height'], px, py, pz,
                step_schema, step_unit, 1 if enable_logging else 0)
        elif obj_type == 'hollow_cylinder_tapered':
            chamfer_sz = cparams.get('top_feature_size', 0) if cparams.get('top_feature') == 'chamfer' else 0
            fillet_sz = cparams.get('top_feature_size', 0) if cparams.get('top_feature') == 'fillet' else 0
            btm_chamfer_sz = cparams.get('bottom_feature_size', 0) if cparams.get('bottom_feature') == 'chamfer' else 0
            btm_fillet_sz = cparams.get('bottom_feature_size', 0) if cparams.get('bottom_feature') == 'fillet' else 0
            success = cpp_exporter.export_hollow_cylinder_tapered_step(
                temp_file, cparams['outer_radius'],
                cparams['inner_radius_top'], cparams['inner_radius_bottom'],
                cparams['height'],
                cparams.get('hole_fillet_radius', 0),
                chamfer_sz, fillet_sz, btm_chamfer_sz, btm_fillet_sz,
                px, py, pz,
                step_schema, step_unit, 1 if enable_logging else 0)
        elif obj_type == 'hollow_cylinder_fillet':
            fillet_sz = cparams.get('top_feature_size', 0)
            success = cpp_exporter.export_hollow_cylinder_fillet_step(
                temp_file, cparams['outer_radius'], cparams['inner_radius'],
                cparams['height'], fillet_sz,
                px, py, pz, step_schema, step_unit, 1 if enable_logging else 0)
        elif obj_type == 'cylinder_chamfer':
            top_sz = cparams.get('top_feature_size', 0) if cparams.get('top_feature') == 'chamfer' else 0
            btm_sz = cparams.get('bottom_feature_size', 0) if cparams.get('bottom_feature') == 'chamfer' else 0
            if btm_sz > 0.001 and top_sz < 0.001:
                success = cpp_exporter.export_cylinder_chamfer_both_step(
                    temp_file, cparams['radius'], cparams['height'],
                    0.0, btm_sz, px, py, pz,
                    step_schema, step_unit, 1 if enable_logging else 0)
            else:
                success = cpp_exporter.export_cylinder_chamfer_step(
                    temp_file, cparams['radius'], cparams['height'],
                    max(top_sz, btm_sz), px, py, pz,
                    step_schema, step_unit, 1 if enable_logging else 0)
        elif obj_type == 'cylinder_fillet':
            top_sz = cparams.get('top_feature_size', 0) if cparams.get('top_feature') == 'fillet' else 0
            btm_sz = cparams.get('bottom_feature_size', 0) if cparams.get('bottom_feature') == 'fillet' else 0
            if btm_sz > 0.001 and top_sz < 0.001:
                success = cpp_exporter.export_cylinder_fillet_both_step(
                    temp_file, cparams['radius'], cparams['height'],
                    0.0, btm_sz, px, py, pz,
                    step_schema, step_unit, 1 if enable_logging else 0)
            else:
                success = cpp_exporter.export_cylinder_fillet_step(
                    temp_file, cparams['radius'], cparams['height'],
                    max(top_sz, btm_sz), px, py, pz,
                    step_schema, step_unit, 1 if enable_logging else 0)
        elif obj_type == 'cylinder_chamfer_fillet':
            reversed_flag = 1 if cparams.get('top_feature') == 'fillet' else 0
            chamfer_sz = cparams.get('top_feature_size', 0)
            fillet_sz = cparams.get('bottom_feature_size', 0)
            if reversed_flag:
                # 当 reversed_flag=1 时，top_feature 是 fillet，bottom_feature 是 chamfer
                # 传入 C++ 的参数需要对应交换：chamfer_size = bottom_feature_size, fillet_radius = top_feature_size
                chamfer_sz, fillet_sz = fillet_sz, chamfer_sz
                log_to_file(f"[STEP Exporter]   reversed_flag=1, swapped chamfer/fillet sizes: chamfer={chamfer_sz:.6f} fillet={fillet_sz:.6f}")
            log_to_file(f"[STEP Exporter]   export params: r={cparams['radius']:.6f} h={cparams['height']:.6f} chamfer={chamfer_sz:.6f} fillet={fillet_sz:.6f} reversed={reversed_flag}")
            success = cpp_exporter.export_cylinder_chamfer_fillet_step(
                temp_file, cparams['radius'], cparams['height'],
                chamfer_sz, fillet_sz,
                px, py, pz, step_schema, step_unit,
                1 if enable_logging else 0, reversed_flag)
            if success:
                try:
                    shell_cnt, face_cnts = _verify_step_shell(temp_file)
                    expected = 5
                    actual = face_cnts[0] if face_cnts else 0
                    if actual < expected:
                        log_to_file(f"[STEP Exporter]   WARNING: expected {expected} faces, got {actual} - chamfer/fillet may have failed!")
                    log_to_file(f"[STEP Exporter]   verify: {shell_cnt} shells, face counts: {face_cnts}")
                except Exception as ve:
                    log_to_file(f"[STEP Exporter]   verify error: {ve}")
        elif obj_type == 'cylinder_chamfer_both':
            success = cpp_exporter.export_cylinder_chamfer_both_step(
                temp_file, cparams['radius'], cparams['height'],
                cparams.get('top_feature_size', 0),
                cparams.get('bottom_feature_size', 0),
                px, py, pz, step_schema, step_unit,
                1 if enable_logging else 0)
        elif obj_type == 'cylinder_fillet_both':
            success = cpp_exporter.export_cylinder_fillet_both_step(
                temp_file, cparams['radius'], cparams['height'],
                cparams.get('top_feature_size', 0),
                cparams.get('bottom_feature_size', 0),
                px, py, pz, step_schema, step_unit,
                1 if enable_logging else 0)
        elif obj_type == 'cylinder_blind_hole':
            hole_pos = cparams.get('hole_position', 'top')
            hole_r_bottom = cparams.get('hole_radius_bottom', 0.0)
            top_ch = cparams.get('top_chamfer', 0.0)
            top_fr = cparams.get('top_fillet', 0.0)
            btm_ch = cparams.get('bottom_chamfer', 0.0)
            btm_fr = cparams.get('bottom_fillet', 0.0)
            if hole_pos == 'both':
                success = cpp_exporter.export_cylinder_dual_blind_holes_step(
                    temp_file, cparams['radius'], cparams['height'],
                    cparams['hole_radius'], cparams['hole_depth'],
                    cparams.get('hole_depth_top', 0),
                    cparams.get('hole_fillet_radius', 0),
                    hole_r_bottom,
                    top_ch, top_fr, btm_ch, btm_fr,
                    px, py, pz, step_schema, step_unit,
                    1 if enable_logging else 0)
            else:
                success = cpp_exporter.export_cylinder_blind_hole_step(
                    temp_file, cparams['radius'], cparams['height'],
                    cparams['hole_radius'], cparams['hole_depth'],
                    cparams.get('hole_fillet_radius', 0),
                    hole_r_bottom,
                    hole_pos,
                    top_ch, top_fr, btm_ch, btm_fr,
                    px, py, pz, step_schema, step_unit,
                    1 if enable_logging else 0)
        elif obj_type == 'cone_chamfer':
            top_ch = cparams.get('top_feature_size', 0) if cparams.get('top_feature') == 'chamfer' else 0
            btm_ch = cparams.get('bottom_feature_size', 0) if cparams.get('bottom_feature') == 'chamfer' else 0
            success = cpp_exporter.export_cone_chamfer_step_both(
                temp_file, cparams['bottom_radius'], cparams['top_radius'], cparams['height'],
                btm_ch, top_ch,
                px, py, pz, step_schema, step_unit, 1 if enable_logging else 0)
        elif obj_type == 'cone_fillet':
            top_fr = cparams.get('top_feature_size', 0) if cparams.get('top_feature') == 'fillet' else 0
            btm_fr = cparams.get('bottom_feature_size', 0) if cparams.get('bottom_feature') == 'fillet' else 0
            success = cpp_exporter.export_cone_fillet_step_both(
                temp_file, cparams['bottom_radius'], cparams['top_radius'], cparams['height'],
                btm_fr, top_fr,
                px, py, pz, step_schema, step_unit, 1 if enable_logging else 0)
        elif obj_type == 'cone_chamfer_fillet':
            reversed_flag = 1 if cparams.get('top_feature') == 'chamfer' else 0
            chamfer_sz = cparams.get('top_feature_size', 0) if cparams.get('top_feature') == 'chamfer' else cparams.get('bottom_feature_size', 0)
            fillet_sz = cparams.get('top_feature_size', 0) if cparams.get('top_feature') == 'fillet' else cparams.get('bottom_feature_size', 0)
            success = cpp_exporter.export_cone_chamfer_fillet_step(
                temp_file, cparams['bottom_radius'], cparams['top_radius'], cparams['height'],
                chamfer_sz, fillet_sz,
                px, py, pz, step_schema, step_unit, 1 if enable_logging else 0, reversed_flag)
        elif obj_type == 'cone_blind_hole':
            hole_pos = cparams.get('hole_position', 'top')
            hole_r_bottom = cparams.get('hole_radius_bottom', 0.0)
            hole_depth_top = cparams.get('hole_depth_top', 0.0)
            top_ch = cparams.get('top_chamfer', 0.0)
            top_fr = cparams.get('top_fillet', 0.0)
            btm_ch = cparams.get('bottom_chamfer', 0.0)
            btm_fr = cparams.get('bottom_fillet', 0.0)
            success = cpp_exporter.export_cone_blind_hole_step(
                temp_file, cparams['bottom_radius'], cparams['top_radius'], cparams['height'],
                cparams['hole_radius'], cparams['hole_depth'],
                cparams.get('hole_fillet_radius', 0),
                hole_r_bottom, hole_depth_top,
                hole_pos,
                top_ch, top_fr, btm_ch, btm_fr,
                px, py, pz, step_schema, step_unit,
                1 if enable_logging else 0)
        elif obj_type == 'hollow_cone':
            top_ch = cparams.get('top_feature_size', 0) if cparams.get('top_feature') == 'chamfer' else 0
            top_fr = cparams.get('top_feature_size', 0) if cparams.get('top_feature') == 'fillet' else 0
            btm_ch = cparams.get('bottom_feature_size', 0) if cparams.get('bottom_feature') == 'chamfer' else 0
            btm_fr = cparams.get('bottom_feature_size', 0) if cparams.get('bottom_feature') == 'fillet' else 0
            success = cpp_exporter.export_hollow_cone_step(
                temp_file, cparams['outer_bottom_radius'], cparams['outer_top_radius'],
                cparams['inner_bottom_radius'], cparams['inner_top_radius'], cparams['height'],
                top_ch, top_fr, btm_ch, btm_fr,
                cparams.get('hole_fillet_radius', 0),
                px, py, pz, step_schema, step_unit, 1 if enable_logging else 0)
        elif obj_type == 'hollow_cone_fillet':
            fillet_sz = cparams.get('top_feature_size', 0)
            success = cpp_exporter.export_hollow_cone_fillet_step(
                temp_file, cparams['outer_bottom_radius'], cparams['outer_top_radius'],
                cparams['inner_bottom_radius'], cparams['inner_top_radius'], cparams['height'],
                fillet_sz,
                px, py, pz, step_schema, step_unit, 1 if enable_logging else 0)
        elif obj_type == 'hollow_cone_fillet_grooved':
            fillet_sz = cparams.get('top_feature_size', 0)
            groove_depth = cparams.get('groove_depth', 0)
            groove_bottom_width = cparams.get('groove_bottom_width', 0)
            groove_top_width = cparams.get('groove_top_width', 0)
            groove_extrusion_length = cparams.get('groove_extrusion_length', 0)
            success = cpp_exporter.export_hollow_cone_fillet_with_groove_step(
                temp_file, cparams['outer_bottom_radius'], cparams['outer_top_radius'],
                cparams['inner_bottom_radius'], cparams['inner_top_radius'], cparams['height'],
                fillet_sz, groove_depth, groove_bottom_width, groove_top_width,
                groove_extrusion_length,
                px, py, pz, step_schema, step_unit, 1 if enable_logging else 0)
        elif obj_type == 'cone_stepped_hole':
            top_fr = cparams.get('top_feature_size', 0) if cparams.get('top_feature') == 'fillet' else 0
            btm_fr = cparams.get('bottom_feature_size', 0) if cparams.get('bottom_feature') == 'fillet' else 0
            top_ch = cparams.get('top_feature_size', 0) if cparams.get('top_feature') == 'chamfer' else 0
            btm_ch = cparams.get('bottom_feature_size', 0) if cparams.get('bottom_feature') == 'chamfer' else 0
            hole_fr = cparams.get('hole_fillet_radius', 0)
            success = cpp_exporter.export_cone_stepped_hole_step(
                temp_file, cparams['outer_bottom_radius'], cparams['outer_top_radius'],
                cparams['height'],
                cparams['small_hole_radius'], cparams['small_hole_height'],
                cparams['inner_bottom_radius'], cparams['inner_top_radius'],
                top_fr, btm_fr, hole_fr, top_ch, btm_ch,
                px, py, pz, step_schema, step_unit, 1 if enable_logging else 0)
        else:
            success = False
        if not success:
            all_success = False
            log_to_file(f"[STEP Exporter]   FAILED to export {obj_type} {idx+1}")
        else:
            log_to_file(f"[STEP Exporter]   {obj_type} {idx+1} exported")
            # 验证导出结果
            shell_cnt, face_cnts = _verify_step_shell(temp_file)
            log_to_file(f"[STEP Exporter]   verify: {shell_cnt} shells, face counts: {face_cnts}")
    
    # 合并或复制
    successful_temp_files = [tf for tf in temp_files if os.path.exists(tf)]
    successful_count = len(successful_temp_files)
    
    if successful_count > 1:
        try:
            _merge_step_files(filepath, successful_temp_files)
            log_to_file(f"[STEP Exporter] Merged {successful_count}/{total} parametric objects into {filepath}")
        except Exception as merge_err:
            log_to_file(f"[STEP Exporter] Failed to merge STEP files: {merge_err}")
            import traceback
            log_to_file(traceback.format_exc())
            if os.path.exists(successful_temp_files[0]):
                import shutil
                shutil.copy2(successful_temp_files[0], filepath)
    elif successful_count == 1:
        # Single file: still run through merge to strip wireframe chain
        try:
            temp_file = successful_temp_files[0]
            temp_size = os.path.getsize(temp_file)
            log_to_file(f"[STEP Exporter] Merging single file: {temp_file} ({temp_size} bytes) -> {filepath}")
            _merge_step_files(filepath, [temp_file])
            log_to_file(f"[STEP Exporter] Single file merge OK")
        except Exception as merge_err:
            log_to_file(f"[STEP Exporter] _merge_step_files failed: {merge_err}, trying os.replace")
            try:
                os.replace(temp_file, filepath)
            except:
                import shutil
                shutil.copy2(temp_file, filepath)
                log_to_file(f"[STEP Exporter] shutil.copy2 also failed: {copy_err}")
    else:
        log_to_file(f"[STEP Exporter] No parametric objects exported successfully")
    
    # 合并后验证输出文件
    if successful_count > 0:
        out_shell_cnt, out_face_cnts = _verify_step_shell(filepath)
        log_to_file(f"[STEP Exporter] post-merge verify: {out_shell_cnt} shells, face counts: {out_face_cnts}")
    
    # 清理临时文件
    for tf in temp_files:
        for ext in ('', '.log'):
            try:
                if os.path.exists(tf + ext):
                    os.remove(tf + ext)
            except:
                pass
    
    if successful_count == total:
        update_progress(100, "参数化导出完成", context)
        log_to_file(f"[STEP Exporter] All {total} parametric object(s) exported successfully")
    elif successful_count > 0:
        update_progress(100, f"部分导出: {successful_count}/{total}个成功", context)
        log_to_file(f"[STEP Exporter] {successful_count}/{total} parametric objects exported")
    else:
        update_progress(100, "参数化导出失败", context)
        log_to_file(f"[STEP Exporter] No parametric objects exported")


