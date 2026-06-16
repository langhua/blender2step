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
        // 
        // 策略：对于闭合曲线，尝试多种参数范围以确保最佳效果
        //
        // 背景：
        //   非周期性 B 样条的 FirstParameter()/LastParameter() 返回内部节点范围，
        //   例如 knots=[0,0,0,0.125,...,0.875,1,1,1], degree=3 -> 返回 [0.125, 0.875]
        //   这只覆盖 ~75% 的参数域，导致圆弧不完整
        //
        // 两级回退策略：
        //   1. 首先尝试完整节点范围 [Knot(1), Knot(NbKnots)] 以获得完整的曲线
        //   2. 如果失败（参数超出有效域），回退到 FirstParam/LastParam
        
        BRepBuilderAPI_MakeEdge edgeMaker;
        bool edgeCreated = false;
        
        if (close_curve && !curve.IsNull()) {
            Handle(Geom_BSplineCurve) bsp = Handle(Geom_BSplineCurve)::DownCast(curve);
            
            if (!bsp.IsNull() && !bsp->IsPeriodic()) {
                double fullU1 = bsp->Knot(1);               // 第一个节点（通常是0）
                double fullU2 = bsp->Knot(bsp->NbKnots());  // 最后一个节点（通常是1）
                double safeU1 = bsp->FirstParameter();       // 安全下界
                double safeU2 = bsp->LastParameter();        // 安全上界
                
                std::cout << "[STEP Exporter]   Attempting FULL KNOT RANGE [" << fullU1 << ", " << fullU2 
                          << "] for closed curve (safe range: [" << safeU1 << ", " << safeU2 << "])" << std::endl;
                
                // 第一级：尝试完整节点范围
                edgeMaker.Init(curve, fullU1, fullU2);
                
                if (!edgeMaker.IsDone()) {
                    std::cerr << "[STEP Exporter]   WARNING: Full knot range failed, falling back to safe range [" 
                              << safeU1 << ", " << safeU2 << "]" << std::endl;
                    // 第二级：回退到安全的参数范围
                    edgeMaker.Init(curve, safeU1, safeU2);
                    
                    if (!edgeMaker.IsDone()) {
                        std::cerr << "[STEP Exporter]   ERROR: Safe range also failed, trying default Init()" << std::endl;
                        edgeMaker.Init(curve);
                    }
                }
            } else {
                // 周期性曲线或其他类型：使用默认范围
                double u1 = curve->FirstParameter();
                double u2 = curve->LastParameter();
                std::cout << "[STEP Exporter]   Creating edge with default range [" << u1 << ", " << u2 
                          << "] for closed " << spline_type << " curve" << std::endl;
                edgeMaker.Init(curve, u1, u2);
            }
        } else {
            // 非闭合曲线：使用默认范围
            edgeMaker.Init(curve);
        }
        
        if (edgeMaker.IsDone()) {
            TopoDS_Edge edge = edgeMaker.Edge();
            builder.Add(compound, edge);
            valid_edge_count++;
            std::cout << "[STEP Exporter]   Created edge from " << spline_type << " curve" << std::endl;
            return true;
        } else {
            std::cerr << "[STEP Exporter]   ERROR: Failed to create edge for " << spline_type << " curve" << std::endl;
        }
    }
    return false;
}