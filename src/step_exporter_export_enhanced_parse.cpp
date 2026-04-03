// STEP Exporter enhanced export argument parsing
#include "../include/step_exporter_internal.h"

bool parse_export_args(PyObject* args, 
                       const char*& filename, 
                       PyObject*& scene_data_list, 
                       double& scale, 
                       int& fix_geometry, 
                       int& create_solid, 
                       int& advanced_brep, 
                       const char*& step_schema, 
                       const char*& unit, 
                       int& enable_logging, 
                       double& sew_tolerance, 
                       PyObject*& progress_callback) {
    // 设置默认值（与export_scene_enhanced一致）
    scale = 1.0;
    fix_geometry = 1;
    create_solid = 1;
    advanced_brep = 1;
    step_schema = "AP214IS";
    unit = "MILLIMETER";
    enable_logging = 1;
    sew_tolerance = 0.001;
    progress_callback = NULL;

    // 解析参数：filename, scene_data_list, scale, [fix_geometry], [create_solid], [advanced_brep], [step_schema], [unit], [enable_logging], [sew_tolerance], [progress_callback]
    // 尝试解析11个参数（包含进度回调）
    if (!PyArg_ParseTuple(args, "sOd|iiissidO", &filename, &scene_data_list, &scale, &fix_geometry, &create_solid, &advanced_brep, &step_schema, &unit, &enable_logging, &sew_tolerance, &progress_callback)) {
        // 如果失败，尝试解析10个参数（无进度回调）
        PyErr_Clear();
        if (!PyArg_ParseTuple(args, "sOd|iiissid", &filename, &scene_data_list, &scale, &fix_geometry, &create_solid, &advanced_brep, &step_schema, &unit, &enable_logging, &sew_tolerance)) {
            PyErr_SetString(PyExc_TypeError, "export_scene_enhanced() expected: filename, scene_data_list, scale, [fix_geometry], [create_solid], [advanced_brep], [step_schema], [unit], [enable_logging], [sew_tolerance], [progress_callback]");
            return false;
        }
    }
    
    // 如果提供了进度回调，检查是否为可调用对象
    if (progress_callback != NULL && progress_callback != Py_None) {
        if (!PyCallable_Check(progress_callback)) {
            PyErr_SetString(PyExc_TypeError, "progress_callback must be callable");
            return false;
        }
        // 增加引用计数，确保回调对象在函数执行期间有效
        Py_INCREF(progress_callback);
    } else {
        progress_callback = NULL;
    }

    return true;
}