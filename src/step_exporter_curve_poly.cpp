// STEP Exporter POLY curve processing functions
#include "../include/step_exporter_internal.h"

bool process_poly_spline(const std::map<std::string, PyObject*>& spline_info, const std::vector<gp_Pnt>& control_points, BRep_Builder& builder, TopoDS_Compound& compound, int& valid_edge_count) {
    // 创建折线
    BRepBuilderAPI_MakePolygon polygon;
    for (const auto& pnt : control_points) {
        polygon.Add(pnt);
    }
    // 检查是否闭合
    bool close_poly = false;
    auto cyclic_it = spline_info.find("use_cyclic_u");
    if (cyclic_it != spline_info.end()) {
        std::cout << "[STEP Exporter]   Found use_cyclic_u key, type: " << Py_TYPE(cyclic_it->second)->tp_name << std::endl;
        if (PyBool_Check(cyclic_it->second)) {
            close_poly = PyObject_IsTrue(cyclic_it->second) ? true : false;
            std::cout << "[STEP Exporter]   use_cyclic_u (bool): " << close_poly << std::endl;
        } else if (PyLong_Check(cyclic_it->second)) {
            long cyclic_val = PyLong_AsLong(cyclic_it->second);
            close_poly = (cyclic_val != 0);
            std::cout << "[STEP Exporter]   use_cyclic_u (int): " << cyclic_val << ", converted to: " << close_poly << std::endl;
        } else {
            std::cout << "[STEP Exporter]   use_cyclic_u value is not bool or int, using default: " << close_poly << std::endl;
        }
    } else {
        std::cout << "[STEP Exporter]   use_cyclic_u not found, using default: " << close_poly << std::endl;
    }
    std::cout << "[STEP Exporter]   close_poly: " << close_poly << ", control points: " << control_points.size() << std::endl;
    if (close_poly) {
        polygon.Close();
    }
    if (polygon.IsDone()) {
        TopoDS_Wire wire = polygon.Wire();
        // 计算边数量
        int edge_count = 0;
        TopoDS_Iterator it(wire);
        for (; it.More(); it.Next()) {
            if (it.Value().ShapeType() == TopAbs_EDGE) {
                edge_count++;
            }
        }
        std::cout << "[STEP Exporter]   Polygon wire edge count: " << edge_count << std::endl;
        // 将线转换为边
        TopoDS_Iterator it2(wire);
        for (; it2.More(); it2.Next()) {
            if (it2.Value().ShapeType() == TopAbs_EDGE) {
                builder.Add(compound, it2.Value());
                valid_edge_count++;
            }
        }
        return true;
    }
    return false;
}