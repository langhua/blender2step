// STEP Exporter curve common functions
#include "../include/step_exporter_internal.h"

std::vector<gp_Pnt> extract_control_points(const std::map<std::string, PyObject*>& spline_info) {
    std::vector<gp_Pnt> control_points;
    auto points_it = spline_info.find("control_points");
    if (points_it != spline_info.end() && PyList_Check(points_it->second)) {
        PyObject* points_list = points_it->second;
        Py_ssize_t num_points = PyList_Size(points_list);
        for (Py_ssize_t p = 0; p < num_points; p++) {
            PyObject* point_item = PyList_GetItem(points_list, p);
            if (PyList_Check(point_item) && PyList_Size(point_item) >= 3) {
                double x = PyFloat_AsDouble(PyList_GetItem(point_item, 0));
                double y = PyFloat_AsDouble(PyList_GetItem(point_item, 1));
                double z = PyFloat_AsDouble(PyList_GetItem(point_item, 2));
                // 缩放已在Python中应用，直接使用坐标
                control_points.push_back(gp_Pnt(x, y, z));
                std::cout << "[STEP Exporter] Control point " << p << ": (" << std::setprecision(15) << x << ", " << y << ", " << z << ")" << std::endl;
            }
        }
    }
    return control_points;
}

bool add_curve_to_compound(const Handle(Geom_Curve)& curve, const std::string& spline_type, bool close_curve, BRep_Builder& builder, TopoDS_Compound& compound, int& valid_edge_count) {
    if (!curve.IsNull()) {
        // 调试：检查曲线属性
        Handle(Geom_BSplineCurve) bspline_curve = Handle(Geom_BSplineCurve)::DownCast(curve);
        if (!bspline_curve.IsNull()) {
            std::cout << "[STEP Exporter]   Curve created - IsRational: " << (bspline_curve->IsRational() ? "YES" : "NO") 
                      << ", IsPeriodic: " << (bspline_curve->IsPeriodic() ? "YES" : "NO") 
                      << ", Degree: " << bspline_curve->Degree()
                      << ", NbPoles: " << bspline_curve->NbPoles()
                      << ", NbKnots: " << bspline_curve->NbKnots() << std::endl;
        }
        // 将几何曲线转换为边
        // 如果曲线需要闭合，检查是否为周期性曲线
        if (close_curve) {
            if (curve->IsPeriodic()) {
                std::cout << "[STEP Exporter]   Curve is already periodic" << std::endl;
            } else {
                // 使用bspline_curve检查是否为有理曲线
                if (!bspline_curve.IsNull()) {
                    if (!bspline_curve->IsRational()) {
                        std::cerr << "[STEP Exporter]   WARNING: Non-rational curve should be periodic but is not. Check knot vector and multiplicities." << std::endl;
                        std::cout << "[STEP Exporter]   B-spline curve parameters: degree=" << bspline_curve->Degree()
                                  << ", poles=" << bspline_curve->NbPoles()
                                  << ", knots=" << bspline_curve->NbKnots()
                                  << ", periodic=" << bspline_curve->IsPeriodic() << std::endl;
                    } else {
                        std::cout << "[STEP Exporter]   Rational closed curve (non-periodic) - this is expected" << std::endl;
                    }
                } else {
                    // 如果bspline_curve为空，输出通用警告
                    std::cerr << "[STEP Exporter]   WARNING: Closed curve is not periodic and cannot determine if rational" << std::endl;
                }
            }
        }
        BRepBuilderAPI_MakeEdge edgeMaker(curve);
        if (edgeMaker.IsDone()) {
            TopoDS_Edge edge = edgeMaker.Edge();
            builder.Add(compound, edge);
            valid_edge_count++;
            std::cout << "[STEP Exporter]   Created edge from " << spline_type << " curve" << std::endl;
            return true;
        }
    }
    return false;
}