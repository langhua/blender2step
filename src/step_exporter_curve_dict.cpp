// STEP Exporter curve dictionary functions
#include "../include/step_exporter_internal.h"

// 从Python字典创建曲线形状
TopoDS_Shape create_shape_from_curve_dict(PyObject* obj_dict, double scale) {
    if (!obj_dict || !PyDict_Check(obj_dict)) {
        std::cerr << "[STEP Exporter] Invalid curve dictionary" << std::endl;
        return TopoDS_Shape();
    }
    
    // 获取splines列表
    PyObject* splines_obj = PyDict_GetItemString(obj_dict, "splines");
    if (!splines_obj || !PyList_Check(splines_obj)) {
        std::cerr << "[STEP Exporter] No valid splines list in curve data" << std::endl;
        return TopoDS_Shape();
    }
    
    Py_ssize_t num_splines = PyList_Size(splines_obj);
    std::cout << "[STEP Exporter] Curve data contains " << num_splines << " splines" << std::endl;
    
    // 将Python样条数据转换为C++结构
    std::vector<std::map<std::string, PyObject*>> splines_data;
    
    for (Py_ssize_t i = 0; i < num_splines; i++) {
        PyObject* spline_dict = PyList_GetItem(splines_obj, i);
        if (!spline_dict || !PyDict_Check(spline_dict)) {
            std::cerr << "[STEP Exporter]   Spline " << i << " is not a dictionary, skipping" << std::endl;
            continue;
        }
        
        std::map<std::string, PyObject*> spline_info;
        
        // 获取样条类型
        PyObject* type_obj = PyDict_GetItemString(spline_dict, "type");
        if (type_obj) {
            spline_info["type"] = type_obj;
        }
        
        // 获取控制点
        PyObject* control_points_obj = PyDict_GetItemString(spline_dict, "control_points");
        if (control_points_obj) {
            spline_info["control_points"] = control_points_obj;
        }
        
        // 获取权重（如果存在）
        PyObject* weights_obj = PyDict_GetItemString(spline_dict, "weights");
        if (weights_obj) {
            spline_info["weights"] = weights_obj;
        }
        
        // 获取节点向量（如果存在）
        PyObject* knots_obj = PyDict_GetItemString(spline_dict, "knots_u");
        if (knots_obj) {
            spline_info["knots_u"] = knots_obj;
        }
        
        // 获取阶数（如果存在）
        PyObject* order_obj = PyDict_GetItemString(spline_dict, "order");
        if (order_obj) {
            spline_info["order"] = order_obj;
        }
        
        // 获取闭合标志（如果存在）
        PyObject* cyclic_obj = PyDict_GetItemString(spline_dict, "use_cyclic_u");
        if (cyclic_obj) {
            spline_info["use_cyclic_u"] = cyclic_obj;
        }
        
        // 获取圆心信息（用于有理NURBS圆的解析表示）
        PyObject* circle_center_obj = PyDict_GetItemString(spline_dict, "circle_center");
        if (circle_center_obj) {
            spline_info["circle_center"] = circle_center_obj;
        }
        
        // 获取半径信息（用于有理NURBS圆的解析表示）
        PyObject* circle_radius_obj = PyDict_GetItemString(spline_dict, "circle_radius");
        if (circle_radius_obj) {
            spline_info["circle_radius"] = circle_radius_obj;
        }
        
        splines_data.push_back(spline_info);
        std::cout << "[STEP Exporter]   Added spline " << i << " data" << std::endl;
    }
    
    if (splines_data.empty()) {
        std::cerr << "[STEP Exporter] No valid splines data extracted" << std::endl;
        return TopoDS_Shape();
    }
    
    // 调用现有的曲线创建函数
    return create_shape_from_curve_data(splines_data, scale);
}