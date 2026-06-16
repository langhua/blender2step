// STEP Exporter curve shape functions - Main file
#include "../include/step_exporter_internal.h"

TopoDS_Shape create_shape_from_curve_data(const std::vector<std::map<std::string, PyObject*>>& splines_data, double scale) {
    if (splines_data.empty()) {
        std::cerr << "[DEBUG] No splines data" << std::endl;
        return TopoDS_Shape();
    }
    
    std::cout << "[STEP Exporter] Creating shape from curve data: " << splines_data.size() << " splines" << std::endl;
    
    BRep_Builder builder;
    TopoDS_Compound compound;
    builder.MakeCompound(compound);
    
    int valid_edge_count = 0;
    
    for (size_t spline_idx = 0; spline_idx < splines_data.size(); spline_idx++) {
        const auto& spline_info = splines_data[spline_idx];
        
        // 获取样条类型
        std::string spline_type = "POLY";
        auto type_it = spline_info.find("type");
        if (type_it != spline_info.end() && PyUnicode_Check(type_it->second)) {
            spline_type = PyUnicode_AsUTF8(type_it->second);
        }
        
        std::cout << "[STEP Exporter] Processing spline " << spline_idx << ": type=" << spline_type << std::endl;
        
        // 提取控制点
        std::vector<gp_Pnt> control_points = extract_control_points(spline_info);
        if (control_points.empty()) {
            std::cerr << "[STEP Exporter]   No valid control points" << std::endl;
            continue;
        }
        
        // 根据样条类型处理
        bool curve_created = false;
        bool close_curve = false;
        
        if (spline_type == "POLY") {
            curve_created = process_poly_spline(spline_info, control_points, builder, compound, valid_edge_count);
        } else if (spline_type == "BEZIER") {
            curve_created = process_bezier_spline(spline_info, control_points, builder, compound, valid_edge_count, close_curve);
        } else if (spline_type == "NURBS") {
            curve_created = process_nurbs_spline(spline_info, control_points, builder, compound, valid_edge_count, close_curve);
        } else {
            std::cerr << "[STEP Exporter]   Unknown spline type: " << spline_type << std::endl;
            continue;
        }
        
        if (!curve_created) {
            std::cerr << "[STEP Exporter]   Failed to create curve for spline " << spline_idx << std::endl;
        }
    }
    
    if (valid_edge_count == 0) {
        std::cerr << "[STEP Exporter] No valid edges created" << std::endl;
        return TopoDS_Shape();
    }
    
    std::cout << "[STEP Exporter] Created " << valid_edge_count << " edges from curve data" << std::endl;
    return compound;
}